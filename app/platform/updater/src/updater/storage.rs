use super::{Event, Result, PACKAGE};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File, OpenOptions},
    io::Read,
    os::{
        fd::AsRawFd,
        unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
    },
    path::PathBuf,
};

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Staged {
    pub version: String,
    pub sha256: String,
    pub size: u64,
    pub architecture: String,
}

pub(super) struct Store {
    pub directory: PathBuf,
    pub public_directory: Option<PathBuf>,
}

impl Store {
    pub fn open() -> Result<Self> {
        let base = std::env::var_os("XDG_CACHE_HOME")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("HOME").map(|p| PathBuf::from(p).join(".cache")))
            .ok_or("无法确定更新缓存目录")?;
        let directory = base.join("betterlinuxcnc/update");
        fs::create_dir_all(&directory)?;
        let info = fs::symlink_metadata(&directory)?;
        if !info.is_dir() || info.uid() != unsafe { libc::getuid() } {
            return Err("更新目录必须属于当前用户且不能是符号链接".into());
        }
        fs::set_permissions(&directory, fs::Permissions::from_mode(0o700))?;
        Ok(Self {
            directory,
            public_directory: None,
        })
    }
    pub fn lock(&self) -> Result<File> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
            .open(self.directory.join("update.lock"))?;
        let info = file.metadata()?;
        if !info.is_file()
            || info.uid() != unsafe { libc::getuid() }
            || info.nlink() != 1
            || info.mode() & 0o077 != 0
        {
            return Err("更新互斥锁不是可信私有文件".into());
        }
        if unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
            return Err("已有更新任务正在运行".into());
        }
        Ok(file)
    }
    pub fn save<T: Serialize>(&self, name: &str, value: &T) -> Result<()> {
        let mut file = tempfile::NamedTempFile::new_in(&self.directory)?;
        serde_json::to_writer(&mut file, value)?;
        file.as_file().sync_all()?;
        file.persist(self.directory.join(name))?;
        Ok(())
    }
    fn read(&self, name: &str) -> Result<Vec<u8>> {
        let file = OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_NOFOLLOW)
            .open(self.directory.join(name))?;
        if !file.metadata()?.is_file() || file.metadata()?.len() > 65536 {
            return Err("更新记录无效".into());
        }
        let mut body = Vec::new();
        file.take(65537).read_to_end(&mut body)?;
        Ok(body)
    }
    pub fn status(&self) -> Result<Event> {
        if !self.directory.join("status.json").try_exists()? {
            return Ok(Event::new("idle", "", "", 0));
        }
        Ok(serde_json::from_slice(&self.read("status.json")?)?)
    }
    pub fn publish(&self, event: &Event) -> Result<()> {
        self.save("status.json", event)?;
        if let Some(directory) = &self.public_directory {
            let mut visible = event.clone();
            if matches!(
                visible.phase.as_str(),
                "checking" | "downloading" | "verifying" | "ready"
            ) {
                visible.phase = "installing".into();
            }
            let mut file = tempfile::NamedTempFile::new_in(directory)?;
            serde_json::to_writer(&mut file, &visible)?;
            file.as_file()
                .set_permissions(fs::Permissions::from_mode(0o644))?;
            file.as_file().sync_all()?;
            file.persist(directory.join("status.json"))?;
        }
        event.emit()
    }
    pub fn staged(&self) -> Result<Staged> {
        let staged: Staged = serde_json::from_slice(&self.read("staged.json")?)?;
        let file = OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_NOFOLLOW)
            .open(self.directory.join("package.deb"))?;
        if !file.metadata()?.is_file() || file.metadata()?.len() != staged.size {
            return Err("更新安装包大小不符，请重新下载".into());
        }
        if hash(file)? != staged.sha256 {
            return Err("更新安装包校验失败，请重新下载".into());
        }
        Ok(staged)
    }
}

pub(super) fn hash(mut source: impl Read) -> Result<String> {
    let mut digest = Sha256::new();
    let mut buffer = [0; 65536];
    loop {
        let size = source.read(&mut buffer)?;
        if size == 0 {
            break;
        }
        digest.update(&buffer[..size]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

pub(super) fn package_info(path: &std::path::Path) -> Result<(String, String)> {
    let output = super::command("/usr/bin/dpkg-deb")
        .args([
            "--show",
            "--showformat=${Package}\n${Version}\n${Architecture}\n",
        ])
        .arg(path)
        .output()?;
    if !output.status.success() {
        return Err("无法读取 Debian 安装包信息".into());
    }
    let text = String::from_utf8(output.stdout)?;
    let fields: Vec<_> = text.lines().collect();
    if fields.len() != 3 || fields[0] != PACKAGE {
        return Err("Release 安装包不属于 BetterLinuxCNC".into());
    }
    validate_version(fields[1])?;
    Ok((fields[1].into(), fields[2].into()))
}

pub(super) fn validate_version(value: &str) -> Result<()> {
    if value.len() > 128
        || !value.as_bytes().first().is_some_and(u8::is_ascii_digit)
        || !value
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b".+:~-".contains(&c))
    {
        return Err("版本号无效".into());
    }
    Ok(())
}

pub(super) fn installed_version(fallback: &str) -> Result<String> {
    validate_version(fallback)?;
    let output = super::command("/usr/bin/dpkg-query")
        .args(["--show", "--showformat=${Version}", PACKAGE])
        .output()?;
    if output.status.success() {
        let value = String::from_utf8(output.stdout)?;
        validate_version(&value)?;
        Ok(value)
    } else {
        Ok(fallback.into())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn validates_versions_and_streamed_digest() {
        for value in ["0.3.0", "1:2.0-1", "1.0~rc1"] {
            validate_version(value).unwrap();
        }
        for value in ["", "--help", "1\n2", "1/2", "v1.0", "1;true"] {
            assert!(validate_version(value).is_err());
        }
        assert_eq!(
            hash(&b"abc"[..]).unwrap(),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }
    #[test]
    fn refuses_changed_staged_payload_and_concurrent_writer() {
        let directory = tempfile::tempdir().unwrap();
        let store = Store {
            directory: directory.path().to_owned(),
            public_directory: None,
        };
        let _guard = store.lock().unwrap();
        assert!(store.lock().is_err());
        fs::write(directory.path().join("package.deb"), b"abc").unwrap();
        store
            .save(
                "staged.json",
                &Staged {
                    version: "1.0".into(),
                    architecture: "amd64".into(),
                    size: 3,
                    sha256: hash(&b"abc"[..]).unwrap(),
                },
            )
            .unwrap();
        assert!(store.staged().is_ok());
        fs::write(directory.path().join("package.deb"), b"abd").unwrap();
        assert!(store.staged().is_err());
    }
}
