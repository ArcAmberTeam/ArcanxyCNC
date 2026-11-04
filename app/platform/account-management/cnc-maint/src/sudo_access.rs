//! Password-authenticated, time-bounded sudo authorization for cnc-maint.
//! The sudo PAM stack authenticates before invoking sudo-open; no password enters Rust.

use crate::{command, enabled, fixed, trusted_parent, validate_account, Result};
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::os::fd::AsRawFd;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

const POLICY: &str = "/etc/betterlinuxcnc/cnc-maint-sudo";
const LOCK: &str = "/var/lib/betterlinuxcnc/cnc-maint-sudo.lock";
const CLOSED: &str = "# Managed temporary cnc-maint sudo authorization; closed.\n";
const PREFIX: &str = "cnc-maint ALL=(ALL:ALL) NOTAFTER=";
const SUFFIX: &str = " NOPASSWD: ALL\n";
const EXPIRE: &str = "betterlinuxcnc-cnc-maint-sudo-expire";
const RESET: &str = "betterlinuxcnc-cnc-maint-sudo-reset";
const HELPER: &str = "/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account";
const SECONDS: u64 = 15 * 60;

//--------//
// BEGIN: TemporarySudoAuthorization
fn lock() -> Result<File> {
    trusted_parent(Path::new(LOCK))?;
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .custom_flags(0x20000)
        .open(LOCK)?;
    let info = file.metadata()?;
    if !info.is_file() || info.uid() != 0 || info.nlink() != 1 || info.mode() & 0o077 != 0 {
        return Err("Invalid sudo authorization lock".into());
    }
    if unsafe { crate::flock(file.as_raw_fd(), 2 | 4) } != 0 {
        return Err("Sudo authorization operation busy".into());
    }
    Ok(file)
}

fn recognized(content: &str) -> bool {
    content == CLOSED
        || content
            .strip_prefix(PREFIX)
            .and_then(|s| s.strip_suffix(SUFFIX))
            .is_some_and(|stamp| {
                stamp.len() == 15
                    && stamp.ends_with('Z')
                    && stamp.as_bytes()[..14].iter().all(u8::is_ascii_digit)
            })
}

fn validate_policy() -> Result<()> {
    trusted_parent(Path::new(POLICY))?;
    match fs::symlink_metadata(POLICY) {
        Ok(info) => {
            if !info.is_file()
                || info.uid() != 0
                || info.nlink() != 1
                || info.mode() & 0o022 != 0
                || info.len() > 256
                || !recognized(&fs::read_to_string(POLICY)?)
            {
                return Err("Unrecognized sudo authorization policy".into());
            }
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(error) => return Err(error.into()),
    }
    Ok(())
}

fn write_policy(content: &str) -> Result<()> {
    validate_policy()?;
    if !recognized(content) {
        return Err("Invalid sudo authorization content".into());
    }
    let temporary = format!("{POLICY}.tmp-{}", std::process::id());
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o440)
        .open(&temporary)?;
    let result = (|| {
        file.set_permissions(fs::Permissions::from_mode(0o440))?;
        file.write_all(content.as_bytes())?;
        file.sync_all()?;
        fixed("/usr/sbin/visudo", &["-c", "-f", &temporary])?;
        fs::rename(&temporary, POLICY)?;
        File::open(Path::new(POLICY).parent().ok_or("Missing policy parent")?)?.sync_all()?;
        Ok(())
    })();
    let _ = fs::remove_file(&temporary);
    result
}

fn grant_until(epoch: u64) -> Result<String> {
    let result = command("/usr/bin/date")
        .args(["-u", "-d", &format!("@{epoch}"), "+%Y%m%d%H%M%SZ"])
        .output()?;
    if !result.status.success() {
        return Err("Cannot calculate sudo deadline".into());
    }
    let stamp = String::from_utf8(result.stdout)?;
    let policy = format!("{PREFIX}{}{SUFFIX}", stamp.trim());
    if !recognized(&policy) {
        return Err("Invalid sudo deadline".into());
    }
    Ok(policy)
}

pub(super) fn close() -> Result<()> {
    let _lock = lock()?;
    write_policy(CLOSED)
}

