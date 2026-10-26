#!/usr/bin/env python3
"""Capture libmpv decoder log messages for a media file (diagnostics).

usage: python mpv_log.py <input> [libmpv-2.dll]
"""
import ctypes
import os
import sys

MPV_FORMAT_NONE = 0
MPV_EVENT_NONE = 0
MPV_EVENT_SHUTDOWN = 1
MPV_EVENT_END_FILE = 7
MPV_EVENT_LOG_MESSAGE = 2

MPV_ERROR_SUCCESS = 0


class MpvEvent(ctypes.Structure):
    _fields_ = [
        ("event_id", ctypes.c_int),
        ("error", ctypes.c_int),
        ("reply_userdata", ctypes.c_uint64),
        ("data", ctypes.c_void_p),
    ]


class MpvEventLogMessage(ctypes.Structure):
    _fields_ = [
        ("prefix", ctypes.c_char_p),
        ("level", ctypes.c_char_p),
        ("text", ctypes.c_char_p),
        ("log_level", ctypes.c_int),
    ]


def main() -> int:
    src = sys.argv[1]
    dll_path = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("MPV_DLL", "libmpv-2.dll")
    os.add_dll_directory(os.path.dirname(os.path.abspath(dll_path)))
    mpv = ctypes.CDLL(dll_path)

    mpv.mpv_create.restype = ctypes.c_void_p
    mpv.mpv_initialize.argtypes = [ctypes.c_void_p]
    mpv.mpv_initialize.restype = ctypes.c_int
    mpv.mpv_set_option_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    mpv.mpv_set_option_string.restype = ctypes.c_int
    mpv.mpv_command.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
    mpv.mpv_command.restype = ctypes.c_int
    mpv.mpv_wait_event.argtypes = [ctypes.c_void_p, ctypes.c_double]
    mpv.mpv_wait_event.restype = ctypes.POINTER(MpvEvent)
    mpv.mpv_request_log_messages.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    mpv.mpv_terminate_destroy.argtypes = [ctypes.c_void_p]
    mpv.mpv_free.argtypes = [ctypes.c_void_p]

    handle = mpv.mpv_create()
    if not handle:
        raise SystemExit("mpv_create failed")
    for opt, val in (
        ("vo", "null"),
        ("ao", "pcm"),
        ("ao-pcm-file", os.environ.get("MPV_PCM_OUT", "ref_log_out.wav")),
        ("audio-display", "no"),
        ("terminal", "no"),
        ("audio-channels", "stereo"),
        ("gapless-audio", "no"),
        ("reset-on-next-file", "all"),
    ):
        mpv.mpv_set_option_string(handle, opt.encode(), val.encode())
    if mpv.mpv_initialize(handle) != 0:
        raise SystemExit("mpv_initialize failed")
    mpv.mpv_request_log_messages(handle, b"trace")

    loadfile = (ctypes.c_char_p * 4)(b"loadfile", src.encode(), b"replace", None)
    mpv.mpv_command(handle, loadfile)

    counts = {}
    while True:
        ev = mpv.mpv_wait_event(handle, 5.0)
        eid = ev.contents.event_id
        if eid == MPV_EVENT_LOG_MESSAGE:
            msg = ctypes.cast(ev.contents.data, ctypes.POINTER(MpvEventLogMessage)).contents
            prefix = msg.prefix.decode(errors="replace") if msg.prefix else ""
            level = msg.level.decode(errors="replace") if msg.level else ""
            text = msg.text.decode(errors="replace") if msg.text else ""
            key = f"{prefix}/{level}"
            counts[key] = counts.get(key, 0) + 1
            if any(k in text.lower() for k in ("error", "invalid", "fail", "ac4", "aspx")):
                print(f"[{prefix}/{level}] {text.strip()}")
        elif eid == MPV_EVENT_END_FILE:
            break
        elif eid == MPV_EVENT_SHUTDOWN:
            break
    mpv.mpv_terminate_destroy(handle)
    print("--- log message counts by prefix/level ---")
    for k, v in sorted(counts.items()):
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
