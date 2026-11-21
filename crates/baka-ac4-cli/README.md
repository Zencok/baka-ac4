# baka-ac4-cli

Command-line AC-4 decoding, inspection and benchmarks, powered by `baka-ac4-core`.

The executable is named **`baka-ac4`**.

```sh
baka-ac4 decode input.mp4 output.wav
baka-ac4 decode --f32 input.ac4 output.wav
baka-ac4 toc input.m4a
baka-ac4 bench input.mp4 10
baka-ac4 decode --object-signals --f32 input.mp4 objects.wav
baka-ac4 decode --stereo-preview --f32 input.mp4 preview.wav
baka-ac4 decode --render=7.1.4 --f32 input.mp4 speakers.wav
```

- Input: MP4/M4A containing an AC-4 track, or a raw `.ac4` stream.
  Truncated sample payloads and inconsistent tables are rejected before decoding.
- Output: 16-bit PCM WAV by default; `--f32` selects float32 WAV.
- `toc` emits frame metadata, output kind, speaker mask and coding-tool statistics as JSON.
- `--core-signals` explicitly enables A-JOC downmix essence for inspection or export.
  Unanchored planes have a zero speaker mask; they are not rendered surround feeds.
- `--object-signals` reconstructs object signals, with LFE first when present,
  and labels `toc` output `ajoc-object-signals`. It retains a zero speaker mask.
  Object gains/positions are not rendered. Use `--f32` to retain peaks above unity.
  This option conflicts with `--core-signals` and `--fast`.
- `--stereo-preview` applies object gain and equal-power left/right panning with
  sample-timed smoothing. TOC labels it `ajoc-stereo-preview`, with mask `0x3`.
  This is a basic stereo projection; Y/Z, zone/extent, trims, distance/divergence
  and binaural cues are not applied. No normalization or limiting is applied;
  use `--f32` to preserve peaks. It conflicts with other signal modes and `--fast`.
- `bench` reports minimum and median decoding time. The optional round count defaults to 10 and accepts `1..=10000`.
- `--render=stereo|5.1|7.1|5.1.4|7.1.4` renders dynamic objects to speaker
  feeds using three-axis panning, size/divergence, zones/snap, screen mapping,
  trim and timed gain ramps. TOC labels the output `ajoc-speaker-feeds` and
  provides the actual WAVE speaker mask. Stereo folds LFE equally at 0.5;
  other layouts retain discrete LFE. No limiting or presentation loudness is
  applied. It conflicts with other A-JOC modes and `--fast`.

The CLI reads the input file into memory. It does not provide streaming playback or DRM decryption. Default decoding rejects object-coded audio; choose an explicit A-JOC mode, including `--render` for speaker feeds. Binaural headphone rendering is not provided. Additional codec limitations are listed in the project documentation. Multichannel WAV output preserves the speaker mask using WAVE_FORMAT_EXTENSIBLE;
unanchored core signals retain a zero mask. A format change or non-finite sample
is rejected instead of corrupting a single-format WAV.

The optional `decode --fast` QMF shortcut changes the output. Use the default path when full processing fidelity is required.

[Project and Rust API](https://github.com/Zencok/baka-ac4) · [简体中文](https://github.com/Zencok/baka-ac4/blob/main/README.zh-CN.md)

GPL-3.0-or-later. See the included `LICENSE` and `NOTICE` files.
