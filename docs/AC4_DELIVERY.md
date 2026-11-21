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
- Native reference harness: ordinary stereo control produces nonzero PCM
  (peak 0.06818). The first 48 A-JOC 1500 packets return success but produce
  silence, while Rust core planes are nonzero (peak 0.01714 on those packets).
  Therefore that backend is not a valid A-JOC numerical reference; success
  return codes alone are not accepted as decoding proof.
- Updated compatible reference library: the same 48 A-JOC 1500 packets produce
  98304 stereo samples per channel, peak 0.03873. The 448 kbit/s tier also
  passes the same 48-packet run, peak 0.03738. This establishes usable
  nonzero reference output; it does not establish Rust reconstruction parity.
  The consumed-byte ABI changed from a 32-bit to a 64-bit pointer. The runner
  accepts both and validates actual PCM rather than return codes alone.

## In progress

- Explicit core-signal API, indexed audio substream selection and variable
  channel elements implemented. Both tiers passed the optional full-song test, including finite-value and
  exact plane-length assertions, and decoded all 5025 entries in host
  release runs (1.990 s / 3.443 s; peaks 0.3866 / 0.3319). Numerical parity with
  reference core PCM is not yet established.
- Raw object-signal reconstruction is implemented in the opt-in mode described
  below; object gain/position rendering and reference parity remain in progress.
- Reconstruction-matrix inspection now passes both complete recordings,
  including shared timing, cross-frame coefficient history and exact payload
  boundary assertions; see the reconstruction-parameters section below.

## Remaining acceptance

- Interpret A-JOC dynamic object gain/position metadata; render to
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

## A-JOC reconstruction parameters

The opt-in `set_ajoc_metadata(true)` path parses the shared OAMD timing substream,
downmix/upmix object blocks, A-JOC dry/wet matrix masks and all twelve normative
Huffman codebooks. It reconstructs frequency deltas modulo the quantizer range,
time deltas against the previous data point (including across frames), sparse
zero coefficients, and fine/coarse dequantized matrix gains. The long-code VLC
path now accepts up to 32 bits; the A-JOC codebooks require up to 29.

On the two local complete recordings, all 5025 frames per tier parse to within
0–7 fill bits of the declared audio boundary. Both contain three enabled
decorrelators and up to 20 fullband objects, plus separate LFE. The 448 tier uses
12 parameter bands and exercises 505784 time-delta matrix elements; the 1500
tier uses 23 bands and exercises 668513. Tests assert these structural properties,
matrix gain bounds, exact plane meaning, and metadata invalidation on flush or
decode errors. These are bitstream consistency checks, not reference PCM parity.

The parser is bounded to 16 fullband downmix signals and 64 fullband objects;
the existing core decoder supports at most 12 total input signals. Static/mixed
assignments and alternative presentations are explicitly rejected in inspection
mode. Object position/zone/other metadata and length-delimited extensions are
traversed, without claiming their rendering semantics. A damaged matrix payload
cannot commit partial dialogue/coefficient history. Authored tests cover exact
bit truncations, mutations, sparse resets, incompatible time history, quantizer
wrap and frequency-to-time transitions. All codebook symbols are round-tripped.

Inspection-only output remains `AjocCoreSignals`. The separate object-signal
mode below implements reconstruction. OAMD-driven rendering and comparison of
rendered PCM against the working native reference remain pending. No player
integration should advertise full A-JOC spatial playback from these milestones.

## A-JOC object-signal reconstruction

`set_ajoc_object_signals(true)` / CLI `--object-signals` now performs all eight
parameter-band mappings, cross-frame dry/wet coefficient ramps, the decorrelation
input pre-matrix, seven independent IIR/ducker histories (D0,D2,D1 cyclic
coefficients), complex QMF mixing and independent object QMF synthesis. LFE
is passed through first when present. The shared synthesis-slot helper also
serves ordinary channel decoding, retaining its accumulation order.

The implementation uses ETSI TS 103 190-1 V1.3.1 clause 5.7.7.4 tables 197–200
for the region-specific all-pass delays/coefficients and 15-band transient
ducker, and Part 2 clauses 5.7.3.1/4/5/6 for the object reconstruction pipeline.
Filter histories use f64; input/output QMF and PCM remain f32. Ramps retain
the old value in their starting slot and reach their target over the following
signalled number of slots, without overshoot; unfinished ramps cross frames.
Exact ramp/filter numerical parity with the native reference remains unverified.

