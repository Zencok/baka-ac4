"""Export bounded local MP4 packets for the Android reference runner.

No network access, source files are opened read-only. Requires ffprobe.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--limit", type=int, default=48)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1_000_000:
        parser.error("limit must be 1..1000000")
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must differ")
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a:0", "-show_packets",
        "-show_entries", "packet=pos,size", "-of", "json", str(args.input),
    ], capture_output=True, check=True, timeout=60)
    packets = json.loads(result.stdout)["packets"][:args.limit]
    if not packets:
        raise ValueError("no audio packets")
    with args.input.open("rb") as source, args.output.open("xb") as dest:
        for packet in packets:
            offset, size = int(packet["pos"]), int(packet["size"])
            if offset < 0 or not 1 <= size <= 131072:
                raise ValueError("invalid packet extent")
            source.seek(offset)
            data = source.read(size)
            if len(data) != size:
                raise ValueError("truncated packet")
            dest.write(struct.pack(">I", size))
            dest.write(data)
    print(f"exported {len(packets)} packets")


if __name__ == "__main__":
    main()
