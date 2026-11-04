//! Guarded maintenance contracts for Mesa firmware and automatic axis configuration.
//! This module owns controller quiescence; independent writers own device/config I/O.
use super::{broker, install, system::PausedLauncher, Event, Result};
use std::fs::File;
use std::io::{Read, Write};
use std::os::fd::{AsRawFd, FromRawFd, RawFd};
use std::os::unix::net::UnixStream;
use std::os::unix::process::CommandExt;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::Duration;

const FLASH: &str = "/usr/bin/betterlinuxcnc-mesa-flash";
const PROTOCOL: &str = "betterlinuxcnc-mesa-maintenance-v1";

//--------//
// BEGIN: AxisProfileMaintenance
pub(super) fn run_axes(axes: u8) -> Result<()> {
    if !cfg!(target_os = "linux")
        || unsafe { libc::getuid() } != 0
        || unsafe { libc::geteuid() } != 0
        || !(3..=5).contains(&axes)
    {
        return Err("Axis profile switching requires the fixed root service".into());
    }
    const APPLIANCE: &str = "/usr/sbin/betterlinuxcnc-appliance";
    let store = broker::root_store()?;
    let lock = store.lock()?;
    let (manager, socket, uid) = broker::machine_context()?;
    install::preflight(&socket, &manager, uid)?;
    let count = axes.to_string();
    let prepared = super::command(APPLIANCE)
        .args(["axis-profile", "prepare-system", &count])
        .stdin(Stdio::null())
        .output()?;
    if !prepared.status.success() || prepared.stdout.len() > 4096 {
        return Err(
            "Axis parameters are incomplete or unsupported; controller was not stopped".into(),
        );
    }
    let prepared: serde_json::Value = serde_json::from_slice(&prepared.stdout)?;
    let revision = prepared["revision"]
        .as_str()
        .filter(|value| value.len() == 64 && value.bytes().all(|b| b.is_ascii_hexdigit()))
        .ok_or("Invalid profile revision")?;
    let original = install::preflight(&socket, &manager, uid)?;
    let launcher = PausedLauncher::stop(manager, original)?;
    let result: Result<()> = (|| {
        if install::present(&socket)? || install::present(Path::new("/tmp/linuxcnc.lock"))? {
            return Err("Control has not stopped; profile switch refused".into());
        }
        let descriptor = duplicate(lock.as_raw_fd())?;
        let raw = descriptor.as_raw_fd();
        let mut apply = super::command(APPLIANCE);
        // The independent profile writer holds the same update lock through its
        // own configuration lease, stopped checks, backup and atomic write.
        unsafe {
            apply.pre_exec(move || {
                if libc::dup2(raw, 4) < 0 {
                    return Err(std::io::Error::last_os_error());
                }
                Ok(())
            });
        }
        let status = apply
            .args(["axis-profile", "apply-system", &count, revision])
            .stdin(Stdio::null())
            .status()?;
        if !status.success() {
            return Err("Profile switch did not complete; control remains stopped".into());
        }
        Ok(())
    })();
    if let Err(error) = result {
        launcher.retain_stop_mask();
        return Err(error);
    }
    // Resume only a previously running launcher. Actual axis feedback is still
    // required before the UI can report that the selected profile is active.
    launcher.resume()
}
// END: AxisProfileMaintenance
//--------//

//--------//
// BEGIN: LocalPackageMaintenance
pub(super) fn install_local() -> Result<()> {
    if !cfg!(target_os = "linux")
        || unsafe { libc::getuid() } != 0
        || unsafe { libc::geteuid() } != 0
    {
        return Err("Local package maintenance requires the fixed root service".into());
    }
    let store = broker::root_store()?;
    let _lock = store.lock()?;
    let (manager, socket, uid) = broker::machine_context()?;
    install::preflight(&socket, &manager, uid)?;
    let prepared = betterlinuxcnc_local_update::PreparedLocalPackage::receive(
        std::io::stdin(),
        &store.directory,
    )?;
    super::package::validate(prepared.path())?;
    let version = prepared.version().to_owned();
    let original = install::preflight(&socket, &manager, uid)?;
    let launcher = PausedLauncher::stop(manager, original)?;
    let result = (|| -> Result<()> {
        if install::present(&socket)? || install::present(Path::new("/tmp/linuxcnc.lock"))? {
            return Err("Control has not stopped; local installation refused".into());
        }
        if !super::command("/usr/sbin/betterlinuxcnc-appliance")
            .arg("backup")
            .stdin(Stdio::null())
            .status()?
            .success()
        {
            return Err("Backup failed; local package was not installed".into());
        }
        if install::present(&socket)? || install::present(Path::new("/tmp/linuxcnc.lock"))? {
            return Err("Control returned after backup; local installation refused".into());
        }
        prepared.install_after_backup()
    })();
    if let Err(error) = result {
        launcher.retain_stop_mask();
        return Err(error);
    }
    launcher.resume()?;
    store.publish(&Event::new(
        "complete",
        "自编译包已安装，版本号保持不变",
        &version,
        100,
    ))
}
// END: LocalPackageMaintenance
//--------//

