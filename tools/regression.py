#!/usr/bin/env python3
"""One-command regression suite for baka-ac4.

Runs, in order:
  1. cargo test --release  (unit tests + panic-safety fuzzer)
  2. cargo clippy --release --all-targets (must be warning-free)
  3. decode checks over the local sample set (feature stats, frame counts,
     bit-exact md5 against tools/baselines.json)
  4. if MPV_DLL is set: reference decode + SNR comparison for each stream
  5. mutation differential (SSF activation) with an SNR floor

Baselines: `python tools/regression.py --update-baselines` rewrites
tools/baselines.json from the current outputs. Float output is deterministic
on the same build/CPU class; treat cross-machine md5 mismatches with
`--update-baselines` after eyeballing the SNR column.

Sample locations default to <repo>/../test-samples (gitignored); override
with --samples-dir. Missing samples are reported as SKIP, not failure.

usage: python tools/regression.py [--update-baselines] [--samples-dir DIR]
                                  [--skip-fuzz] [--fuzz-iters N]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
EXE = os.path.join(REPO, "target", "release", "baka-ac4.exe")
BASELINES = os.path.join(HERE, "baselines.json")

SAMPLES = [
    # key, file, description, expected feature-stats fragment
    ("htys", "荷塘月色-凤凰传奇.mp4", "CM_SIMPLE stereo MP4", "CM_SIMPLE"),
    ("p83", "uhd_c24_p83.ac4", "CM_ASPX stereo broadcast", "CM_ASPX(l=asf"),
    ("atsc3", "atsc3.ac4", "CM_ASPX 5.1 v2 broadcast", "CM_ASPX(l=asf"),
]

# Global-SNR floors. atsc3's floor is much lower by construction: its two
# balance-mode channels sit in the reference decoder's UB region (~45-51 dB)
# which drags the global value down; the well-defined channels measure
# 88-115 dB (verified per-channel in the milestone-3 investigation).
SNR_FLOOR = {
    "htys": 100.0,
    "p83": 80.0,
    "atsc3": 40.0,
}
MUTATION_SNR_FLOOR = 100.0


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, env=None, cwd=REPO):
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd)


def sh_failure(name, res):
    print(f"FAIL {name}")
    tail = (res.stderr or res.stdout or "").strip().splitlines()[-8:]
    for line in tail:
        print("     " + line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-baselines", action="store_true")
    ap.add_argument("--samples-dir", default=os.path.join(REPO, "..", "test-samples"))
    ap.add_argument("--skip-fuzz", action="store_true")
    ap.add_argument("--fuzz-iters", type=int, default=None)
    args = ap.parse_args()

    failures = []
    baselines = {}
    if os.path.exists(BASELINES):
        baselines = json.load(open(BASELINES))
    baselines.setdefault("md5", {})

    dll = os.environ.get("MPV_DLL", "")

    # 1+2: build, tests, clippy -------------------------------------------
    print("== cargo build --release")
    res = run(["cargo", "build", "--release"])
    if res.returncode != 0:
        sh_failure("build", res)
        failures.append("build")
        print_summary(failures)
        return 1

    env = dict(os.environ)
    if args.skip_fuzz:
        print("== cargo test --release (fuzz skipped)")
        res = run(["cargo", "test", "--release", "--lib", "--bins"], env=env)
    else:
        if args.fuzz_iters:
            env["BAKA_FUZZ_ITERS"] = str(args.fuzz_iters)
        n = env.get("BAKA_FUZZ_ITERS", "20000")
        print(f"== cargo test --release (fuzz iters={n})")
        res = run(["cargo", "test", "--release"], env=env)
    if res.returncode != 0:
        sh_failure("cargo test", res)
        failures.append("cargo test")
    else:
        print("PASS cargo test")

    res = run(["cargo", "clippy", "--release", "--all-targets"])
    warns = [l for l in (res.stderr or "").splitlines()
             if l.startswith("warning: ") or l.startswith("error")]
    if res.returncode != 0 or warns:
        sh_failure("clippy", res)
        failures.append("clippy")
    else:
        print("PASS clippy (0 warnings)")

    # 3+4: sample streams ---------------------------------------------------
    tmp = os.path.join(args.samples_dir, "tmp")
    os.makedirs(tmp, exist_ok=True)
    snr_results = {}
    for key, fname, desc, feat_fragment in SAMPLES:
        src = os.path.join(args.samples_dir, fname)
        if not os.path.exists(src):
            print(f"SKIP {key}: {fname} not found in {args.samples_dir}")
            continue
        wav = os.path.join(tmp, f"reg_{key}.wav")
        res = run([EXE, "decode", "--f32", src, wav])
        if res.returncode != 0:
            sh_failure(f"decode {key}", res)
            failures.append(f"decode {key}")
            continue
        m = [l for l in (res.stdout or "").splitlines() if l.startswith("decoded")]
        print(f"     {key}: {m[0] if m else '?'}")

        res = run([EXE, "toc", src])
        tools_line = ""
        if res.returncode == 0:
            try:
                stats = json.loads(res.stdout)["tools"]
                tools_line = "; ".join(f"{k}: {v}" for k, v in stats.items())
                if feat_fragment not in res.stdout:
                    failures.append(f"features {key}")
                    print(f"FAIL features {key}: expected '{feat_fragment}' in {tools_line}")
            except json.JSONDecodeError:
                failures.append(f"toc {key}")
                print(f"FAIL toc {key}: invalid JSON")
        if feat_fragment in res.stdout:
            print(f"     {key} tools: {tools_line}")

        digest = md5(wav)
        expected = baselines["md5"].get(key)
        if expected is None or args.update_baselines:
            baselines["md5"][key] = digest
            print(f"     {key} md5 {digest} (baseline {'updated' if expected else 'set'})")
        elif digest != expected:
            print(f"WARN {key}: md5 {digest} != baseline {expected}")
            print("     (float output can differ across CPU classes; check the")
            print("      SNR column below, then --update-baselines if justified)")
        else:
            print(f"PASS {key} md5 matches baseline")

        if dll and os.path.exists(dll):
            ref = os.path.join(tmp, f"reg_{key}_ref.wav")
            renv = {**os.environ, "MPV_DLL": dll, "MPV_AUDIO_CHANNELS": "auto"}
            res = run(["python", os.path.join(HERE, "ref_decode.py"), src, ref], env=renv)
            if res.returncode != 0 or not os.path.exists(ref):
                sh_failure(f"ref_decode {key}", res)
                failures.append(f"ref_decode {key}")
                continue
            res = run(["python", os.path.join(HERE, "compare_wav.py"), wav, ref])
            gsnr = [l for l in res.stdout.splitlines() if l.startswith("global")]
            if gsnr:
                val = float(gsnr[0].split()[2])
                snr_results[key] = val
                floor = SNR_FLOOR.get(key, 80.0)
                status = "PASS" if val >= floor else "FAIL"
                print(f"{status} {key} SNR vs reference: {val:.2f} dB (floor {floor})")
                if val < floor:
                    failures.append(f"snr {key}")

    # 5: mutation differential ---------------------------------------------
    if os.path.exists(os.path.join(args.samples_dir, "uhd_c24_p83.ac4")):
        print("== mutation differential (SSF activation)")
        res = run(["python", os.path.join(HERE, "mutate_diff.py"),
                   os.path.join(args.samples_dir, "uhd_c24_p83.ac4")])
        ssf_lines = [l for l in (res.stdout or "").splitlines()
                     if l.startswith("ssf_") and "decoded" in l]
        ok_mut = False
        for l in ssf_lines:
            print("     " + l.strip())
            if "global SNR" in l:
                try:
                    val = float(l.split("global SNR:")[1].split("dB")[0])
                    if val >= MUTATION_SNR_FLOOR:
                        ok_mut = True
                except (ValueError, IndexError):
                    pass
        if ok_mut:
            print(f"PASS mutation differential (SSF SNR >= {MUTATION_SNR_FLOOR} dB)")
        else:
            failures.append("mutation differential")
            print("FAIL mutation differential: no ssf_* mutant at/above floor")
    else:
        print("SKIP mutation differential (p83 sample missing)")

    # persist baselines ------------------------------------------------------
    if args.update_baselines:
        json.dump(baselines, open(BASELINES, "w"), indent=1)
        print(f"baselines written: {BASELINES}")

    print_summary(failures)
    return 1 if failures else 0


def print_summary(failures):
    print()
    if failures:
        print(f"REGRESSION FAILED ({len(failures)}): " + ", ".join(failures))
    else:
        print("REGRESSION OK")


if __name__ == "__main__":
    sys.exit(main())
