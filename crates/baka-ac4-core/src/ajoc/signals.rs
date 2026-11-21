//! Reconstructed fullband object PCM; separate from OAMD rendering.

use super::AjocMetadata;
use super::decorrelation::AjocDecorrelation;
use super::reconstruction::{QmfPlanes, QmfSlot, Reconstructor};
use crate::error::{Result, invalid};
use crate::qmf::QmfSynthesis;

#[derive(Default)]
pub(crate) struct ObjectDecoder {
    matrix: Reconstructor,
    decorrelation: AjocDecorrelation,
    qmf: QmfPlanes,
    history: Vec<[f32; 1280]>,
}

impl ObjectDecoder {
    pub(crate) fn process(
        &mut self,
        synthesis: &QmfSynthesis,
        metadata: &AjocMetadata,
        core: &[Vec<QmfSlot>],
        lfe: Option<&[f32]>,
        output: &mut Vec<Vec<f32>>,
    ) -> Result<()> {
        self.matrix
            .process_into(metadata, core, &mut self.decorrelation, &mut self.qmf)?;
        let objects = self.qmf.len();
        let first = usize::from(lfe.is_some());
        let samples = core[0].len() * 64;
        if lfe.is_some_and(|plane| plane.len() != samples || plane.iter().any(|v| !v.is_finite())) {
            return Err(invalid("A-JOC LFE plane"));
        }
        self.history.resize(objects, [0.0; 1280]);
        output.resize_with(objects + first, Vec::new);
        for plane in output.iter_mut() {
            plane.resize(samples, 0.0);
        }
        if let Some(lfe) = lfe {
            output[0].copy_from_slice(lfe);
        }
        for (object, plane) in self.qmf.iter().enumerate() {
            for (ts, slot) in plane.iter().enumerate() {
                let real = std::array::from_fn(|sb| slot[sb][0]);
                let imaginary = std::array::from_fn(|sb| slot[sb][1]);
                let mut pcm = [0.0; 64];
                synthesis.synthesize_slot(&mut self.history[object], &real, &imaginary, &mut pcm);
                if pcm.iter().any(|v| !v.is_finite()) {
                    return Err(invalid("non-finite A-JOC object PCM"));
                }
                output[first + object][ts * 64..(ts + 1) * 64].copy_from_slice(&pcm);
            }
        }
        Ok(())
    }
}
