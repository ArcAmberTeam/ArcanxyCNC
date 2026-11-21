//! Persistent, password-authenticated sudo policy for the dedicated administrator.
//! cnc_admin 账户常驻。只有管理员验证通过后才能切换 sudo，状态保存在机床上。

use crate::{command, fixed, trusted_parent, Result};
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::os::fd::AsRawFd;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::Path;
use std::process::Stdio;

pub(super) mod enrollment;

const POLICY: &str = "/etc/betterlinuxcnc/cnc-admin-sudo";
const CLOSED: &str = "# Managed cnc_admin sudo authorization; closed.\n";
const OPEN: &str = "Defaults:cnc_admin timestamp_timeout=0\ncnc_admin ALL=(ALL:ALL) PASSWD: ALL\n";
const PAM: &str = "/etc/pam.d/betterlinuxcnc-admin";
const PAM_STACK: &str = "auth required pam_unix.so\naccount required pam_unix.so\n";

// Use the same lock as the previous implementation during package upgrades.
const LOCK: &str = "/var/lib/betterlinuxcnc/cnc-maint-sudo.lock";
const OLD_POLICY: &str = "/etc/betterlinuxcnc/cnc-maint-sudo";
const OLD_CLOSED: &str = "# Managed temporary cnc-maint sudo authorization; closed.\n";
const EXPIRE: &str = "betterlinuxcnc-cnc-maint-sudo-expire";
const RESET: &str = "betterlinuxcnc-cnc-maint-sudo-reset";
const HELPER: &str = "/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account";

//--------//
// BEGIN: AdminSudoAuthorization
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
    // LOCK_EX | LOCK_NB: callers keep the file open until their policy update finishes.
    // 申请非阻塞独占锁。开通和撤销共用这把锁，调用方持有文件句柄直到操作结束。
    if unsafe { crate::flock(file.as_raw_fd(), 2 | 4) } != 0 {
        return Err("Sudo authorization operation busy".into());
    }
    Ok(file)
}

