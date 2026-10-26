<div align="center">

# baka-ac4

**AC-4 audio decoding in pure Rust.**

[![Rust](https://img.shields.io/badge/Rust-2024-DEA584?logo=rust&logoColor=white)](Cargo.toml)
[![License](https://img.shields.io/badge/License-GPL--3.0--or--later-blue)](LICENSE)

**English** · [简体中文](README.zh-CN.md)

[Quick start](#quick-start) · [Rust API](#rust-api) · [Support](#support) · [Integration](#integration) · [Development](#development)

</div>

`baka-ac4` provides a standalone AC-4 decoder and command-line tools for MP4, M4A and raw AC-4 streams. The codec runs entirely in Rust, without a C decoder dependency.

- **Reusable decoder** — compressed packets in, planar `f32` PCM out.
- **Playback integration** — embed the core in your existing audio pipeline.
- **Practical CLI** — decode to WAV, inspect stream metadata and benchmark decoding.

## Quick start

Install the CLI with Rust and Cargo:

```sh
cargo install baka-ac4-cli --version 0.1.0 --locked
```

```sh
# Decode to 16-bit PCM WAV
baka-ac4 decode input.mp4 output.wav

# Preserve float32 PCM output
baka-ac4 decode --f32 input.ac4 output.wav

# Inspect frame metadata and coding tools as JSON
baka-ac4 toc input.m4a

# Benchmark decoding over 10 rounds
baka-ac4 bench input.mp4 10
```

MP4/M4A files must contain an AC-4 track. The CLI also accepts raw `.ac4` streams. Full QMF processing is enabled by default; the optional `decode --fast` shortcut changes the output and is not the fidelity-preserving path.

## Rust API

Add the decoder library to your project:

```toml
[dependencies]
baka-ac4-core = "0.1"
```

Reuse channel buffers across packets:

```rust
use baka_ac4_core::{Ac4Decoder, Result};

pub fn decode_packets(packets: &[Vec<u8>]) -> Result<()> {
    let mut decoder = Ac4Decoder::new()?;
    let mut pcm = Vec::new();

    for packet in packets {
        if let Some(frame) = decoder.decode_frame_into(packet, &mut pcm)? {
            // pcm[channel][sample]: planar f32 samples.
            // Consume PCM here before decoding the next packet.
            println!("{} Hz, {} channels", frame.sample_rate, pcm.len());
        }
    }
    Ok(())
}
```

Packets may include the `0xAC40` / `0xAC41` sync header. The decoder returns `Ok(None)` while waiting for an iframe. Frame metadata includes the sample rate, channel mask, sample count and key-frame flag. `decode_frame()` is also available when an owned `Frame` is more convenient.

## Support

| Area | Status |
| :--- | :--- |
| AC-4 TOC v1/v2 and channel-coded audio | Supported, including tested stereo and 5.1 streams |
| ASF, IMDCT, QMF, SAP and companding | Implemented |
| A-SPX, including balance mode | Supported on tested broadcast streams |
| SSF | Implemented; tested with controlled stream mutations |
| ACPL | Implemented paths; successful decoding still needs real-stream validation |
| Object-coded audio / A-JOC object rendering | Not supported |

Not every AC-4 profile or channel layout has been validated. The CLI writes basic WAV headers; applications that need speaker-position metadata should use the core's channel mask.

## Integration

Use `baka-ac4-core` as the codec layer and keep source access, demuxing, timestamps and audio output in your player. Prefer the system decoder when it supports the stream; use Rust decoding when it does not.

AC-4 decoding is stateful. Seek from a suitable iframe and discard pre-roll before the target. Recreate the decoder when complete history isolation is required: `flush()` marks the stream for resynchronization but does not clear every history array.

The core does not provide networking, DRM decryption or a playback device. The CLI reads the input file into memory and is intended for file conversion and inspection, not as a streaming playback layer.

## Development

```sh
cargo build --release --locked
cargo test --release --locked
cargo clippy --release --all-targets --locked -- -D warnings
```

Use release builds for decoding performance and mobile integration. Robustness tests include embedded fixtures; additional reference and stream-inspection tools are in [`tools/`](tools).

| Package | Purpose |
| :--- | :--- |
| [`baka-ac4-core`](crates/baka-ac4-core) | Decoder library, tests and examples |
| [`baka-ac4-cli`](crates/baka-ac4-cli) | File input, WAV output, inspection and benchmarks |

## License

[GPL-3.0-or-later](LICENSE). Third-party attribution is retained in [NOTICE](NOTICE).
