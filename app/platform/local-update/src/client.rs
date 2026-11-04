use crate::Result;
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::os::unix::net::UnixStream;
use std::path::Path;
const ROOT: &str = "/var/lib/betterlinuxcnc/build";
const SOCKET: &str = "/run/betterlinuxcnc-cnc-maint-build.sock";
const MAX_PACKAGE: u64 = 256 * 1024 * 1024;
fn peer(stream: &UnixStream) -> Result<u32> {
    use std::os::fd::AsRawFd;
    let mut credentials: libc::ucred = unsafe { std::mem::zeroed() };
    let mut size = std::mem::size_of::<libc::ucred>() as libc::socklen_t;
    if unsafe {
        libc::getsockopt(
            stream.as_raw_fd(),
            libc::SOL_SOCKET,
            libc::SO_PEERCRED,
            (&mut credentials as *mut libc::ucred).cast(),
            &mut size,
        )
    } != 0
    {
        return Err(io::Error::last_os_error().into());
    }
    Ok(credentials.uid)
}
fn valid_filename(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 200
        && !name.starts_with('.')
        && name.ends_with(".deb")
        && name
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"._+-".contains(&byte))
}
fn package_file(name: &str) -> Result<File> {
    if !valid_filename(name) {
        return Err("Use a DEB filename from the packages directory".into());
    }
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(0x20000 | 0x800)
        .open(Path::new(ROOT).join("packages").join(name))?;
    let info = file.metadata()?;
    if !info.is_file()
        || info.uid() != unsafe { libc::getuid() }
        || info.nlink() != 1
        || info.len() == 0
        || info.len() > MAX_PACKAGE
    {
        return Err("Invalid local package".into());
    }
    Ok(file)
}
fn install(name: &str) -> Result<()> {
    let file = package_file(name)?;
    let mut stream = UnixStream::connect(SOCKET)?;
    if peer(&stream)? != 0 {
        return Err("Local package service is not root".into());
    }
    io::copy(&mut file.take(MAX_PACKAGE + 1), &mut stream)?;
    stream.shutdown(std::net::Shutdown::Write)?;
    let mut reader = std::io::BufReader::new(stream);
    let mut complete = false;
    use std::io::BufRead;
    loop {
        let mut line = String::new();
        if std::io::Read::take(&mut reader, 65537).read_line(&mut line)? == 0 {
            break;
        }
        if line.len() > 65536 {
            return Err("Installation response is too large".into());
        }
        if line.trim() == "LOCAL-INSTALL-COMPLETE" {
            complete = true;
        }
        print!("{line}");
        io::stdout().flush()?;
    }
    if !complete {
        return Err("Local package installation did not complete".into());
    }
    Ok(())
}

pub(crate) fn run(args: &[String]) -> Result<()> {
    let output = crate::command("/usr/bin/id")
        .args(["-u", "cnc-maint"])
        .output()?;
    let uid: u32 = String::from_utf8(output.stdout)?.trim().parse()?;
    if !output.status.success()
        || uid == 0
        || unsafe { libc::getuid() } != uid
        || unsafe { libc::geteuid() } != uid
    {
        return Err("cnc-maint OS account required".into());
    }
    if let [operation, name] = args {
        if operation == "install-deb" {
            return install(name);
        }
    }
    Err("Use install-deb FILE from the maintenance packages directory".into())
}
