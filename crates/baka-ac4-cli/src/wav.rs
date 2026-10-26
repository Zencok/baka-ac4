//! Minimal WAV writer (s16 PCM or f32, seekable output).
//!
//! The header is written as a placeholder up front and patched in `finish`,
//! so the channel count and sample rate can be filled in from the first
//! decoded frame.

use std::io::{self, Seek, SeekFrom, Write};

pub struct WavWriter<W: Write + Seek> {
    out: W,
    channels: u16,
    sample_rate: u32,
    /// true = 32-bit float samples, false = 16-bit PCM (default).
    float: bool,
    data_bytes: u64,
    /// Reused interleaving buffer.
    buf: Vec<u8>,
}

impl<W: Write + Seek> WavWriter<W> {
    pub fn start_fmt(mut out: W, float: bool) -> io::Result<Self> {
        out.write_all(&[0u8; 44])?;
        Ok(WavWriter {
            out,
            channels: 0,
            sample_rate: 0,
            float,
            data_bytes: 0,
            buf: Vec::new(),
        })
    }

    /// Sets the format reported by the first decoded frame.
    pub fn set_format(&mut self, channels: u16, sample_rate: u32) {
        self.channels = channels;
        self.sample_rate = sample_rate;
    }

    /// Writes one planar f32 frame as interleaved samples (s16le or f32le
    /// per the configured format). The format is captured from the first
    /// frame.
    pub fn write_frame_planar(&mut self, chans: &[Vec<f32>], sample_rate: u32) -> io::Result<()> {
        if self.channels == 0 {
            self.set_format(chans.len() as u16, sample_rate);
        }
        let n = chans.first().map(|c| c.len()).unwrap_or(0);
        let ch = self.channels as usize;
        let bps = if self.float { 4 } else { 2 };
        self.buf.clear();
        self.buf.reserve(n * ch * bps);
        for i in 0..n {
            for c in chans {
                let v = c.get(i).copied().unwrap_or(0.0);
                if self.float {
                    self.buf.extend_from_slice(&v.to_le_bytes());
                } else {
                    let s = (v * 32768.0).round().clamp(-32768.0, 32767.0) as i16;
                    self.buf.extend_from_slice(&s.to_le_bytes());
                }
            }
        }
        self.out.write_all(&self.buf)?;
        self.data_bytes += self.buf.len() as u64;
        Ok(())
    }

    /// Seeks back and writes the full 44-byte header with final sizes.
    pub fn finish(mut self) -> io::Result<()> {
        let channels = self.channels.max(1);
        let rate = self.sample_rate.max(1);
        let data = self.data_bytes.min(u32::MAX as u64) as u32;
        let riff = (36 + self.data_bytes).min(u32::MAX as u64) as u32;
        let bps = if self.float { 4 } else { 2 };
        let fmt_tag = if self.float { 3u16 } else { 1u16 }; // IEEE float / PCM
        let byte_rate = rate * channels as u32 * bps as u32;
        let mut hdr = Vec::with_capacity(44);
        hdr.extend_from_slice(b"RIFF");
        hdr.extend_from_slice(&riff.to_le_bytes());
        hdr.extend_from_slice(b"WAVE");
        hdr.extend_from_slice(b"fmt ");
        hdr.extend_from_slice(&16u32.to_le_bytes());
        hdr.extend_from_slice(&fmt_tag.to_le_bytes());
        hdr.extend_from_slice(&channels.to_le_bytes());
        hdr.extend_from_slice(&rate.to_le_bytes());
        hdr.extend_from_slice(&byte_rate.to_le_bytes());
        hdr.extend_from_slice(&(channels * bps as u16).to_le_bytes()); // block align
        hdr.extend_from_slice(&((bps * 8) as u16).to_le_bytes()); // bits per sample
        hdr.extend_from_slice(b"data");
        hdr.extend_from_slice(&data.to_le_bytes());
        self.out.seek(SeekFrom::Start(0))?;
        self.out.write_all(&hdr)?;
        self.out.flush()?;
        Ok(())
    }
}
