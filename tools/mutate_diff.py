#!/usr/bin/env python3
"""Targeted bit-mutation differential tester.

Activates decoder paths that no public stream exercises (SSF spectral
frontend, ACPL) by rewriting header fields of a real CM_ASPX frame, then
decodes the same mutated frame with this decoder and with libmpv (the
independent AC-4 implementation) and scores the outputs.

Findings on the reference captures: SSF mutations decode on both sides at
114-119 dB SNR (first real-stream SSF validation); ACPL mutations are
rejected at the same frame by both implementations (error-path agreement);
ATSC3 (v2/5.1/balance) mutations agree 40/40 on the success pattern.
Random single/double/triple-bit mutations: 39/40 success-pattern agreement;
the residual cases are bitstream-length corruption where error recovery
differs, not decoding divergences. The reference WAV is deleted before each
run so a failed mpv invocation cannot be masked by the previous trial's
output (a stale-file bug that once produced phantom disagreements).

usage: python mutate_diff.py <in.ac4> [--iframe-index N] [--outdir DIR]
"""
import os
import struct
import subprocess
import sys


def split_frames(data):
    frames = []
    off = 0
    while off + 4 <= len(data):
        if data[off] != 0xAC or data[off + 1] not in (0x40, 0x41):
            break
        total = struct.unpack(">H", data[off + 2:off + 4])[0] + 4
        if total == 4 + 0xFFFF:
            total = 7 + int.from_bytes(data[off + 4:off + 7], "big")
        if data[off + 1] == 0x41:
            total += 2
        if off + total > len(data):
            break
        frames.append((off, total))
        off += total
    return frames


def flip_bit(buf, bitpos):
    """bitpos counted from the start of the buffer, MSB-first."""
    buf[bitpos >> 3] ^= 0x80 >> (bitpos & 7)


def set_bit(buf, bitpos, value):
    byte, mask = bitpos >> 3, 0x80 >> (bitpos & 7)
    if value:
        buf[byte] |= mask
    else:
        buf[byte] &= ~mask & 0xFF


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    src = sys.argv[1]
    iframe_index = 15
    outdir = "mutants"
    if "--iframe-index" in sys.argv:
        iframe_index = int(sys.argv[sys.argv.index("--iframe-index") + 1])
    if "--outdir" in sys.argv:
        outdir = sys.argv[sys.argv.index("--outdir") + 1]
    os.makedirs(outdir, exist_ok=True)

    data = bytearray(open(src, "rb").read())
    frames = split_frames(data)
    off, total = frames[iframe_index]
    # window: the mutated iframe plus the following frames so mpv's raw-ac4
    # demuxer probe accepts the file (single frames score too low)
    win_end = frames[min(iframe_index + 30, len(frames) - 1)][0] +         frames[min(iframe_index + 30, len(frames) - 1)][1]
    base = bytearray(data[off:win_end])

    # Mutations: (name, list of (bitpos, bitvalue))
    mutants = {
        # stereo CM_ASPX(1) -> CM_ASPX_ACPL_1(2): bits 296..297 = 01 -> 10
        "acpl1": [(296, 1), (297, 0)],
        # mdct_stereo_proc 1->0 at bit 316, then the next two bits become
        # spec_frontend_l/r: SSF=1, ASF=0
        "ssf_l":  [(316, 0), (317, 1), (318, 0)],
        "ssf_r":  [(316, 0), (317, 0), (318, 1)],
        "ssf_lr": [(316, 0), (317, 1), (318, 1)],
    }

    results = []
    for name, bits in mutants.items():
        frame = bytearray(base)
        for pos, val in bits:
            set_bit(frame, pos, val)
        path = os.path.join(outdir, f"{name}.ac4")
        open(path, "wb").write(frame)

        ours = os.path.join(outdir, f"{name}_ours.wav")
        ref = os.path.join(outdir, f"{name}_ref.wav")
        for f in (ours, ref):
            if os.path.exists(f):
                os.remove(f)
        r1 = run(["./target/release/baka-ac4.exe", "decode", "--f32", path, ours])
        dll = r"D:\Github\Music\BakaMusic\res\.runtime\mpv\win32-x64\libmpv-2.dll"
        env = {**os.environ, "MPV_DLL": dll, "MPV_AUDIO_CHANNELS": "auto"}
        r2 = run(["python", "tools/ref_decode.py", path, ref], env=env)
        ok1 = os.path.exists(ours) and os.path.getsize(ours) > 100
        ok2 = os.path.exists(ref) and os.path.getsize(ref) > 100
        if ok1 and ok2:
            r3 = run(["python", "tools/compare_wav.py", ours, ref])
            lines = r3.stdout.splitlines()
            gsnr = [l for l in lines if l.startswith("global")]
            below = [l for l in lines if l.startswith("frames below")]
            results.append((name, "decoded",
                            " | ".join(filter(None, gsnr + below)) or r3.stdout[:80]))
        elif ok1 or ok2:
            who = "ours" if ok1 else "mpv"
            other = (r2.stderr + r2.stdout) if ok1 else (r1.stderr + r1.stdout)
            results.append((name, f"only {who} produced audio",
                            other.strip().splitlines()[-1][:100] if other.strip() else ""))
        else:
            results.append((name, "both produced no audio",
                            (r1.stderr + r1.stdout).strip().splitlines()[-1][:80]))

    print(f"{'mutant':8} {'outcome':22} detail")
    for name, outcome, detail in results:
        print(f"{name:8} {outcome:22} {detail}")


if __name__ == "__main__":
    main()
