use crate::{Result, BASE, EXPORT, STATE};
use std::{
    ffi::CString,
    fs,
    os::unix::fs::{MetadataExt, PermissionsExt},
    path::Path,
    process::Command,
};

pub(crate) fn uid(name: &str) -> Result<u32> {
    let name = CString::new(name)?;
    let mut user: libc::passwd = unsafe { std::mem::zeroed() };
    let mut buffer = vec![0u8; 16384];
    let mut result = std::ptr::null_mut();
    let status = unsafe {
        libc::getpwnam_r(
            name.as_ptr(),
            &mut user,
            buffer.as_mut_ptr().cast(),
            buffer.len(),
            &mut result,
        )
    };
    if status != 0 || result.is_null() {
        return Err("Required system account is missing".into());
    }
    Ok(user.pw_uid)
}
fn fixed(command: &str, args: &[&str]) -> Result<()> {
    if !Command::new(command)
        .args(args)
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .status()?
        .success()
    {
        return Err(format!("Provisioning failed: {command}").into());
    }
    Ok(())
}
fn directory(path: &Path, owner: u32, group: u32, mode: u32) -> Result<()> {
    if path.exists() {
        let info = fs::symlink_metadata(path)?;
        if !info.is_dir() || ![0, owner].contains(&info.uid()) || info.mode() & 0o002 != 0 {
            return Err("Untrusted error-record directory".into());
        }
    } else {
        fs::create_dir(path)?;
    }
    let name = CString::new(path.as_os_str().as_encoded_bytes())?;
    if unsafe { libc::chown(name.as_ptr(), owner, group) } != 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    fs::set_permissions(path, fs::Permissions::from_mode(mode))?;
    Ok(())
}
pub(crate) fn run() -> Result<()> {
    if unsafe { libc::geteuid() } != 0 {
        return Err("Provisioning requires root".into());
    }
    if uid("cnc-errors").is_err() {
        fixed(
            "/usr/sbin/useradd",
            &[
                "--system",
                "--user-group",
                "--no-create-home",
                "--home-dir",
                STATE,
                "--shell",
                "/usr/sbin/nologin",
                "cnc-errors",
            ],
        )?;
    }
    let owner = uid("cnc-errors")?;
    let account = Command::new("/usr/bin/getent")
        .args(["passwd", "cnc-errors"])
        .output()?;
    let account = String::from_utf8(account.stdout)?;
    let fields: Vec<_> = account.trim().split(':').collect();
    if owner == 0 || fields.len() != 7 || fields[5] != STATE || fields[6] != "/usr/sbin/nologin" {
        return Err("Unexpected error service account".into());
    }
    let group = Command::new("/usr/bin/getent")
        .args(["group", "cnc-logs"])
        .output()?;
    let group = String::from_utf8(group.stdout)?
        .split(':')
        .nth(2)
        .ok_or("Missing log group")?
        .parse::<u32>()?;
    directory(Path::new(STATE), owner, group, 0o700)?;
    directory(&Path::new(STATE).join("pending"), owner, group, 0o700)?;
    // The service already runs with cnc-logs as its primary group. SGID is
    // unnecessary and is rejected by the updater's RestrictSUIDSGID sandbox.
    directory(Path::new(EXPORT), owner, group, 0o750)?;
    for category in crate::categories::ALL {
        directory(&Path::new(EXPORT).join(category), owner, group, 0o750)?;
    }
    if !Path::new("/var/lib/mysql").exists() {
        directory(Path::new("/var/lib/mysql"), 0, 0, 0o755)?;
    }
    let mysql_parent = fs::symlink_metadata("/var/lib/mysql")?;
    if !mysql_parent.is_dir() || mysql_parent.mode() & 0o002 != 0 {
        return Err("Untrusted MySQL parent".into());
    }
    directory(Path::new(crate::database::DATA), owner, group, 0o700)?;
    directory(Path::new("/etc/betterlinuxcnc/error-records"), 0, 0, 0o755)?;
    let config = Path::new(crate::config::PATH);
    if !config.exists() {
        crate::export::atomic(
            config,
            toml::to_string(&crate::config::Config::default())?.as_bytes(),
        )?;
        fs::set_permissions(config, fs::Permissions::from_mode(0o644))?;
    }
    // Units remain inside the old updater's application allowlist in the package;
    // root provision installs the fixed integration files, never caller content.
    let unit = "betterlinuxcnc-error-records.service";
    let bytes = fs::read(format!("{BASE}/{unit}"))?;
    let destination = Path::new("/usr/lib/systemd/system").join(unit);
    let ledger = Path::new("/etc/betterlinuxcnc/error-records/service.unit");
    if destination.exists() && fs::read(&destination)? != bytes {
        let info = fs::symlink_metadata(ledger)?;
        if !info.is_file()
            || info.uid() != 0
            || info.mode() & 0o022 != 0
            || fs::read(ledger)? != fs::read(&destination)?
        {
            return Err("Error service has local edits".into());
        }
    }
    crate::export::atomic(&destination, &bytes)?;
    fs::set_permissions(destination, fs::Permissions::from_mode(0o644))?;
    crate::export::atomic(ledger, &bytes)?;
    fs::set_permissions(ledger, fs::Permissions::from_mode(0o644))?;
    fixed("/usr/bin/systemctl", &["enable", unit])?;
    if Path::new("/run/systemd/system").is_dir() {
        fixed("/usr/bin/systemctl", &["daemon-reload"])?;
        // Explicitly requested diagnostics activation; this service has no CNC control API.
        fixed("/usr/bin/systemctl", &["restart", "--no-block", unit])?;
    }
    Ok(())
}
