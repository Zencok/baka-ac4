# Changelog

## 0.1.0

- Initial Rust AC-4 decoder and file-conversion CLI.
- Planar f32 output, frame metadata and reusable PCM buffers.
- Channel-coded audio, ASF/SSF frontends, QMF, SAP, companding and A-SPX processing.
- MP4/M4A and raw AC-4 input; s16/f32 WAV output, JSON inspection and benchmarks.
- Reusable FFT workspaces, shared immutable tables and long-code VLC lookup improvements.
- Embedded regression fixtures, robustness tests and transform-allocation checks.

Object-coded audio is unsupported. ACPL successful decoding and additional stream layouts require further validation.
