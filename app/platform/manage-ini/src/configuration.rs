//! Fixed-path privileged configuration protocol and low-privilege client.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::os::{
    fd::AsRawFd,
    unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
};
use std::{
    fs,
    io::{self, Read, Write},
    path::{Component, Path, PathBuf},
    process::{Command, Stdio},
};

const HELPER: &str = "/usr/lib/betterlinuxcnc/manage-ini/pa-config";
const LAUNCHER: &str = "/etc/betterlinuxcnc/launcher.json";
const LEASE: &str = "/var/lib/betterlinuxcnc/configuration.lock";
const MAX: u64 = 2 * 1024 * 1024;

#[derive(Clone, Serialize, Deserialize)]
pub(crate) struct Document {
    pub content: String,
    pub revision: String,
    pub label: String,
}

#[derive(Serialize, Deserialize)]
#[serde(tag = "operation", rename_all = "snake_case", deny_unknown_fields)]
enum Request {
    Read {
        target: String,
    },
    Save {
        target: String,
        revision: String,
        content: String,
    },
}
#[derive(Serialize, Deserialize)]
struct Response {
    document: Option<Document>,
    error: Option<String>,
}

pub(crate) fn read(target: &str) -> io::Result<Document> {
    client(Request::Read {
        target: target.into(),
    })
}
pub(crate) fn save(target: &str, revision: &str, content: String) -> io::Result<Document> {
    client(Request::Save {
        target: target.into(),
        revision: revision.into(),
        content,
    })
}

fn client(request: Request) -> io::Result<Document> {
    let mut child = Command::new("/usr/bin/sudo")
        .args(["-n", "--", HELPER])
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LANG", "C.UTF-8")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()?;
    let result = (|| {
        let mut input = child
            .stdin
            .take()
            .ok_or_else(|| io::Error::other("Missing helper input"))?;
        serde_json::to_writer(&mut input, &request)?;
        drop(input);
        let mut bytes = Vec::new();
        child
            .stdout
            .take()
            .ok_or_else(|| io::Error::other("Missing helper output"))?
            .take(MAX + 1)
            .read_to_end(&mut bytes)?;
        if bytes.len() as u64 > MAX {
            return Err(io::Error::other("Configuration response exceeds limit"));
        }
        let response: Response = serde_json::from_slice(&bytes).map_err(|_| {
            io::Error::other("Configuration helper unavailable; activate the PA maintenance policy")
        })?;
        response.document.ok_or_else(|| {
            io::Error::other(
                response
                    .error
                    .unwrap_or_else(|| "Configuration request failed".into()),
            )
        })
    })();
    if result.is_err() {
        let _ = child.kill();
    }
    let status = child.wait()?;
    if !status.success() && result.is_ok() {
        return Err(io::Error::other("Configuration helper failed"));
    }
    result
}

pub(crate) fn serve() -> u8 {
    let result = (|| {
        // SAFETY: these libc calls only inspect process credentials.
        if !cfg!(target_os = "linux")
            || unsafe { libc::getuid() != 0 || libc::geteuid() != 0 }
            || std::env::args_os().len() != 1
        {
            return Err(io::Error::other(
                "Configuration helper requires root and no arguments",
            ));
        }
        let mut input = String::new();
        io::stdin().take(MAX + 1).read_to_string(&mut input)?;
        if input.len() as u64 > MAX {
            return Err(io::Error::other("Configuration request exceeds limit"));
        }
        let request: Request = serde_json::from_str(&input)?;
        execute(request)
    })();
    let (response, code) = match result {
        Ok(document) => (
            Response {
                document: Some(document),
                error: None,
            },
            0,
        ),
        Err(error) => {
            betterlinuxcnc_error_client::report(
                "configuration",
                "configuration_write_failed",
                &error.to_string(),
            );
            (
                Response {
                    document: None,
                    error: Some(error.to_string()),
                },
                1,
            )
        }
    };
    let _ = serde_json::to_writer(io::stdout(), &response);
    code
}

fn trusted(path: &Path) -> io::Result<()> {
    if !path.is_absolute()
        || path
            .components()
            .any(|c| !matches!(c, Component::RootDir | Component::Normal(_)))
    {
        return Err(io::Error::other("Invalid managed path"));
    }
    for parent in path.ancestors() {
        let info = fs::symlink_metadata(parent)?;
        if info.uid() != 0
            || info.mode() & 0o022 != 0
            || info.file_type().is_symlink()
            || (parent != path && !info.is_dir())
        {
            return Err(io::Error::other(
                "Configuration path must be root-owned without links or writable parents",
            ));
        }
    }
    Ok(())
}

fn load(path: &Path) -> io::Result<Document> {
    trusted(path)?;
    let mut file = fs::OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)?;
    let info = file.metadata()?;
    if !info.is_file() || info.nlink() != 1 || info.uid() != 0 || info.mode() & 0o022 != 0 {
        return Err(io::Error::other("Unsafe configuration file"));
    }
    let mut content = String::new();
    (&mut file)
        .take(256 * 1024 + 1)
        .read_to_string(&mut content)?;
    if content.len() > 256 * 1024 {
        return Err(io::Error::other("Configuration exceeds 256 KiB"));
    }
    Ok(Document {
        revision: revision(&content),
        content,
        label: path.display().to_string(),
    })
}