pub(super) fn run() -> Result<()> {
    if !cfg!(target_os = "linux")
        || unsafe { libc::getuid() } != 0
        || unsafe { libc::geteuid() } != 0
    {
        return Err("Mesa maintenance requires the fixed root service".into());
    }
    let store = broker::root_store()?;
    let lock = store.lock()?; // The same lock excludes Debian installation.
    let (manager, socket, uid) = broker::machine_context()?;
    install::preflight(&socket, &manager, uid)?;
    // Missing/unverified firmware fails before stopping a working controller.
    let prepared = super::command(FLASH)
        .arg("prepare-system")
        .stdin(Stdio::null())
        .status()?;
    if !prepared.success() {
        return Err(
            "No independently verified Mesa firmware is ready; controller was not stopped".into(),
        );
    }
    let original = install::preflight(&socket, &manager, uid)?;
    let launcher = PausedLauncher::stop(manager, original)?;
    // Once stopping has succeeded, neither failure nor success may restart it.
    launcher.retain_stop_mask();
    let stopped = || {
        if install::present(&socket)? || install::present(Path::new("/tmp/linuxcnc.lock"))? {
            return Err(
                "Control socket or native core lock still exists; Mesa access refused".into(),
            );
        }
        Ok(())
    };
    stopped()?;
    let version = super::storage::installed_version("0")?;
    let result = backed_up_write(
        &lock,
        &version,
        stopped,
        &mut super::command("/usr/sbin/betterlinuxcnc-appliance"),
        &mut super::command(FLASH),
    );
    if let Err(error) = &result {
        let _ = store.publish(&Event::new("error", error.to_string(), &version, 0));
    }
    result
}

fn backed_up_write(
    lock: &File,
    version: &str,
    stopped: impl Fn() -> Result<()>,
    backup: &mut Command,
    writer: &mut Command,
) -> Result<()> {
    if !backup
        .arg("backup")
        .stdin(Stdio::null())
        .status()?
        .success()
    {
        return Err("Pre-flash recovery backup failed; control remains stopped".into());
    }
    stopped()?;
    guarded_writer(lock, version, stopped, writer)
}

fn duplicate(fd: RawFd) -> Result<File> {
    // Reserve sources above the two fixed inherited descriptors before fork.
    let copy = unsafe { libc::fcntl(fd, libc::F_DUPFD_CLOEXEC, 10) };
    if copy < 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    Ok(unsafe { File::from_raw_fd(copy) })
}

fn guarded_writer(
    lock: &File,
    version: &str,
    stopped: impl Fn() -> Result<()>,
    writer: &mut Command,
) -> Result<()> {
    let (mut parent, child) = UnixStream::pair()?;
    parent.set_read_timeout(Some(Duration::from_secs(600)))?;
    parent.set_write_timeout(Some(Duration::from_secs(10)))?;
    let channel_fd = duplicate(child.as_raw_fd())?;
    let lock_fd = duplicate(lock.as_raw_fd())?;
    let channel_raw = channel_fd.as_raw_fd();
    let lock_raw = lock_fd.as_raw_fd();
    unsafe {
        writer.pre_exec(move || {
            if libc::dup2(channel_raw, 3) < 0 || libc::dup2(lock_raw, 4) < 0 {
                return Err(std::io::Error::last_os_error());
            }
            Ok(())
        });
    }
    let mut process = writer.arg("write-system").stdin(Stdio::null()).spawn()?;
    drop(child);
    drop(channel_fd);
    drop(lock_fd);
    let result = exchange(&mut parent, version, stopped);
    // Closing the channel denies any subsequent hardware operation. Never kill
    // an in-progress flash write; wait while the inherited lock stays held.
    drop(parent);
    let status = process.wait()?;
    result?;
    if !status.success() {
        return Err("Mesa write or readback failed; control remains stopped".into());
    }
    Ok(())
}

fn exchange(
    stream: &mut UnixStream,
    version: &str,
    stopped: impl Fn() -> Result<()>,
) -> Result<()> {
    let challenge = uuid::Uuid::new_v4().to_string();
    let request = serde_json::json!({"protocol":PROTOCOL,"challenge":challenge,"version":version});
    writeln!(stream, "{request}")?;
    if read_line(stream)? != format!("ready {challenge}") {
        return Err("Mesa maintenance handshake failed".into());
    }
    for step in ["probe", "write", "verify", "complete"] {
        if read_line(stream)? != format!("{step} {challenge}") {
            return Err("Mesa maintenance steps are missing or out of order".into());
        }
        stopped()?;
        writeln!(stream, "continue {challenge}")?;
    }
    Ok(())
}

