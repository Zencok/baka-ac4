use std::process::Command;

fn bench(rounds: &str) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_baka-ac4"))
        .args([
            "bench",
            "tests/fixtures/p83_iframe_plus5.ac4",
            rounds,
        ])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .output()
        .unwrap()
}

#[test]
fn invalid_rounds_fail_without_panicking() {
    for value in ["0", "-1", "invalid", "10001"] {
        let output = bench(value);
        assert!(!output.status.success());
        assert!(String::from_utf8_lossy(&output.stderr).contains("rounds must be"));
    }
}

#[test]
fn multiple_rounds_retain_peak() {
    let output = bench("2");
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(String::from_utf8_lossy(&output.stdout).contains("peak=0.2019"));
}
