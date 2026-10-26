//! FFT workspaces must be allocated at construction, not on the audio path.
use baka_ac4_core::{
    imdct::Imdct,
    qmf::{QmfAnalysis, QmfSynthesis},
};
use std::alloc::{GlobalAlloc, Layout, System};
use std::cell::Cell;

struct CountingAllocator;
thread_local! {
    static TRACK: Cell<bool> = const { Cell::new(false) };
    static ALLOCATIONS: Cell<usize> = const { Cell::new(0) };
}

fn record_allocation() {
    if TRACK.try_with(Cell::get).unwrap_or(false) {
        let _ = ALLOCATIONS.try_with(|count| count.set(count.get() + 1));
    }
}

unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        record_allocation();
        unsafe { System.alloc(layout) }
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) }
    }
    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        record_allocation();
        unsafe { System.alloc_zeroed(layout) }
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, size: usize) -> *mut u8 {
        record_allocation();
        unsafe { System.realloc(ptr, layout, size) }
    }
}

#[global_allocator]
static ALLOCATOR: CountingAllocator = CountingAllocator;

fn assert_no_allocations(run: impl FnOnce()) {
    struct StopTracking;
    impl Drop for StopTracking {
        fn drop(&mut self) {
            TRACK.set(false);
        }
    }
    ALLOCATIONS.set(0);
    TRACK.set(true);
    let guard = StopTracking;
    run();
    drop(guard);
    assert_eq!(
        ALLOCATIONS.get(),
        0,
        "transform allocated after construction"
    );
}

#[test]
fn qmf_calls_reuse_workspace_from_first_call() {
    let analysis = QmfAnalysis::new();
    let synthesis = QmfSynthesis::new();
    let input = std::array::from_fn::<_, 128, _>(|i| (i as f32 * 0.17).sin());
    let mut q0 = [0.0; 64];
    let mut q1 = [0.0; 64];
    let mut output = [0.0; 128];
    assert_no_allocations(|| {
        for _ in 0..16 {
            analysis.bands(&input, &mut q0, &mut q1);
            synthesis.filterbank(&q0, &q1, &mut output);
            std::hint::black_box(&output);
        }
    });
    assert!(output.iter().all(|x| x.is_finite()));
}

#[test]
fn imdct_calls_reuse_workspace_for_all_decoder_lengths() {
    let lengths = baka_ac4_core::tables::TRANSF_LENGTH_48KHZ;
    let mut lengths: Vec<_> = lengths.into_iter().flatten().collect();
    lengths.sort_unstable();
    lengths.dedup();
    for length in lengths {
        let length = length as usize;
        let transform = Imdct::new(length, -1.0 / length as f32);
        let input: Vec<_> = (0..length).map(|i| (i as f32 * 0.17).sin()).collect();
        let mut output = vec![0.0; 2 * length];
        assert_no_allocations(|| {
            for _ in 0..4 {
                transform.imdct(&input, &mut output);
                std::hint::black_box(&output);
            }
        });
        assert!(output.iter().all(|x| x.is_finite()));
    }
}
