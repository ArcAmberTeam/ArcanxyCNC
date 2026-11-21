use std::process::Command;

#[test]
fn rejects_arbitrary_paths_and_commands() {
    let output = Command::new(env!("CARGO_BIN_EXE_betterlinuxcnc-system-info"))
        .args(["--json", "/etc/shadow"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(output.stdout.is_empty());
}

#[test]
#[cfg(target_os = "linux")]
fn reports_real_linux_information_through_the_public_cli() {
    let output = Command::new(env!("CARGO_BIN_EXE_betterlinuxcnc-system-info"))
        .arg("--json")
        .output()
        .unwrap();
    assert!(output.status.success());
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["schemaVersion"], 1);
    assert_eq!(
        value["kernel"],
        std::fs::read_to_string("/proc/sys/kernel/osrelease")
            .unwrap()
            .trim()
    );
    assert!(value["cpu"]["logicalCores"].as_u64().unwrap() > 0);
    assert!(value["memory"]["totalBytes"].as_u64().unwrap() > 0);
    assert!(value["gpus"].is_array() || value["gpus"].is_null());
}
