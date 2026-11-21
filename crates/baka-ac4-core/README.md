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

Frame metadata provides `audio_kind`, `sample_rate`, `channel_mask`, `nb_samples` and `key_frame`. Packets may include an AC-4 sync header; `Ok(None)` means the decoder is waiting for an iframe.

Channel-coded audio, ASF/SSF, QMF and A-SPX paths are implemented. A-JOC downmix essence is available through explicit `set_ajoc_core_signals(true)`.
`AudioKind::AjocCoreSignals` identifies it; a zero `channel_mask` means the planes
are unanchored signals and must not be assigned speaker positions by count.
Object reconstruction, a basic stereo preview and spatial speaker rendering are opt-in; binaural rendering and reference parity remain pending.
ACPL successful decoding still needs real-stream validation. Full QMF processing is enabled by default.

For A-JOC matrix inspection, call `set_ajoc_metadata(true)` before decoding and
read `ajoc_metadata()` after a successful frame. This also enables core signal
output. The metadata includes dry/wet matrices, frequency/time differential
decoding, dequantized gains, QMF update ramps and payload boundary accounting.
Shared object timing is read from its declared substream. The supported profile
uses dynamic-only assignments and a non-alternative presentation. Object-major
`downmix_metadata` / `upmix_metadata` expose resolved gain, priority, position,
zone and other property values with PCM update offsets and smoothing durations.
`common` retains shared mastering screen ratio, bed-channel distribution and
the nine trim configurations (gain, front/back balance and Y-warp controls).
Default, disabled, custom, absent and reserved trim values remain distinct.
Both inline group headers and the shared OAMD substream feed these controls;
failed shared reads cannot commit partial controls or timing. Bed-render/future
extension bits are retained separately. Trim controls are applied in speaker
rendering; the basic stereo preview does not apply them.
Absolute/differential positions retain their standard-precision history separately
from extended precision. Position codes are room coordinates, not speaker labels.
Disabling inspection retains core output. Metadata is cleared on flush, a failed
packet or a packet that produces no A-JOC frame. Inspection allocates parameter
storage and is not the allocation-free playback path.

`set_ajoc_object_signals(true)` additionally reconstructs object PCM using all
eight parameter-band maps, cross-frame interpolation, the dry/wet pre-matrix,
seven independent decorrelator/ducker instances and independent QMF synthesis
histories. `AudioKind::AjocObjectSignals` has a zero speaker mask, with LFE first
when present. This is not a rendered listening output: OAMD gain/position,
speaker/headphone rendering and optional dialogue enhancement are not applied.
Object mode always uses full QMF processing. Disabling it retains core/metadata
mode; disabling core output or metadata inspection also disables object mode.

The standalone `ajoc::reconstruction::Reconstructor` accepts an explicit
decorrelation backend; `ajoc::decorrelation::AjocDecorrelation` implements the
specified filter/ducker stages. It operates on complex QMF planes, without LFE.
`copy_ajoc_core_qmf` exposes fullband planes from the last successfully inspected
frame. Validation errors occur before backend/history mutation; backend or
arithmetic failures reset both reconstruction and backend histories.
Reset both on seek. PCM object mode clears all these histories through `flush()`.

`set_ajoc_stereo_preview(true)` projects reconstructed objects to two channels
using resolved object gain and equal-power X panning. LFE uses a fixed 0.5 gain
into each side. Updates follow OAMD sample offsets and linear coefficient ramps,
including unfinished ramps across frames. No normalization/limiting is applied.
`AjocStereoPreview` has speaker mask `0x3`. This basic preview does not implement
Y/Z, zone/extent, trims, screen/distance/divergence controls or binaural cues;
it is not reference-equivalent immersive rendering. The standalone implementation
is `ajoc::stereo::StereoPreview`. Disabling preview retains raw object mode;
explicitly selecting raw object mode also disables preview. `flush()` resets it.

The host owns source access, demuxing, timestamps, seek pre-roll and audio output. `flush()` clears all stream histories and waits for a fresh iframe. Transform plans
and output options are preserved. Call it on the control path because it allocates
fresh channel history; it is not a real-time PCM callback operation.

Spatial speaker rendering is selected explicitly:

```rust
use baka_ac4_core::{Ac4Decoder, Result};
use baka_ac4_core::ajoc::render::{RenderOptions, SpeakerLayout};

fn enable_spatial(decoder: &mut Ac4Decoder) -> Result<()> {
    decoder.set_ajoc_render(Some(RenderOptions::new(SpeakerLayout::Surround714)))
}
```

Layouts are stereo, 5.1, 7.1, 5.1.4 and 7.1.4. The standalone implementation is
`ajoc::render::SpeakerRenderer`. It applies TS 103 448 source panning, size,
divergence, screen mapping, zone/elevation restrictions, global snap targets,
default/custom trim, object gain and sample ramps. `Screen` supplies physical
playback screen geometry; its defaults preserve coordinates. Speaker feeds have
kind `AjocSpeakerFeeds` and an actual speaker mask, in ascending WAVE bit order.
Stereo uses a 0.5-per-side LFE fold; surround uses discrete LFE. There is no bass
management, loudness correction, dialogue enhancement, limiter or HRTF processing.

Target ramps advance on the update sample and reach the new value in
`ramp_duration + 1` samples. State carries across frames and clears on flush,
configuration changes or a failed packet. Repeating identical options preserves
history; invalid options leave it intact. Standalone validation errors clear
output before history mutation; arithmetic failure also resets renderer history.
Changes in fullband/LFE meaning require reset even when total plane count stays
the same. Disabling an active renderer retains raw object mode; selecting raw
objects or preview disables rendering. Ordinary channel-coded streams are unaffected.

Dynamic-only A-JOC assignments are supported. Bed/mixed assignments, zone codes
6/7 and reserved divergence/trim codes are rejected. Mastering screen ratio and
priority are retained but ignored as directed by TS 103 448. Distance, Y-warp and
balance extensions are retained without application. Reference PCM parity is
not established. Rendering allocates metadata/gain storage and is not an
allocation-free callback path; float output may exceed unity.

[Project and CLI](https://github.com/Zencok/baka-ac4) · [简体中文](https://github.com/Zencok/baka-ac4/blob/main/README.zh-CN.md)

GPL-3.0-or-later. See the included `LICENSE` and `NOTICE` files.