Both complete local streams passed all 5025 object frames and produced 21 finite
planes (LFE + 20 fullband objects), with nonzero activity in every plane. Peaks
before OAMD gain/rendering were 2.2072082 and 1.6112839. One host release run took
7.382 s / 10.476 s for approximately 214.4 s of audio after sharing the existing
QMF transform plan. This is host evidence,
not mobile timing. Flush/replay matched the first six frames sample for sample;
the test also exercises object/core mode transitions and malformed-packet output
invalidation. The two metadata/core acceptance runs remain passing.
The LFE-first plane also matches core-mode LFE sample for sample after reset.

Output is tagged `AjocObjectSignals`, with speaker mask zero. Object gain,
position, zone/extent, trims, speaker/headphone rendering and optional dialogue
enhancement are not applied. Float WAV export preserves object peaks above 1;
integer export clips these peaks. `--object-signals` rejects `--fast` and
`--core-signals`. The default API still rejects object-coded input.

The standalone matrix engine validates bounded dimensions, timing, finite QMF
input and matrix shapes before changing history or calling a backend. Backend
errors/non-finite arithmetic clear the output and reset both matrix/backend
histories. A stream dimension change requires reset. PCM object mode forces
full QMF and resets matrix, all-pass, ducker and synthesis histories on flush.
It allocates signal/parameter storage and does not claim an allocation-free
real-time callback path. `copy_ajoc_core_qmf` is an inspection API for native DSP
consumers, with last-frame availability tracked independently of option changes.

## Validation commands

- `cargo test --release --locked`: unit, generated A-JOC, malformed input,
  history reset and transform allocation checks (52 tests passed).
- `cargo clippy --release --locked --all-targets -- -D warnings`.
- `BAKA_AC4_IMMERSIVE_DIR=<local-directory> cargo test --release --locked
  -p baka-ac4-cli --test immersive -- --ignored --nocapture`: both real A-JOC
  tiers passed all-frame finite PCM and layout assertions.
- `python tools/regression.py --skip-fuzz`: local decode baselines and SSF
  mutation differential (114.86–118.66 dB on the tested mutations). Full fuzz
  was run separately through the Cargo test command.

The authored matrix transport tests include all twelve Huffman codebooks, whose
longest code is 29 bits. The optional full-song test additionally verifies the
metadata path and its flush/error invalidation. Ordinary decoding baselines
remain byte-identical. Supplementary change/quality checks were used; the
available generic security scanner does not scan Rust, so its empty result is
not security evidence. Reader bounds, bounded dimensions and transactional
coefficient history were reviewed directly and exercised by the Rust tests.

The ten new DSP tests cover every frequency-map row, complex dry/wet mixing,
absolute-wet pre-matrices, 64-slot ramps across frames without new points,
interrupted ramps, sparse zeros, disabled/independent decorrelators, malformed
shapes, backend failures and non-finite output. All-pass impulse responses verify
the specified delay/first tap and unit energy in all three frequency regions
for D0/D1/D2. A CLI test rejects conflicting output modes before opening input.
CLI checks on the first 48 packets of both tiers produced float extensible WAV
with 21 signals, 48 kHz and a zero speaker mask; every TOC entry identified
`ajoc-object-signals`. Ordinary stream hashes and SSF mutation SNR remain at
their previous baselines.

Removed redundant homepage metadata which produced manifest warnings and made
the strict regression script reject an otherwise successful Clippy run.

## Reference runner

Export local packets with `tools/export_reference_packets.py input.mp4 packets.bin
--limit 48`. Build `tools/reference_probe.c` using an Android ARM64 NDK compiler:

```sh
clang --target=aarch64-linux-android24 -O2 -Wall -Wextra -Werror tools/reference_probe.c -ldl -o reference_probe
```

Provide compatible external libraries on the test device, then run with a bounded
host timeout and device-local paths:

```sh
LD_LIBRARY_PATH=. ./reference_probe ./reference.so packets.bin reference.s16le
```

Exit 0 means nonzero PCM was observed, 1 means a decoder error or all-zero output,
and 2 means the harness/input/ABI was unavailable or invalid. Silence alone does
not identify a codec failure; use a non-silent control from the same recording.
No external binaries, recordings, URLs or credentials are redistributed here.

Reference harness checks on Android cover both nonzero A-JOC tiers (exit 0),
ordinary stereo control (exit 0), the old all-zero A-JOC result (exit 1), and a
missing library (exit 2). Packet export was checked byte for byte against an
independent ffprobe-driven export. The output file is created exclusively so
existing input/output files cannot be overwritten by the reference runner.
