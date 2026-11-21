# Codec validation tools

| Tool | Purpose |
| --- | --- |
| `regression.py` | Rust checks, local decode baselines and SSF differential validation |
| `compare_wav.py` | Align PCM and measure channel/global SNR |
| `ref_decode.py` | Produce a comparison WAV using an available libmpv decoder |
| `export_reference_packets.py` | Export bounded packets from a local MP4 for native reference checks |
| `reference_probe.c` | Android ARM64 runner for compatible external decoder ABIs; validate actual nonzero PCM |

[Acceptance records and native runner commands](../docs/AC4_DELIVERY.md).
External libraries, media, credentials and signed URLs are local inputs only.
Reference output is comparison evidence; it is never an input to Rust decoding.
