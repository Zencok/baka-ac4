# baka-ac4-cli

Command-line AC-4 decoding, inspection and benchmarks, powered by `baka-ac4-core`.

The executable is named **`baka-ac4`**.

```sh
baka-ac4 decode input.mp4 output.wav
baka-ac4 decode --f32 input.ac4 output.wav
baka-ac4 toc input.m4a
baka-ac4 bench input.mp4 10
```

- Input: MP4/M4A containing an AC-4 track, or a raw `.ac4` stream.
  Truncated sample payloads and inconsistent tables are rejected before decoding.
- Output: 16-bit PCM WAV by default; `--f32` selects float32 WAV.
- `toc` emits frame metadata, output kind, speaker mask and coding-tool statistics as JSON.
- `--core-signals` explicitly enables A-JOC downmix essence for inspection or export.
  Unanchored planes have a zero speaker mask; they are not rendered surround feeds.
- `bench` reports minimum and median decoding time. The optional round count defaults to 10 and accepts `1..=10000`.

The CLI reads the input file into memory. It does not provide streaming playback or DRM decryption. Object-coded audio is unsupported; additional codec limitations are listed in the project documentation. Multichannel WAV output preserves the speaker mask using WAVE_FORMAT_EXTENSIBLE;
unanchored core signals retain a zero mask. A format change or non-finite sample
is rejected instead of corrupting a single-format WAV.

The optional `decode --fast` QMF shortcut changes the output. Use the default path when full processing fidelity is required.

[Project and Rust API](https://github.com/Zencok/baka-ac4) · [简体中文](https://github.com/Zencok/baka-ac4/blob/main/README.zh-CN.md)

GPL-3.0-or-later. See the included `LICENSE` and `NOTICE` files.
