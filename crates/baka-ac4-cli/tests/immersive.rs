//! Optional local-media acceptance; no copyrighted recordings or URLs embedded.
use baka_ac4_cli::mp4;
use baka_ac4_core::{Ac4Decoder, AudioKind};

#[test]
#[ignore = "set BAKA_AC4_IMMERSIVE_DIR to a local acceptance sample directory"]
fn complete_ajoc_tiers_have_finite_core_pcm_and_honest_layouts() {
    std::thread::Builder::new()
        .stack_size(64 * 1024 * 1024)
        .spawn(|| {
            let root = std::path::PathBuf::from(
                std::env::var_os("BAKA_AC4_IMMERSIVE_DIR").expect("sample directory"),
            );
            for (quality, signals) in [("dolbyajoc448", 8), ("dolbyajoc1500", 12)] {
                let bytes = std::fs::read(root.join(format!("{quality}.mp4"))).unwrap();
                let track = mp4::read_ac4_track(&bytes).unwrap();
                assert!(track.samples.len() > 1000);
                let mut decoder = Ac4Decoder::new().unwrap();
                decoder.set_ajoc_core_signals(true);
                let mut pcm = Vec::new();
                let mut peak = 0.0f32;
                let mut samples = 0usize;
                for (index, &(offset, size)) in track.samples.iter().enumerate() {
                    let packet = &bytes[offset as usize..offset as usize + size as usize];
                    let frame = decoder
                        .decode_frame_into(packet, &mut pcm)
                        .unwrap_or_else(|e| panic!("{quality} frame {index}: {e}"))
                        .expect("decoded frame");
                    assert_eq!(frame.audio_kind, AudioKind::AjocCoreSignals);
                    assert_eq!(frame.channel_mask, 0);
                    assert_eq!(frame.sample_rate, 48000);
                    assert_eq!(pcm.len(), signals);
                    for channel in &pcm {
                        assert_eq!(channel.len(), frame.nb_samples);
                        for &x in channel {
                            assert!(x.is_finite(), "{quality} frame {index}");
                            peak = peak.max(x.abs());
                        }
                    }
                    samples += frame.nb_samples;
                }
                assert!(peak > 0.01 && peak < 2.0, "{quality}: {peak}");
                assert!(samples > 48000 * 100);
                eprintln!(
                    "{quality}: {} frames, {samples} samples, {signals} signals, peak {peak}",
                    track.samples.len()
                );
            }
        })
        .unwrap()
        .join()
        .unwrap();
}
