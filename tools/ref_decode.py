#!/usr/bin/env python3
"""Decode any media file to a WAV using libmpv.

Drives libmpv-2.dll through the C client API with --ao=pcm, producing a WAV
of exactly what another AC-4-capable player would output. Useful as the
comparison side of decode regression runs (see compare_wav.py).

usage: python ref_decode.py <input.mp4> <output.wav> [libmpv-2.dll]
       (the DLL path defaults to the MPV_DLL environment variable)
"""
import ctypes
import os
import sys
import time

MPV_FORMAT_NONE = 0
MPV_EVENT_NONE = 0
MPV_EVENT_SHUTDOWN = 1
MPV_EVENT_END_FILE = 7


class MpvEvent(ctypes.Structure):
    _fields_ = [
        ("event_id", ctypes.c_int),
        ("error", ctypes.c_int),
        ("reply_userdata", ctypes.c_uint64),
        ("data", ctypes.c_void_p),
    ]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    dll_path = (
        sys.argv[3]
        if len(sys.argv) > 3
        else os.environ.get("MPV_DLL", "libmpv-2.dll")
    )
    os.add_dll_directory(os.path.dirname(os.path.abspath(dll_path)))
    mpv = ctypes.CDLL(dll_path)

    mpv.mpv_create.restype = ctypes.c_void_p
    mpv.mpv_initialize.argtypes = [ctypes.c_void_p]
    mpv.mpv_set_option_string.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
    ]
    mpv.mpv_command.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
    mpv.mpv_wait_event.argtypes = [ctypes.c_void_p, ctypes.c_double]
    mpv.mpv_wait_event.restype = ctypes.POINTER(MpvEvent)
    mpv.mpv_terminate_destroy.argtypes = [ctypes.c_void_p]

    ctx = mpv.mpv_create()
    if not ctx:
        print("mpv_create failed")
        return 1
    opts = {
        "vo": "null",
        "ao": "pcm",
        "ao-pcm-file": dst,
        "audio-display": "no",
        "terminal": "no",
        "audio-channels": os.environ.get("MPV_AUDIO_CHANNELS", "stereo"),
        "gapless-audio": "no",
        "reset-on-next-file": "all",
    }
    for k, v in opts.items():
        r = mpv.mpv_set_option_string(ctx, k.encode(), v.encode())
        if r < 0:
            print(f"option {k}={v} failed: {r}")
            return 1
    r = mpv.mpv_initialize(ctx)
    if r < 0:
        print(f"mpv_initialize failed: {r}")
        return 1

    cmd = (ctypes.c_char_p * 4)(
        b"loadfile", src.encode(), b"replace", None
    )
    r = mpv.mpv_command(ctx, cmd)
    if r < 0:
        print(f"loadfile failed: {r}")
        return 1

    deadline = time.time() + 600
    while time.time() < deadline:
        ev = mpv.mpv_wait_event(ctx, 1.0)
        eid = ev.contents.event_id
        if eid == MPV_EVENT_END_FILE:
            break
        if eid == MPV_EVENT_SHUTDOWN:
            break
    mpv.mpv_terminate_destroy(ctx)

    if not os.path.exists(dst) or os.path.getsize(dst) < 44:
        print("no output written")
        return 1
    print(f"wrote {dst} ({os.path.getsize(dst)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
