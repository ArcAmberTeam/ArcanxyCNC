//! Public executable contracts under real CI identities, without machine files.

use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::process::{Command, Output, Stdio};
use std::sync::Mutex;

static INVOCATION_LOCK: Mutex<()> = Mutex::new(());

fn invoke(arguments: &[&str], input: &[u8], account: Option<&str>) -> Output {
    // A concurrent fork can inherit another test's writable executable descriptor.
    // Serialize staging and child lifetimes to prevent transient ETXTBSY failures.
    let _invocation = INVOCATION_LOCK.lock().unwrap();
    // Hosted checkouts may have private ancestors; expose only this built executable.
    let directory = tempfile::tempdir_in("/tmp").unwrap();
    std::fs::set_permissions(directory.path(), std::fs::Permissions::from_mode(0o755)).unwrap();
    let binary = directory.path().join("pa");
    std::fs::copy(env!("CARGO_BIN_EXE_pa"), &binary).unwrap();
    std::fs::set_permissions(&binary, std::fs::Permissions::from_mode(0o755)).unwrap();
    let mut command = if let Some(account) = account {
        let mut command = Command::new("sudo");
        command.args(["-n", "-u", account, "--"]).arg(&binary);
        command
    } else {
        Command::new(binary)
    };
    let mut child = command
        .args(arguments)
        .env("USER", "cnc-maint")
        .env("LOGNAME", "cnc-maint")
        .env("SSH_CONNECTION", "untrusted")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child.stdin.take().unwrap().write_all(input).unwrap();
    child.wait_with_output().unwrap()
}

#[test]
fn rejects_other_accounts_and_root_despite_spoofed_environment() {
    for account in [None, Some("root")] {
        let result = invoke(&["manage", "ini"], b"", account);
        assert_eq!(result.status.code(), Some(77));
        assert!(result.stdout.is_empty());
    }
}

#[test]
fn maintenance_account_enters_each_target_and_closes_on_exit_or_eof() {
    for (target, title) in [
        ("ini", "Machine INI configuration"),
        ("launcher.json", "Launcher configuration"),
    ] {
        for input in [b"help\nexit\n".as_slice(), b"".as_slice()] {
            let result = invoke(&["manage", target], input, Some("cnc-maint"));
            assert!(result.status.success(), "{:?}", result);
            let text = String::from_utf8(result.stdout).unwrap();
            assert!(text.contains(title));
            assert!(text.contains("interactive terminal"));
        }
    }
}

#[test]
fn rejects_unknown_verbs_targets_paths_extra_arguments_and_shell_syntax() {
    for arguments in [
        vec!["manage"],
        vec!["manage", "../ini"],
        vec!["manage", "/etc/shadow"],
        vec!["manage", "launcher.json", "extra"],
        vec!["manage", "ini;id"],
        vec!["manage", "$(id)"],
        vec!["execute", "ini"],
        vec!["manage", "sudo"],
        vec!["manage", "sudo", "open", "extra"],
        vec!["manage", "sudo", "close"],
    ] {
        let result = invoke(&arguments, b"", Some("cnc-maint"));
        assert_eq!(result.status.code(), Some(64), "{:?}", result);
        assert!(result.stdout.is_empty());
    }
}

#[test]
fn help_lists_registered_targets_and_session_does_not_execute_input() {
    let result = invoke(&["--help"], b"", Some("cnc-maint"));
    assert!(result.status.success());
    let text = String::from_utf8(result.stdout).unwrap();
    assert!(text.contains("manage ini"));
    assert!(text.contains("manage launcher.json"));
    assert!(text.contains("manage sudo open"));
    let result = invoke(&["manage", "ini"], b"id\nexit\n", Some("cnc-maint"));
    assert!(result.status.success());
    let text = String::from_utf8(result.stdout).unwrap();
    assert!(text.contains("Unknown command"));
    assert!(!text.contains("uid="));
}

#[test]
fn oversized_terminal_input_is_bounded() {
    let result = invoke(&["manage", "ini"], &[b'x'; 5000], Some("cnc-maint"));
    assert_eq!(result.status.code(), Some(74));
    assert!(String::from_utf8(result.stderr).unwrap().contains("4096"));
}