fn revision(content: &str) -> String {
    format!("{:x}", Sha256::digest(content.as_bytes()))
}

fn ini_path(content: &str) -> io::Result<PathBuf> {
    let config: serde_json::Value = serde_json::from_str(content)?;
    let path = PathBuf::from(
        config["ini"]
            .as_str()
            .ok_or_else(|| io::Error::other("Launcher has no INI path"))?,
    );
    if !path.starts_with("/etc/betterlinuxcnc/machine") {
        return Err(io::Error::other(
            "INI must be inside /etc/betterlinuxcnc/machine",
        ));
    }
    trusted(&path)?;
    if !fs::metadata(&path)?.is_file() {
        return Err(io::Error::other("INI path is not a file"));
    }
    Ok(path)
}

fn stopped() -> io::Result<()> {
    let uid = crate::permissions::account_uid(c"linuxcnc").map_err(io::Error::other)?;
    for path in [
        PathBuf::from("/tmp/linuxcnc.lock"),
        PathBuf::from(format!("/run/user/{uid}/betterlinuxcnc/control.sock")),
    ] {
        match fs::symlink_metadata(path) {
            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
            Err(error) => return Err(error),
            Ok(_) => {
                return Err(io::Error::other(
                    "Stop the CNC launcher before saving configuration",
                ))
            }
        }
    }
    Ok(())
}

fn execute(request: Request) -> io::Result<Document> {
    let target = match &request {
        Request::Read { target } | Request::Save { target, .. } => target.clone(),
    };
    if !matches!(target.as_str(), "ini" | "launcher.json") {
        return Err(io::Error::other("Unknown management target"));
    }
    // The launcher and every privileged save share this installation-owned lease.
    trusted(Path::new(LEASE))?;
    let lock = fs::OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW)
        .open(LEASE)?;
    let info = lock.metadata()?;
    if !info.is_file() || info.nlink() != 1 {
        return Err(io::Error::other("Untrusted configuration lease"));
    }
    let exclusive = matches!(request, Request::Save { .. });
    // SAFETY: lock remains open for the complete read/backup/write transaction.
    if unsafe {
        libc::flock(
            lock.as_raw_fd(),
            (if exclusive {
                libc::LOCK_EX
            } else {
                libc::LOCK_SH
            }) | libc::LOCK_NB,
        )
    } != 0
    {
        return Err(io::Error::other(
            "Stop the CNC launcher before saving; another configuration operation may be active",
        ));
    }
    let _update_lock = if exclusive {
        let directory = Path::new("/var/cache/betterlinuxcnc/update");
        trusted(directory)?;
        let file = fs::OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
            .open(directory.join("update.lock"))?;
        let info = file.metadata()?;
        if !info.is_file() || info.uid() != 0 || info.nlink() != 1 || info.mode() & 0o077 != 0 {
            return Err(io::Error::other("Untrusted update lease"));
        }
        // SAFETY: file remains open through the configuration transaction.
        if unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
            return Err(io::Error::other(
                "An update or firmware operation is in progress",
            ));
        }
        Some(file)
    } else {
        None
    };
    let launcher = load(Path::new(LAUNCHER))?;
    let path = if target == "ini" {
        ini_path(&launcher.content)?
    } else {
        PathBuf::from(LAUNCHER)
    };
    let current = load(&path)?;
    let Request::Save {
        content,
        revision: expected,
        ..
    } = request
    else {
        return Ok(current);
    };
    if current.revision != expected {
        return Err(io::Error::other(
            "Configuration changed externally; reopen before saving",
        ));
    }
    if content.len() > 256 * 1024 {
        return Err(io::Error::other("Configuration exceeds 256 KiB"));
    }
    if target == "ini" {
        crate::ini::validate(&content)?;
    } else {
        ini_path(&content)?;
    }
    stopped()?;
    let backup = Command::new("/usr/sbin/betterlinuxcnc-appliance")
        .arg("backup")
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LANG", "C.UTF-8")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()?;
    if !backup.success() {
        return Err(io::Error::other(
            "Backup failed; configuration was not changed",
        ));
    }
    stopped()?;
    if load(&path)?.revision != expected {
        return Err(io::Error::other("Configuration changed during backup"));
    }
    let temporary = path.with_file_name(format!(".pa-save-{}", std::process::id()));
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&temporary)?;
    let result = (|| {
        file.write_all(content.as_bytes())?;
        let original = fs::metadata(&path)?;
        // SAFETY: file is the newly created regular staging file owned by this helper.
        if unsafe { libc::fchown(file.as_raw_fd(), original.uid(), original.gid()) } != 0 {
            return Err(io::Error::last_os_error());
        }
        file.set_permissions(fs::Permissions::from_mode(original.mode() & 0o777))?;
        file.sync_all()?;
        fs::rename(&temporary, &path)?;
        fs::File::open(
            path.parent()
                .ok_or_else(|| io::Error::other("No configuration parent"))?,
        )?
        .sync_all()?;
        load(&path)
    })();
    let _ = fs::remove_file(temporary);
    result
}
