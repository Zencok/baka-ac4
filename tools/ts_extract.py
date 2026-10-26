#!/usr/bin/env python3
"""Extract raw AC-4 elementary stream frames from an MPEG-TS capture.

Usage: python ts_extract.py <input.ts> <output.ac4> [--pid PID]

PES PIDs are auto-detected by sniffing payload start codes followed by an
AC-4 syncword (0xAC40/0xAC41). Framing from the sync header size fields:
    total = 4 + frame_size (16 bits)
    extended (frame_size == 0xFFFF): total = 7 + ext24
    0xAC41 frames carry a trailing 2-byte substream index: total += 2
"""
import sys
from collections import defaultdict

TS_LEN = 188


def parse_ts(data):
    """Yield (pid, pusi, payload_start_index, payload_len, cc)."""
    n = len(data) // TS_LEN
    for i in range(n):
        off = i * TS_LEN
        if data[off] != 0x47:
            # try to resync at 1-byte offsets within the first packet
            raise SystemExit(f"TS sync lost at packet {i} (offset {off:#x})")
        b1 = data[off + 1]
        if b1 & 0x80:  # transport_error_indicator
            continue
        pusi = bool(b1 & 0x40)
        pid = ((b1 & 0x1F) << 8) | data[off + 2]
        b3 = data[off + 3]
        afc = (b3 >> 4) & 3
        if afc in (0, 2):  # reserved or adaptation-only: no payload
            continue
        idx = off + 4
        if afc & 2:  # adaptation field present
            idx += 1 + data[off + 4]
        if idx >= off + TS_LEN:
            continue
        yield pid, pusi, idx, off + TS_LEN - idx, b3 & 0xF


def pes_payload_start(p):
    """Given payload starting at a PUSI, return (payload_off, payload_len_declared)
    or None if not a PES packet."""
    if len(p) < 9 or p[0] != 0 or p[1] != 0 or p[2] != 1:
        return None
    stream_id = p[3]
    if stream_id in (0xBC, 0xBE, 0xBF, 0xF0, 0xF1, 0xF2, 0xF8, 0xFF):
        # header is 6 bytes, no optional header
        return 6, (p[4] << 8) | p[5]
    hdr_data_len = p[8]
    return 9 + hdr_data_len, (p[4] << 8) | p[5]


def sniff(data, want_pid=None):
    """Find PIDs carrying PES payloads that start with an AC-4 syncword."""
    hits = defaultdict(int)
    pes = defaultdict(int)
    cur = {}  # pid -> bytearray of in-flight PES payload (for sniffing start)
    for pid, pusi, idx, plen, _cc in parse_ts(data):
        p = data[idx:idx + plen]
        if not pusi:
            continue
        r = pes_payload_start(p)
        if r is None:
            continue
        pes[pid] += 1
        off, _ = r
        rest = p[off:]
        if len(rest) >= 2 and rest[0] == 0xAC and rest[1] in (0x40, 0x41):
            hits[pid] += 1
    return hits, pes


def extract(data, pid, keep_partial=False):
    """Reassemble PES payloads for pid into a list of (bytes, intact_flag).

    A PES is intact when every TS packet arrived in continuity-counter order
    and the payload length matches the declared PES_packet_length."""
    out = []
    buf = None
    declared = 0
    got = 0
    intact = True
    last_cc = None
    for p, pusi, idx, plen, cc in parse_ts(data):
        if p != pid:
            continue
        if last_cc is not None and (last_cc + 1) & 0xF != cc:
            # packets lost (or duplicated) on this PID; any in-flight PES
            # is now incomplete
            if buf is not None:
                intact = False
        last_cc = cc
        p = data[idx:idx + plen]
        if pusi:
            if buf is not None:
                if intact or keep_partial:
                    out.append((bytes(buf[:declared]) if declared else bytes(buf), intact))
                buf = None
            r = pes_payload_start(p)
            if r is None:
                buf = None
                intact = True
                continue
            off, declared = r
            buf = bytearray(p[off:])
            intact = True
            if declared == 0:
                got = 0
            else:
                need_hdr = off - 6
                declared -= need_hdr
                got = len(buf)
                if got >= declared:
                    out.append((bytes(buf[:declared]), True))
                    buf = None
            continue
        elif buf is not None:
            if declared == 0:
                buf += p
            else:
                take = min(len(p), declared - got)
                buf += p[:take]
                got += take
                if got >= declared:
                    out.append((bytes(buf[:declared]), intact))
                    buf = None
    if buf is not None and (intact or keep_partial):
        out.append((bytes(buf[:declared]) if declared else bytes(buf), intact))
    return out


def split_frames(es):
    """Split an AC-4 ES into (offset, total_len) frames."""
    frames = []
    off = 0
    n = len(es)
    while off + 4 <= n:
        if es[off] != 0xAC or es[off + 1] not in (0x40, 0x41):
            break
        size = (es[off + 2] << 8) | es[off + 3]
        if size == 0xFFFF:
            if off + 7 > n:
                break
            ext = (es[off + 4] << 16) | (es[off + 5] << 8) | es[off + 6]
            total = 7 + ext
        else:
            total = 4 + size
        if es[off + 1] == 0x41:
            total += 2
        if off + total > n:
            break
        frames.append((off, total))
        off += total
    return frames, es[off:n] if off < n else b""


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    pid = None
    if "--pid" in sys.argv:
        pid = int(sys.argv[sys.argv.index("--pid") + 1], 0)
    data = open(src, "rb").read()
    hits, pes = sniff(data)
    print(f"PES start counts: {dict(pes)}")
    print(f"AC4 sync hits:    {dict(hits)}")
    if pid is None:
        if not hits:
            raise SystemExit("no AC-4 PES PID found")
        pid = max(hits, key=lambda k: hits[k])
        print(f"auto-selected PID {pid:#x}")
    pes_list = extract(data, pid)
    good = []
    for payload, intact in pes_list:
        if not intact or len(payload) < 8:
            continue
        if payload[0] != 0xAC or payload[1] not in (0x40, 0x41):
            continue
        frames, tail = split_frames(payload)
        if len(frames) == 1 and frames[0][1] == len(payload) and not tail:
            good.append(payload)
    n_intact = sum(1 for _, i in pes_list if i)
    print(f"PES total: {len(pes_list)}, intact: {n_intact}, "
          f"clean single-frame: {len(good)}")
    # longest consecutive run of clean frames
    best_run = run = 0
    for payload, intact in pes_list:
        ok = (intact and len(payload) >= 8 and payload[0] == 0xAC
              and payload[1] in (0x40, 0x41))
        if ok:
            run += 1
            best_run = max(best_run, run)
        else:
            run = 0
    print(f"longest consecutive clean run: {best_run} frames")
    if good:
        sizes = [len(f) for f in good]
        print(f"frame size min/avg/max: {min(sizes)}/{sum(sizes)//len(sizes)}/{max(sizes)}")
        out = bytearray()
        for f in good:
            out += f
        open(dst, "wb").write(bytes(out))
        print(f"wrote {dst}: {len(out)} bytes, {len(good)} frames")


if __name__ == "__main__":
    main()