pub(super) fn open() -> Result<()> {
    validate_account()?;
    let uid = command("/usr/bin/id").args(["-u", "cnc-maint"]).output()?;
    if !uid.status.success()
        || !enabled()?
        || std::env::var("SUDO_USER").as_deref() != Ok("cnc-maint")
        || std::env::var("SUDO_UID").ok().as_deref() != Some(String::from_utf8(uid.stdout)?.trim())
    {
        return Err("Authenticated maintenance caller required".into());
    }
    let _lock = lock()?;
    // Reopening revokes the previous grant first. Failure never leaves an extended lease.
    write_policy(CLOSED)?;
    if !Path::new("/run/systemd/system").is_dir() {
        return Err("Sudo authorization requires the system timer manager".into());
    }
    fixed(
        "/usr/bin/systemctl",
        &[
            "stop",
            &format!("{EXPIRE}.timer"),
            &format!("{EXPIRE}.service"),
        ],
    )?;
    let deadline = SystemTime::now()
        .duration_since(UNIX_EPOCH)?
        .as_secs()
        .checked_add(SECONDS)
        .ok_or("Invalid sudo deadline")?;
    let policy = grant_until(deadline)?;
    // Arm monotonic cleanup before granting access. NOTAFTER independently rejects
    // new sudo requests at the wall-clock deadline even if cleanup fails.
    fixed(
        "/usr/bin/systemctl",
        &["restart", &format!("{EXPIRE}.timer")],
    )?;
    fixed(
        "/usr/bin/systemctl",
        &["is-active", "--quiet", &format!("{EXPIRE}.timer")],
    )?;
    write_policy(&policy)?;
    println!("cnc-maint sudo enabled for 15 minutes.");
    println!("Expiry denies new elevation; existing root processes and changes are not undone.");
    Ok(())
}

pub(super) fn provision() -> Result<()> {
    close()?;
    let service = format!("[Unit]\nDescription=Revoke temporary CNC maintenance sudo authorization\n[Service]\nType=oneshot\nExecStart={HELPER} sudo-close\nUser=root\nUMask=0077\nTimeoutStartSec=15\nTimeoutStopSec=3\n");
    let reset = format!("[Unit]\nDescription=Close CNC maintenance sudo authorization at boot\nBefore=ssh.service sshd.service\n[Service]\nType=oneshot\nExecStart={HELPER} sudo-close\nUser=root\nUMask=0077\n[Install]\nWantedBy=multi-user.target\n");
    let timer = format!("[Unit]\nDescription=Expire CNC maintenance sudo authorization after 15 minutes\n[Timer]\nOnActiveSec=900s\nAccuracySec=1s\nWakeSystem=yes\nUnit={EXPIRE}.service\n");
    for (name, content) in [
        (format!("{EXPIRE}.service"), service),
        (format!("{EXPIRE}.timer"), timer),
        (format!("{RESET}.service"), reset),
    ] {
        let path = format!("/usr/lib/systemd/system/{name}");
        trusted_parent(Path::new(&path))?;
        match fs::symlink_metadata(&path) {
            Ok(info) => {
                if !info.is_file()
                    || info.uid() != 0
                    || info.nlink() != 1
                    || info.mode() & 0o022 != 0
                    || fs::read_to_string(&path)? != content
                {
                    return Err("Local sudo service edits require review".into());
                }
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                let mut file = OpenOptions::new()
                    .write(true)
                    .create_new(true)
                    .mode(0o644)
                    .open(path)?;
                file.write_all(content.as_bytes())?;
                file.sync_all()?;
            }
            Err(error) => return Err(error.into()),
        }
    }
    fixed(
        "/usr/bin/systemctl",
        &["enable", &format!("{RESET}.service")],
    )?;
    Ok(())
}

// END: TemporarySudoAuthorization
//--------//

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn grant_has_a_fixed_identity_and_absolute_expiry() {
        assert_eq!(
            grant_until(0).unwrap(),
            "cnc-maint ALL=(ALL:ALL) NOTAFTER=19700101000000Z NOPASSWD: ALL\n"
        );
        assert!(recognized(CLOSED));
        for value in [
            "cnc-maint ALL=(ALL) ALL\n",
            "root ALL=(ALL:ALL) ALL\n",
            "",
            "cnc-maint ALL=(ALL:ALL) NOTAFTER=20261105000000Z NOPASSWD: ALL\nroot ALL=(ALL) ALL\n",
        ] {
            assert!(!recognized(value));
        }
    }
}
