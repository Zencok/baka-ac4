# baka-ac4-core

Pure Rust AC-4 audio decoding. No C decoder dependency.

Decode compressed AC-4 packets into planar `f32` PCM, reusing channel buffers between frames:

```rust
use baka_ac4_core::{Ac4Decoder, Result};

fn decode_packets(packets: &[Vec<u8>]) -> Result<()> {
    let mut decoder = Ac4Decoder::new()?;
    let mut pcm = Vec::new();
    for packet in packets {
        if let Some(frame) = decoder.decode_frame_into(packet, &mut pcm)? {
            println!("{} Hz, {} channels", frame.sample_rate, pcm.len());
            // Consume pcm[channel][sample] before the next decode call.
        }
    }
    Ok(())
}
```

Frame metadata provides `sample_rate`, `channel_mask`, `nb_samples` and `key_frame`. Packets may include an AC-4 sync header; `Ok(None)` means the decoder is waiting for an iframe.

Channel-coded audio, ASF/SSF, QMF and A-SPX paths are implemented. Object-coded audio is unsupported, and ACPL successful decoding still needs real-stream validation. Full QMF processing is enabled by default.

The host owns source access, demuxing, timestamps, seek pre-roll and audio output. Recreate the decoder for complete history isolation; `flush()` marks resynchronization without clearing every history array.

[Project and CLI](https://github.com/Zencok/baka-ac4) · [简体中文](https://github.com/Zencok/baka-ac4/blob/main/README.zh-CN.md)

GPL-3.0-or-later. See the included `LICENSE` and `NOTICE` files.
