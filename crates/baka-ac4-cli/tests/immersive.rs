//! Optional local-media acceptance; no copyrighted recordings or URLs embedded.
use baka_ac4_cli::mp4;
use baka_ac4_core::{Ac4Decoder, AudioKind};

#[test]
#[ignore = "set BAKA_AC4_IMMERSIVE_DIR to a local acceptance sample directory"]
fn complete_ajoc_tiers_reconstruct_object_signals_and_reset() {
    std::thread::Builder::new()
        .stack_size(64 * 1024 * 1024)
        .spawn(|| {
            let root = std::path::PathBuf::from(
                std::env::var_os("BAKA_AC4_IMMERSIVE_DIR").expect("sample directory"),
            );
            for quality in ["dolbyajoc448", "dolbyajoc1500"] {
                let bytes = std::fs::read(root.join(format!("{quality}.mp4"))).unwrap();
                let track = mp4::read_ac4_track(&bytes).unwrap();
                let mut decoder = Ac4Decoder::new().unwrap();
                decoder.set_qmf_bypass(true); // object mode must still use full QMF
                decoder.set_ajoc_object_signals(true);
                let mut pcm = Vec::new();
                let mut first = Vec::new();
                let mut peak = 0.0f32;
                let mut active = [false; 21];
                let started = std::time::Instant::now();
                for (index, &(offset, size)) in track.samples.iter().enumerate() {
                    let packet = &bytes[offset as usize..offset as usize + size as usize];
                    let frame = decoder
                        .decode_frame_into(packet, &mut pcm)
                        .unwrap_or_else(|e| panic!("{quality} object frame {index}: {e}"))
                        .unwrap();
                    assert_eq!(frame.audio_kind, AudioKind::AjocObjectSignals);
                    assert_eq!(frame.channel_mask, 0);
                    assert_eq!(pcm.len(), 21);
                    assert_eq!(frame.sample_rate, 48000);
                    assert_eq!(frame.nb_samples, 2048);
                    for (signal, plane) in pcm.iter().enumerate() {
                        assert_eq!(plane.len(), frame.nb_samples);
                        for &x in plane {
                            assert!(x.is_finite());
                            peak = peak.max(x.abs());
                            active[signal] |= x.abs() > 1.0e-6;
                        }
                    }
                    if index < 6 {
                        first.push(pcm.clone());
                    }
                }
                assert!(
                    active.into_iter().all(|a| a),
                    "{quality}: inactive objects {active:?}"
                );
                assert!(peak > 0.01 && peak < 10.0, "{quality}: peak {peak}");
                eprintln!(
                    "{quality}: {} reconstructed object frames, peak {peak}, {:.3}s",
                    track.samples.len(),
                    started.elapsed().as_secs_f64()
                );
                decoder.flush();
                for (index, &(offset, size)) in track.samples[..6].iter().enumerate() {
                    decoder
                        .decode_frame_into(
                            &bytes[offset as usize..offset as usize + size as usize],
                            &mut pcm,
                        )
                        .unwrap()
                        .unwrap();
                    assert_eq!(pcm, first[index], "{quality}: reset frame {index}");
                }
                decoder.set_ajoc_object_signals(false);
                decoder.set_qmf_bypass(false);
                let (offset, size) = track.samples[0];
                let core = decoder
                    .decode_frame_into(
                        &bytes[offset as usize..offset as usize + size as usize],
                        &mut pcm,
                    )
                    .unwrap()
                    .unwrap();
                assert_eq!(core.audio_kind, AudioKind::AjocCoreSignals);
                assert_eq!(
                    pcm[0], first[0][0],
                    "LFE must retain the core plane and order"
                );
                assert_eq!(pcm.len(), if quality.ends_with("448") { 8 } else { 12 });
                decoder.set_ajoc_object_signals(true);
                decoder
                    .decode_frame_into(
                        &bytes[offset as usize..offset as usize + size as usize],
                        &mut pcm,
                    )
                    .unwrap()
                    .unwrap();
                assert_eq!(pcm.len(), 21);
                assert!(decoder.decode_frame_into(&[0; 7], &mut pcm).is_err());
                assert!(pcm.is_empty());
                decoder.set_ajoc_core_signals(false);
                let (offset, size) = track.samples[0];
                assert!(
                    decoder
                        .decode_frame_into(
                            &bytes[offset as usize..offset as usize + size as usize],
                            &mut pcm
                        )
                        .is_err()
                );
            }
        })
        .unwrap()
        .join()
        .unwrap();
}

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
                decoder.set_ajoc_metadata(true);
                let mut pcm = Vec::new();
                let mut peak = 0.0f32;
                let mut samples = 0usize;
                let mut max_padding = 0;
                let mut dt_count = 0;
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
                    let metadata = decoder.ajoc_metadata().expect("requested A-JOC metadata");
                    assert_eq!(metadata.objects.len(), 20);
                    assert!(metadata.bits > 20);
                    assert!(
                        metadata.padding_bits <= 7,
                        "{quality} frame {index}: unparsed metadata"
                    );
                    assert_eq!(metadata.downmix_blocks, 1);
                    assert_eq!(metadata.upmix_blocks, 1);
                    assert_eq!(metadata.decorrelators, [true, true, true]);
                    for object in metadata.objects.iter().filter(|o| o.present) {
                        assert_eq!(object.bands, if signals == 8 { 12 } else { 23 });
                        for matrix in object.dry.iter().chain(&object.wet).flatten().flatten() {
                            assert_eq!(matrix.gains.len(), object.bands);
                            assert!(
                                matrix
                                    .gains
                                    .iter()
                                    .all(|x| x.is_finite() && x.abs() <= 5.005)
                            );
                        }
                    }
                    max_padding = max_padding.max(metadata.padding_bits);
                    dt_count += metadata
                        .objects
                        .iter()
                        .flat_map(|o| o.dry.iter().chain(&o.wet))
                        .flatten()
                        .flatten()
                        .filter(|m| m.time_delta)
                        .count();
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
                assert!(dt_count > 100000, "must exercise cross-frame time deltas");
                decoder.flush();
                assert!(decoder.ajoc_metadata().is_none());
                let mut qmf = Vec::new();
                assert!(decoder.copy_ajoc_core_qmf(&mut qmf).is_err());
                let (offset, size) = track.samples[0];
                assert!(
                    decoder
                        .decode_frame_into(
                            &bytes[offset as usize..offset as usize + size as usize],
                            &mut pcm
                        )
                        .unwrap()
                        .is_some()
                );
                assert!(decoder.ajoc_metadata().is_some());
                decoder.copy_ajoc_core_qmf(&mut qmf).unwrap();
                assert_eq!(qmf.len(), signals - 1);
                assert!(qmf.iter().all(|plane| plane.len() == 32));
                assert!(
                    qmf.iter()
                        .flatten()
                        .flatten()
                        .flatten()
                        .all(|v| v.is_finite())
                );
                assert!(decoder.decode_frame_into(&[0; 7], &mut pcm).is_err());
                assert!(decoder.ajoc_metadata().is_none());
                eprintln!(
                    "metadata: padding <= {max_padding} bits, {dt_count} time-delta elements"
                );
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