fn read_line(stream: &mut UnixStream) -> Result<String> {
    let mut line = Vec::new();
    for _ in 0..512 {
        let mut byte = [0];
        stream.read_exact(&mut byte)?;
        if byte[0] == b'\n' {
            return Ok(String::from_utf8(line)?);
        }
        line.push(byte[0]);
    }
    Err("Mesa maintenance message exceeds limit".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;
    use std::os::unix::fs::PermissionsExt;

    #[test]
    fn every_hardware_step_requires_a_live_stopped_guard() {
        for denied_step in [None, Some(0), Some(1), Some(2), Some(3)] {
            let (mut guard, mut child) = UnixStream::pair().unwrap();
            let reader = std::thread::spawn(move || {
                let initial: serde_json::Value =
                    serde_json::from_str(&read_line(&mut child).unwrap()).unwrap();
                let challenge = initial["challenge"].as_str().unwrap();
                assert_eq!(initial["protocol"], PROTOCOL);
                writeln!(child, "ready {challenge}").unwrap();
                for (index, step) in ["probe", "write", "verify", "complete"].iter().enumerate() {
                    writeln!(child, "{step} {challenge}").unwrap();
                    let answer = read_line(&mut child);
                    if denied_step == Some(index) {
                        assert!(answer.is_err());
                        return;
                    }
                    assert_eq!(answer.unwrap(), format!("continue {challenge}"));
                }
            });
            let index = Cell::new(0);
            let result = exchange(&mut guard, "26.10.26.1", || {
                let current = index.get();
                index.set(current + 1);
                if denied_step == Some(current) {
                    Err("core lock returned".into())
                } else {
                    Ok(())
                }
            });
            assert_eq!(result.is_ok(), denied_step.is_none());
            drop(guard);
            reader.join().unwrap();
        }
    }

    #[test]
    fn failed_backup_never_spawns_the_writer() {
        let directory = tempfile::tempdir().unwrap();
        let backup = directory.path().join("backup");
        std::fs::write(&backup, "#!/bin/sh\nexit 1\n").unwrap();
        std::fs::set_permissions(&backup, std::fs::Permissions::from_mode(0o700)).unwrap();
        let lock = tempfile::tempfile().unwrap();
        assert!(backed_up_write(
            &lock,
            "26.10.26.1",
            || Ok(()),
            &mut Command::new(backup),
            &mut Command::new("/never-executed-writer")
        )
        .is_err());
    }

    #[test]
    fn real_child_receives_the_same_locked_description_and_actual_exit_is_checked() {
        let directory = tempfile::tempdir().unwrap();
        let lock_path = directory.path().join("maintenance.lock");
        let lock = std::fs::OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .open(&lock_path)
            .unwrap();
        assert_eq!(
            unsafe { libc::flock(lock.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) },
            0
        );
        for exit_status in [0, 7] {
            let fixture = directory.path().join("writer.py");
            let path_literal = serde_json::to_string(lock_path.to_str().unwrap()).unwrap();
            let script = format!(
                r#"#!/usr/bin/python3
import fcntl, json, os, socket, sys
assert sys.argv[1:] == ['write-system']
assert os.fstat(4).st_ino == os.stat({path_literal}).st_ino
with open({path_literal}) as other:
    try:
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        pass
    else:
        raise AssertionError('maintenance mutex was lost')
stream = socket.socket(fileno=3).makefile('rwb', buffering=0)
request = json.loads(stream.readline())
assert request['protocol'] == 'betterlinuxcnc-mesa-maintenance-v1'
assert request['version'] == '26.10.26.1'
challenge = request['challenge']
stream.write(('ready ' + challenge + '\n').encode())
for step in ['probe', 'write', 'verify', 'complete']:
    stream.write((step + ' ' + challenge + '\n').encode())
    assert stream.readline().decode().strip() == 'continue ' + challenge
sys.exit({exit_status})
"#
            );
            std::fs::write(&fixture, script).unwrap();
            std::fs::set_permissions(&fixture, std::fs::Permissions::from_mode(0o700)).unwrap();
            let checks = Cell::new(0);
            let result = guarded_writer(
                &lock,
                "26.10.26.1",
                || {
                    checks.set(checks.get() + 1);
                    Ok(())
                },
                &mut Command::new(&fixture),
            );
            assert_eq!(result.is_ok(), exit_status == 0);
            assert_eq!(checks.get(), 4);
        }
    }
}
