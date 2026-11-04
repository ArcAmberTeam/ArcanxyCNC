use serde_json::{json, Value};
use std::{
    fs,
    process::{Command, Output},
};

fn invoke(directory: &std::path::Path, arguments: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_betterlinuxcnc-updater"))
        .env("XDG_CACHE_HOME", directory)
        .args(arguments)
        .output()
        .unwrap()
}

#[test]
fn status_survives_gui_restart_without_network_or_controller() {
    let directory = tempfile::tempdir().unwrap();
    let output = invoke(directory.path(), &["status"]);
    assert!(output.status.success());
    let state: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(state["phase"], "idle");
    let record =
        json!({"phase":"complete","message":"已更新至 0.3.0","version":"0.3.0","progress":100});
    fs::write(
        directory.path().join("betterlinuxcnc/update/status.json"),
        record.to_string(),
    )
    .unwrap();
    let output = invoke(directory.path(), &["status"]);
    assert!(output.status.success());
    let mut expected = record;
    expected["self_compiled"] = json!(false);
    assert_eq!(
        serde_json::from_slice::<Value>(&output.stdout).unwrap(),
        expected
    );
}

#[test]
fn interrupted_download_is_retryable_not_permanently_busy() {
    let directory = tempfile::tempdir().unwrap();
    invoke(directory.path(), &["status"]);
    fs::write(
        directory.path().join("betterlinuxcnc/update/status.json"),
        json!({"phase":"downloading","message":"downloading","progress":25}).to_string(),
    )
    .unwrap();
    let output = invoke(directory.path(), &["status"]);
    assert!(output.status.success());
    let state: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(state["phase"], "error");
    assert!(state["message"].as_str().unwrap().contains("中断"));
}

#[test]
fn missing_payload_never_schedules_installation() {
    let directory = tempfile::tempdir().unwrap();
    let output = invoke(directory.path(), &["install"]);
    assert!(!output.status.success());
    let state: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(state["phase"], "error");
    assert_ne!(state["phase"], "scheduled");
    assert!(!directory
        .path()
        .join("betterlinuxcnc/update/install.log")
        .exists());
}
