# FFT workspace review (2026-10-26)

The QMF analysis, QMF synthesis and IMDCT contexts previously retained their
transform buffers but called RustFFT's `Fft::process`. RustFFT 6.4.1 constructs
a scratch Vec in that convenience method. An empty scratch requirement need
not allocate, so the number of actual allocations depends on the selected plan.

Each context now allocates transform data plus `get_inplace_scratch_len()`
elements at construction, splits that buffer during execution and calls
`process_with_scratch`. The FFT plans, twiddles, floating-point operation order,
QMF default and public APIs are unchanged. Scratch memory remains resident for
the lifetime of the context; this trades retained memory for avoiding repeated
allocation. Decoder startup and memory still require mobile-device measurement.

`tests/transform_allocations.rs` counts alloc, alloc_zeroed and realloc on the
calling thread, starting with the first transform call. It covers both QMF
directions and every unique length in `TRANSF_LENGTH_48KHZ`. The assertion is
about these transforms, not allocation freedom of every decoder path.

## Validation

- `cargo test --release`: 18 core unit tests, decoder and demuxer robustness
  tests, and two new allocation tests pass. Decoder fuzzing uses its default
  20,000 iterations per phase.
- `cargo clippy --release --all-targets -- -D warnings`: passes.
- `rustfmt --edition 2024 --check` on the two changed source files and new
  test passes. Workspace-wide formatting already has differences in unrelated
  files; they were not reformatted for this change.
- Full CM_SIMPLE stereo MP4: 5,852 frames decoded, zero waiting/errors; before
  and after f32 WAV SHA-256 is
  `1cb9795e8ae8a6a3d6ac704437305c13e3c4bcdc482eac269ebbece07e2a00a0`.
- Embedded p83 A-SPX fixture: seven frames, zero waiting/errors; identical
  before/after SHA-256
  `8548506ed8212c0ceda9469c8ad6b0721e52690b638efb17b6309d1a9cf82395`.
- Embedded ATSC3 5.1/v2/balance A-SPX fixture: seven frames, zero waiting/errors;
  identical before/after SHA-256
  `022894c81819e63c2d24922be5d8816a34ed5d0002d1bf41bd722f21ad471a15`.

This compares the pre-change decoder with the optimized decoder. It does not
repeat historical independent-decoder SNR checks or establish full profile
coverage. No Android/iOS device measurements were performed.

On the full stereo sample, four alternating old/new pairs (five rounds each,
median of per-run minima) measured 0.649 s before and 0.565 s after, a 12.9%
reduction in decode time. The individual min pairs in seconds were
0.643/0.562, 0.655/0.546, 0.661/0.576 and 0.597/0.568. These are Windows host
measurements, not a mobile-device performance claim. Host: Intel Core
i9-13900HX, rustc/cargo 1.93.1, default repository release profile, without
adding `target-cpu=native`.

Use release builds with identical compiler flags, `baka-ac4 bench input.mp4 5`,
and alternate old/new execution order over several pairs. Verify each sample
separately with `decode --f32`: the existing benchmark suppresses frame errors,
accepts zero rounds and reports an incorrect peak after multiple rounds.
Those benchmark issues describe the original baseline and were fixed by the
follow-up below.

## Follow-up: playback startup and long VLC codes

Immutable VLC tables, KBD windows and the quantization lookup now initialize
once through `OnceLock`. They remain resident after the first decoder is used;
they are not initialized merely by loading the library. Each decoder still owns
its FFT scratch buffers and complete inter-frame state. IMDCT construction now
shares one local FFT planner across transform sizes and no longer constructs
40 placeholder transforms only to discard them.

Long VLC codebooks now use a compact binary trie instead of scanning the entire
codebook after every input bit. Invalid prefixes still consume the original
maximum number of bits, preserving error-recovery behavior. A differential unit
test covers all lengths 1..24, signed symbols, invalid prefixes and 10,000
deterministic random inputs, including consumed bit counts.

`bench` rejects invalid/zero/excessive rounds, fails on decode errors or zero
decoded frames, and preserves its first-round peak. Two CLI tests cover round
validation and multi-round peak reporting. `cargo run --release -p baka-ac4-core
--example startup_bench` measures first construction and 100 subsequent
construct/drop operations.

On the same Windows host/toolchain, three old/new process pairs measured warm
construction medians of 2823/187, 2617/191 and 2738/188 microseconds (median:
2738 -> 188 us, about 93% lower). Cold times were 3280/2476, 3340/2338 and
3403/2436 us (median: 3340 -> 2436 us). Repeated construction benefits most;
the first call still builds shared immutable data.

Steady-state decode timings were noisy: stereo per-run minima were
0.522/0.519, 0.503/0.519 and 0.553/0.514 seconds. A 3500-frame input made by
repeating the embedded p83 fixture measured 0.383/0.366, 0.399/0.423 and
0.361/0.351 seconds. No stable additional throughput improvement is claimed.
Both full stereo and the embedded p83/ATSC3 fixtures retain the SHA-256 values
above; the repeated p83 input also remains bit-identical with zero errors.

Validation: 19 core tests, two CLI benchmark tests, both robustness tests and
both transform-allocation tests pass under `cargo test --release`;
`cargo clippy --release --all-targets -- -D warnings` passes. No mobile-device
performance claim is made. Stop numerical changes here until on-device
profiling justifies further work; preserve full QMF precision for integration.

## Integration boundary

Keep this crate independent of app networking and Flutter. BakaMusic should
prefer the actual platform decoder and instantiate this decoder only for an
unsupported format or one controlled fallback after a confirmed decoding
failure. The application can import the core into its Rust workspace while
retaining this repository as the algorithm upstream, CLI and regression suite.

Stateful seek, bounded buffering, cancellation, PCM channel order and exact
sample trimming belong in the application's Rust playback adapter. The CLI's
whole-file input loading is not a streaming integration layer.
