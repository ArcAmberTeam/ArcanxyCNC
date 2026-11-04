//! Unprivileged source/build workspace and authenticated local-DEB submission.
use super::{command, enabled, peer, trusted_parent, validate_account, Result};
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::process::Stdio;
use std::time::Duration;

pub(super) const UNIT: &str = "betterlinuxcnc-cnc-maint-build";
const ROOT: &str = "/var/lib/betterlinuxcnc/build";
pub(super) const SOCKET_UNIT: &str = "[Unit]\nDescription=Maintenance local package requests\n[Socket]\nListenStream=/run/betterlinuxcnc-cnc-maint-build.sock\nSocketUser=cnc-maint\nSocketMode=0600\nAccept=yes\nMaxConnections=2\nRemoveOnStop=yes\n[Install]\nWantedBy=sockets.target\n";
pub(super) const SERVICE_UNIT: &str = "[Unit]\nDescription=Guarded maintenance local package installation\n[Service]\nExecStart=/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account install-serve\nUser=root\nStandardInput=socket\nStandardOutput=null\nStandardError=journal\nTimeoutStartSec=infinity\nUMask=0077\nNoNewPrivileges=yes\nPrivateTmp=no\nProtectHome=read-only\nProtectKernelTunables=yes\nProtectKernelModules=yes\nProtectControlGroups=yes\nLockPersonality=yes\nLimitCORE=0\n";

unsafe extern "C" {
    fn getuid() -> u32;
    fn getgid() -> u32;
    fn fchown(fd: i32, uid: u32, gid: u32) -> i32;
}
fn identity() -> Result<(u32, u32)> {
    validate_account()?;
    let read = |flag: &str| -> Result<u32> {
        let result = command("/usr/bin/id").args([flag, "cnc-maint"]).output()?;
        if !result.status.success() {
            return Err("Maintenance account is unavailable".into());
        }
        Ok(String::from_utf8(result.stdout)?.trim().parse()?)
    };
    Ok((read("-u")?, read("-g")?))
}
fn directory(path: &Path, uid: u32, gid: u32, mode: u32) -> Result<()> {
    trusted_parent(path)?;
    match fs::create_dir(path) {
        Ok(()) => {}
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {}
        Err(error) => return Err(error.into()),
    }
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(0x20000 | 0x10000)
        .open(path)?;
    let info = file.metadata()?;
    if !info.is_dir() || ![0, uid].contains(&info.uid()) {
        return Err("Unexpected workspace ownership".into());
    }
    if unsafe { fchown(file.as_raw_fd(), uid, gid) } != 0 {
        return Err(io::Error::last_os_error().into());
    }
    file.set_permissions(fs::Permissions::from_mode(mode))?;
    Ok(())
}
pub(super) fn provision() -> Result<()> {
    let (uid, gid) = identity()?;
    directory(Path::new(ROOT), 0, 0, 0o755)?;
    for child in ["src", "work", "packages", "home"] {
        directory(&Path::new(ROOT).join(child), uid, gid, 0o700)?;
    }
    Ok(())
}
pub(super) fn serve_install() -> Result<()> {
    let mut stream = unsafe { UnixStream::from_raw_fd(0) };
    if peer(&stream)? != identity()?.0 || !enabled()? {
        return Err("Enabled maintenance account required".into());
    }
    stream.set_read_timeout(Some(Duration::from_secs(30)))?;
    let status = command("/usr/bin/betterlinuxcnc-updater")
        .arg("maintenance-install")
        .stdin(Stdio::from(std::os::fd::OwnedFd::from(stream.try_clone()?)))
        .stdout(Stdio::from(std::os::fd::OwnedFd::from(stream.try_clone()?)))
        .stderr(Stdio::from(std::os::fd::OwnedFd::from(stream.try_clone()?)))
        .status()?;
    if status.success() {
        stream.write_all(b"LOCAL-INSTALL-COMPLETE\n")?;
    }
    Ok(())
}
pub(super) fn run(args: &[String]) -> Result<()> {
    let (uid, gid) = identity()?;
    if unsafe { getuid() } != uid
        || unsafe { super::geteuid() } != uid
        || unsafe { getgid() } != gid
    {
        return Err("The cnc-maint OS account is required".into());
    }
    let binary = if args.first().is_some_and(|arg| arg == "install-deb") {
        "/usr/lib/betterlinuxcnc/local-update/betterlinuxcnc-local-update"
    } else {
        "/usr/lib/betterlinuxcnc/package-build/betterlinuxcnc-package-build"
    };
    use std::os::unix::process::CommandExt;
    Err(command(binary)
        .args(args)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .exec()
        .into())
}
