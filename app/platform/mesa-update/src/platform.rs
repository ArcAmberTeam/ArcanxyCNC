use crate::contract::valid_version;
use crate::Result;
use std::fs::{File, OpenOptions};
use std::io::Read;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::path::{Component, Path, PathBuf};
use std::process::Command;

pub(crate) fn operating_user() -> Result<u32> {
    let name = c"linuxcnc";
    // This process is single-threaded at entry; copy the uid before any network work.
    let entry = unsafe { libc::getpwnam(name.as_ptr()) };
    if entry.is_null() {
        return Err("The fixed linuxcnc operating account has not been provisioned".into());
    }
    let uid = unsafe { (*entry).pw_uid };
    if uid == 0 {
        return Err("The linuxcnc operating account must not be root".into());
    }
    Ok(uid)
}

pub(crate) fn require_operator() -> Result<u32> {
    let uid = operating_user()?;
    if unsafe { libc::geteuid() } != uid || unsafe { libc::getuid() } != uid {
        return Err("Mesa checks and downloads must run as the fixed linuxcnc account".into());
    }
    Ok(uid)
}

pub(crate) fn require_root() -> Result<()> {
    if unsafe { libc::geteuid() } != 0 || unsafe { libc::getuid() } != 0 {
        return Err("The separate Mesa flash entry requires the root system service".into());
    }
    Ok(())
}

pub(crate) fn command(program: &str) -> Command {
    let mut command = Command::new(program);
    command
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("HOME", "/root")
        .env("LANG", "C")
        .current_dir("/");
    command
}

pub(crate) fn host_boot_id() -> Result<String> {
    let mut text = String::new();
    OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open("/proc/sys/kernel/random/boot_id")?
        .take(64)
        .read_to_string(&mut text)?;
    let id = text.strip_suffix('\n').unwrap_or(&text);
    if !valid_boot_id(id) {
        return Err("Cannot establish the current host boot identity".into());
    }
    Ok(id.to_owned())
}

pub(crate) fn valid_boot_id(id: &str) -> bool {
    uuid::Uuid::parse_str(id)
        .is_ok_and(|value| !value.is_nil() && value.hyphenated().to_string() == id)
}

pub(crate) fn trusted_file(path: &Path, private: bool) -> Result<File> {
    let mut current = PathBuf::new();
    for component in path.components() {
        if !matches!(component, Component::RootDir | Component::Normal(_)) {
            return Err("Invalid fixed privileged path".into());
        }
        current.push(component);
        let info = std::fs::symlink_metadata(&current)?;
        if info.uid() != 0
            || info.mode() & 0o022 != 0
            || info.file_type().is_symlink()
            || (current != path && !info.is_dir())
        {
            return Err("Privileged command or file is not on trusted root-owned paths".into());
        }
    }
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)?;
    let info = file.metadata()?;
    if !info.is_file()
        || info.uid() != 0
        || info.nlink() != 1
        || info.mode() & if private { 0o077 } else { 0o022 } != 0
    {
        return Err("Privileged file ownership or type is unsafe".into());
    }
    Ok(file)
}

pub(crate) fn installed_version() -> Result<String> {
    let output = Command::new("/usr/bin/dpkg-query")
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("HOME", "/")
        .env("LANG", "C")
        .current_dir("/")
        .args([
            "-W",
            "-f=${db:Status-Status}\n${Version}\n",
            if Path::new("/usr/share/betterlinuxcnc/package-rename").is_file() {
                "betterlinuxcnc-qt"
            } else {
                "betterlinuxcnc"
            },
        ])
        .output()
        .map_err(|_| "Cannot query the installed application package")?;
    if !output.status.success() {
        return Err("The application package is not installed".into());
    }
    parse_installed_version(&output.stdout)
}

fn parse_installed_version(bytes: &[u8]) -> Result<String> {
    let text = std::str::from_utf8(bytes)?;
    let lines: Vec<_> = text.lines().collect();
    if lines.len() != 2 || lines[0] != "installed" || !valid_version(lines[1]) {
        return Err(
            "The application package must be completely installed at a supported release version"
                .into(),
        );
    }
    Ok(lines[1].to_owned())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn boot_identity_requires_a_canonical_nonempty_uuid() {
        assert!(valid_boot_id("c6076b8e-a07e-4c6d-93a1-0b1f99551b63"));
        for id in [
            "",
            "00000000-0000-0000-0000-000000000000",
            "c6076b8ea07e4c6d93a10b1f99551b63",
            "c6076b8e-a07e-4c6d-93a1-0b1f99551b63\n",
            "invalid",
        ] {
            assert!(!valid_boot_id(id));
        }
    }

    #[test]
    fn partial_install_and_untrusted_version_text_are_rejected() {
        assert_eq!(
            parse_installed_version(b"installed\n26.10.26.1\n").unwrap(),
            "26.10.26.1"
        );
        for bytes in [
            b"unpacked\n26.10.26.1\n".as_slice(),
            b"half-configured\n26.10.26.1\n",
            b"installed\n../../main\n",
            b"installed\n26.10.26.1\nextra\n",
        ] {
            assert!(parse_installed_version(bytes).is_err());
        }
    }
}