fn managed_file(path: &str) -> Result<Option<String>> {
    trusted_parent(Path::new(path))?;
    match fs::symlink_metadata(path) {
        Ok(info)
            if info.is_file()
                && info.uid() == 0
                && info.nlink() == 1
                && info.mode() & 0o022 == 0
                && info.len() <= 4096 =>
        {
            Ok(Some(fs::read_to_string(path)?))
        }
        Ok(_) => Err("Untrusted authorization file".into()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(error.into()),
    }
}

fn policy_state() -> Result<Option<bool>> {
    match managed_file(POLICY)?.as_deref() {
        Some(OPEN) => Ok(Some(true)),
        Some(CLOSED) => Ok(Some(false)),
        None => Ok(None),
        _ => Err("Unrecognized admin sudo policy".into()),
    }
}

// Write and validate the complete file before publishing it by rename.
// 先在同一目录写好临时文件并校验，再原子替换，使后续 sudo 请求立即使用新规则。
fn replace_file(path: &str, content: &str, mode: u32) -> Result<()> {
    let temporary = format!("{path}.tmp-{}", std::process::id());
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(mode)
        .open(&temporary)?;
    let result = (|| {
        file.set_permissions(fs::Permissions::from_mode(mode))?;
        file.write_all(content.as_bytes())?;
        file.sync_all()?;
        if path == POLICY || path == OLD_POLICY {
            fixed("/usr/sbin/visudo", &["-c", "-f", &temporary])?;
        }
        fs::rename(&temporary, path)?;
        File::open(Path::new(path).parent().ok_or("Missing policy parent")?)?.sync_all()?;
        Ok(())
    })();
    let _ = fs::remove_file(&temporary);
    result
}

fn authenticate(password: &str) -> Result<()> {
    crate::validate_identity("cnc_admin", "/var/lib/betterlinuxcnc/admin")?;
    if managed_file(PAM)?.as_deref() != Some(PAM_STACK) {
        return Err("Admin authentication policy unavailable".into());
    }
    let mut pam = command("/usr/bin/pamtester")
        .args([
            "betterlinuxcnc-admin",
            "cnc_admin",
            "authenticate(PAM_DISALLOW_NULL_AUTHTOK)",
            "acct_mgmt",
        ])
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .spawn()?;
    let mut input = pam.stdin.take().ok_or("Missing authentication pipe")?;
    let written = writeln!(input, "{password}");
    drop(input);
    let status = pam.wait()?;
    written?;
    if !status.success() {
        return Err("Admin authentication rejected".into());
    }
    Ok(())
}

fn active_policy() -> Result<bool> {
    let enabled = policy_state()?.ok_or("Admin sudo policy is not installed")?;
    let include = format!("@include {POLICY}");
    if !fs::read_to_string("/etc/sudoers")?
        .lines()
        .any(|line| line.trim() == include)
    {
        return Err("Appliance sudo policy is not active".into());
    }
    Ok(enabled)
}

pub(super) fn request(desired: Option<bool>, password: &str) -> Result<bool> {
    let _guard = lock()?;
    let enabled = active_policy()?;
    if let Some(desired) = desired {
        // Authenticate every change, including retries and requests to turn sudo off.
        // 开关两种操作都校验 cnc_admin 的密码，重复请求同样需要验证。
        authenticate(password)?;
        enrollment::finish()?;
        if desired != enabled {
            replace_file(POLICY, if desired { OPEN } else { CLOSED }, 0o440)?;
        }
        return Ok(desired);
    }
    Ok(enabled)
}

fn old_grant(content: &str) -> bool {
    content
        .strip_prefix("cnc-maint ALL=(ALL:ALL) NOTAFTER=")
        .and_then(|s| s.strip_suffix(" NOPASSWD: ALL\n"))
        .is_some_and(|stamp| {
            stamp.len() == 15
                && stamp.ends_with('Z')
                && stamp.as_bytes()[..14].iter().all(u8::is_ascii_digit)
        })
}

fn retire_temporary_sudo() -> Result<()> {
    match managed_file(OLD_POLICY)?.as_deref() {
        None | Some(OLD_CLOSED) => {}
        Some(content) if old_grant(content) => replace_file(OLD_POLICY, OLD_CLOSED, 0o440)?,
        _ => return Err("Unrecognized legacy sudo policy".into()),
    }
    let service = format!("[Unit]\nDescription=Revoke temporary CNC maintenance sudo authorization\n[Service]\nType=oneshot\nExecStart={HELPER} sudo-close\nUser=root\nUMask=0077\nTimeoutStartSec=15\nTimeoutStopSec=3\n");
    let reset = format!("[Unit]\nDescription=Close CNC maintenance sudo authorization at boot\nBefore=ssh.service sshd.service\n[Service]\nType=oneshot\nExecStart={HELPER} sudo-close\nUser=root\nUMask=0077\n[Install]\nWantedBy=multi-user.target\n");
    let timer = format!("[Unit]\nDescription=Expire CNC maintenance sudo authorization after 15 minutes\n[Timer]\nOnActiveSec=900s\nAccuracySec=1s\nWakeSystem=yes\nUnit={EXPIRE}.service\n");
    for (name, content) in [
        (format!("{EXPIRE}.timer"), timer),
        (format!("{EXPIRE}.service"), service),
        (format!("{RESET}.service"), reset),
    ] {
        let path = format!("/usr/lib/systemd/system/{name}");
        if let Some(current) = managed_file(&path)? {
            if current != content {
                return Err("Local sudo service edits require review".into());
            }
            if name == format!("{EXPIRE}.timer") && Path::new("/run/systemd/system").is_dir() {
                fixed("/usr/bin/systemctl", &["stop", &name])?;
            }
            if name == format!("{RESET}.service") {
                fixed("/usr/bin/systemctl", &["disable", &name])?;
            }
            fs::remove_file(&path)?;
        }
    }
    Ok(())
}

pub(super) fn provision() -> Result<()> {
    let _guard = lock()?;
    retire_temporary_sudo()?;
    crate::validate_identity("cnc_admin", "/var/lib/betterlinuxcnc/admin")?;
    if policy_state()?.is_none() {
        replace_file(POLICY, CLOSED, 0o440)?;
    }
    enrollment::provision()?;
    match managed_file(PAM)?.as_deref() {
        Some(PAM_STACK) => Ok(()),
        None => replace_file(PAM, PAM_STACK, 0o644),
        _ => Err("Local admin PAM policy requires review".into()),
    }
}

// END: AdminSudoAuthorization
//--------//
