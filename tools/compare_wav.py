#!/usr/bin/env python3
"""Compare two decode outputs (ours vs reference) for regression testing.

Usage: python compare_wav.py ours.wav ref.wav [--frames N]

Handles s16/f32/i32 WAVs, converts to float, reports global SNR / max diff,
per-channel SNR, and per-frame SNR (AC-4 frame = 2048 samples at 48 kHz)
with the worst frames listed. Channel count must match; sample counts may
differ by a leading offset (aligned via cross-correlation over the first
10 s)."""
import sys
import wave


def read_wav(path):
    """Minimal RIFF parser: PCM s16 (tag 1), float f32 (tag 3), or
    WAVE_FORMAT_EXTENSIBLE (0xFFFE) wrapping either."""
    import struct
    d = open(path, "rb").read()
    if d[:4] != b"RIFF" or d[8:12] != b"WAVE":
        raise SystemExit(f"not a WAV file: {path}")
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(d):
        cid = d[pos:pos + 4]
        clen = struct.unpack("<I", d[pos + 4:pos + 8])[0]
        body = d[pos + 8:pos + 8 + clen]
        if cid == b"fmt ":
            tag, nch, rate = struct.unpack("<HHI", body[:8])
            bits = struct.unpack("<H", body[14:16])[0]
            if tag == 0xFFFE:  # extensible: real tag in SubFormat GUID
                tag = struct.unpack("<H", body[24:26])[0] & 0xFFFF
                if len(body) >= 40:
                    guid = body[24:40]
                    if guid == bytes.fromhex("0300000000001000800000aa00389b71"):
                        tag = 3
                    elif guid == bytes.fromhex("0100000000001000800000aa00389b71"):
                        tag = 1
            fmt = (tag, nch, rate, bits)
        elif cid == b"data":
            data = body
        pos += 8 + clen + (clen & 1)
    if not fmt or data is None:
        raise SystemExit(f"missing fmt/data chunk in {path}")
    tag, nch, rate, bits = fmt
    if tag == 1 and bits == 16:
        import array
        a = array.array("h")
        a.frombytes(data[: len(data) // 2 * 2])
        x = [v / 32768.0 for v in a]
    elif tag == 3 and bits == 32:
        x = list(struct.unpack(f"<{len(data) // 4}f", data[: len(data) // 4 * 4]))
    else:
        raise SystemExit(f"unsupported wav format: tag={tag} bits={bits} in {path}")
    chs = [x[c::nch] for c in range(nch)]
    return chs, rate


def align(a, b, max_lag=512):
    """Return lag k such that a[i+k] aligns with b[i] (positive: a leads)."""
    n = min(len(a), len(b), 48000 * 10)
    best, best_ncc = 0, -2.0
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            ua, ub = a[k:k + n], b[:n - k] if k else b[:n]
        else:
            ua, ub = a[:n + k], b[-k:-k + n]
        m = min(len(ua), len(ub))
        sa = sum(ua[i] * ub[i] for i in range(m))
        ea = sum(v * v for v in ua) ** 0.5
        eb = sum(v * v for v in ub) ** 0.5
        if ea and eb:
            ncc = sa / (ea * eb)
            if ncc > best_ncc:
                best_ncc, best = ncc, k
    return best, best_ncc


def frame_snrs(a, b, frame_len):
    import math
    out = []
    for i in range(0, min(len(a), len(b)), frame_len):
        ua, ub = a[i:i + frame_len], b[i:i + frame_len]
        se = sum((x - y) ** 2 for x, y in zip(ua, ub))
        sp = sum(y * y for y in ub)
        snr = 10 * math.log10(sp / se) if se > 0 and sp > 0 else float("inf")
        out.append(snr)
    return out


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    import math
    ours_p, ref_p = sys.argv[1], sys.argv[2]
    frame_len = int(sys.argv[sys.argv.index("--frames") + 1]) if "--frames" in sys.argv else 2048
    a, ra = read_wav(ours_p)
    b, rb = read_wav(ref_p)
    if ra != rb:
        print(f"NOTE: sample rates differ ({ra} vs {rb}); continuing")
    if len(a) != len(b):
        raise SystemExit(f"channel mismatch: {len(a)} vs {len(b)}")
    n = min(len(x) for x in a + b)
    print(f"channels={len(a)} rate={ra}/{rb} samples={n}")
    total_se = total_sp = 0.0
    for c, (x, y) in enumerate(zip(a, b)):
        lag, ncc = align(x, y)
        if lag > 0:
            x = x[lag:]
        elif lag < 0:
            y = y[-lag:]
        m = min(len(x), len(y))
        se = sum((x[i] - y[i]) ** 2 for i in range(m))
        sp = sum(y[i] * y[i] for i in range(m))
        snr = float("inf") if se == 0 else 10 * math.log10(sp / se) if sp > 0 else float("-inf")
        md = max(abs(x[i] - y[i]) for i in range(m))
        print(f"ch{c}: align lag={lag} ncc={ncc:.4f}  SNR={snr:.2f} dB  maxdiff={md:.8f}  n={m}")
        total_se += se
        total_sp += sp
    gsnr = float("inf") if total_se == 0 else 10 * math.log10(total_sp / total_se)
    print(f"global SNR: {gsnr:.2f} dB")
    # per-frame SNR on channel 0 for locating desync
    fs = frame_snrs(a[0][:n], b[0][:n], frame_len)
    bad = sorted(range(len(fs)), key=lambda i: fs[i])[:8]
    print("worst frames (ch0, idx@framelen):",
          [(i, round(fs[i], 1)) for i in sorted(bad)])
    lo = sum(1 for s in fs if s < 20)
    print(f"frames below 20 dB: {lo}/{len(fs)}")


if __name__ == "__main__":
    main()
