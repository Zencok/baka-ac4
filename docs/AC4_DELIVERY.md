# AC-4 delivery work

Updated: 2026-11-21

## Target

Complete the missing native decoding paths for current AC-4 music streams,
including A-JOC at 448 and 1500 kbit/s. Keep compressed source access separate
from the reusable Rust codec. Reference binary execution is a validation tool,
not a runtime dependency or distributable library.

## Baseline and completed fixes

- Ordinary 48 kHz stereo stream: 5023 frames decode successfully; measured host
  release decode time 0.539 s, peak 0.4507. This is one host run, not device timing.
- A-JOC 448: 5025 sample-table entries, seven full-band downmix signals plus LFE,
  twenty full-band reconstruction signals.
- A-JOC 1500: 5025 sample-table entries, eleven full-band downmix signals plus LFE,
  twenty full-band reconstruction signals.
- Both A-JOC downmix assignments are dynamic objects, not fixed speaker beds.
  Do not label their raw signals 7.1 or 7.1.4 based only on signal count.
- Truncated MP4 sample bounds, oversized sample table counts, extended-size boxes
  and missing track timescale fixed in f0443db. Seven CLI tests and release Clippy
  passed. The embedded MP4 fuzz seed is itself a truncated file; the tests also
  cover a completed container and command-level rejection before WAV creation.
- Native reference on Android successfully decoded the first 48 A-JOC 1500
  packets to stereo PCM. This establishes a working comparison side only.

## In progress

- Explicit core-signal API, indexed audio substream selection and variable
  channel elements implemented. Both tiers passed the optional full-song test, including finite-value and
  exact plane-length assertions, and decoded all 5025 entries in host
  release runs (1.990 s / 3.443 s; peaks 0.3866 / 0.3319). Numerical parity with
  reference core PCM is not yet established.
- Full reconstruction and metadata rendering remain in progress.

## Remaining acceptance

- Reconstruct A-JOC objects and parse their dynamic object metadata; render to
  defined speaker/headphone outputs and compare against the reference.
- Validate full-song outputs, finite samples, seek/reset history, corrupted inputs
  and dynamic layout changes. Preserve ordinary stereo and broadcast regressions.
- Complete ACPL/other multichannel gaps where actual streams expose them.
- Multichannel WAV metadata and format-change rejection implemented; retain
  zero masks for unanchored core signals.
- Verify mobile cost where available; label host/theoretical evidence accurately.

## Specification

ETSI TS 103 190-2 describes separate core and full decoding modes, variable
channel elements, A-JOC reconstruction, and object rendering. Raw downmix PCM
alone does not establish full A-JOC playback support.

https://www.etsi.org/deliver/etsi_ts/103100_103199/10319002/01.03.01_60/ts_10319002v010301p.pdf

## Quality matrix

| Selector | Payload | Nominal rate |
| --- | --- | --- |
| dolbyd004 | AC-4, legacy variant | 256 kbit/s |
| dolby | AC-4 | stream dependent |
| dolbyajoc448 | AC-4 A-JOC | 448 kbit/s |
| dolbyajoc1500 | AC-4 A-JOC | 1500 kbit/s |
| dolbyeac3 / dolbyd001 | E-AC-3 | 448 kbit/s |
| dolbyd006 / dolbyd002 | E-AC-3 | 640 kbit/s |
| dolbyd007 / dolbyd003 | E-AC-3 | 768 kbit/s |

The last three rows are different codecs and do not establish AC-4 support.
Media bytes, credentials, signed URLs and external libraries remain local.

## History reset

`flush()` now replaces all per-stream history, retaining transform plans and
output options. Before the fix, replay failed a fresh-decoder comparison at the
first frame. Regression coverage compares all six frames for stereo simple,
stereo A-SPX and 5.1 A-SPX fixtures, with QMF bypass enabled and disabled.
This establishes deterministic history isolation, not a seek latency guarantee.

## WAV output

Multichannel export uses WAVE_FORMAT_EXTENSIBLE with the original mask and
PCM/float subtype. Core signals with no speaker assignment retain a zero mask.
The writer rejects changing formats, inconsistent plane lengths, non-finite
samples, empty output and size/rate overflows before writing invalid samples.
Ordinary mono/stereo speaker output retains the previous 44-byte header.

Before/after export comparisons retain byte-identical PCM on all three local
regression streams. Stereo output files remain byte-identical. The 5.1 float
WAV hash changed only with the new header: `e7dfdb1699975db6fffc8904e8fb0a5f`
→ `00977d662f40f6079a6fba2882ba45c3`. The regression baseline is updated after
verifying its previous hash against the control executable. External inspection
recognizes the new 5.1 file as float PCM with the `5.1(side)` layout.
