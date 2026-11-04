use crate::Result;
use std::ffi::CString;
use std::fs::File;
use std::io::{Read, Write};
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::fs::MetadataExt;
use std::path::{Component, Path, PathBuf};

pub(crate) const USER_CACHE: &str = "/var/cache/betterlinuxcnc/user/mesa-update";
pub(crate) const ROOT_CACHE: &str = "/var/cache/betterlinuxcnc/mesa-flash";
pub(crate) const ROOT_STATE: &str = "/var/lib/betterlinuxcnc/mesa-flash";
const USER_PARENT: &str = "/var/cache/betterlinuxcnc/user";

pub(crate) struct Store {
    directory: File,
    owner: u32,
    public: bool,
}

impl Store {
    pub(crate) fn user(uid: u32, create: bool) -> Result<Option<Self>> {
        Self::open(USER_CACHE, uid, Some(Path::new(USER_PARENT)), false, create)
    }

    pub(crate) fn root_cache() -> Result<Self> {
        Self::open(ROOT_CACHE, 0, None, false, true)?.ok_or_else(|| "Missing root cache".into())
    }

    pub(crate) fn root_state(create: bool) -> Result<Option<Self>> {
        Self::open(ROOT_STATE, 0, None, true, create)
    }

    fn open(
        path: &str,
        owner: u32,
        user_parent: Option<&Path>,
        public: bool,
        create: bool,
    ) -> Result<Option<Self>> {
        let target = Path::new(path);
        let mut directory = File::open("/")?;
        let mut current = PathBuf::from("/");
        for component in target.components() {
            let Component::Normal(part) = component else {
                if component == Component::RootDir {
                    continue;
                }
                return Err("Invalid fixed storage path".into());
            };
            current.push(part);
            let name = CString::new(part.as_encoded_bytes())?;
            let mut fd = open_directory_at(&directory, &name);
            if fd < 0 && std::io::Error::last_os_error().kind() == std::io::ErrorKind::NotFound {
                if current != target || !create {
                    if !create {
                        return Ok(None);
                    }
                    return Err("Required system storage parent is missing".into());
                }
                // Only the final fixed directory may be created here. Its parent is pinned.
                let mode = if public { 0o755 } else { 0o700 };
                if unsafe { libc::mkdirat(directory.as_raw_fd(), name.as_ptr(), mode) } != 0
                    && std::io::Error::last_os_error().kind() != std::io::ErrorKind::AlreadyExists
                {
                    return Err(std::io::Error::last_os_error().into());
                }
                fd = open_directory_at(&directory, &name);
            }
            if fd < 0 {
                return Err("Storage path contains an unsafe or inaccessible directory".into());
            }
            directory = unsafe { File::from_raw_fd(fd) };
            let expected = if user_parent.is_some_and(|path| current.starts_with(path)) {
                owner
            } else {
                0
            };
            let info = directory.metadata()?;
            if !info.is_dir()
                || info.uid() != expected
                || info.mode() & 0o022 != 0
                || (current == target && !public && info.mode() & 0o077 != 0)
            {
                return Err("Storage directory ownership or permissions are unsafe".into());
            }
            if current == target
                && public
                && create
                && unsafe { libc::fchmod(directory.as_raw_fd(), 0o755) } != 0
            {
                return Err("Cannot publish the root service status directory".into());
            }
        }
        Ok(Some(Self {
            directory,
            owner,
            public,
        }))
    }

    pub(crate) fn lock(&self) -> Result<File> {
        self.try_lock()?
            .ok_or_else(|| "Another Mesa update operation is already running".into())
    }

    pub(crate) fn try_lock(&self) -> Result<Option<File>> {
        let name = CString::new("operation.lock")?;
        let fd = unsafe {
            libc::openat(
                self.directory.as_raw_fd(),
                name.as_ptr(),
                libc::O_WRONLY
                    | libc::O_CREAT
                    | libc::O_NOFOLLOW
                    | libc::O_CLOEXEC
                    | libc::O_NONBLOCK,
                0o600,
            )
        };
        if fd < 0 {
            return Err("Cannot open operation lock".into());
        }
        let file = unsafe { File::from_raw_fd(fd) };
        self.validate_file(&file, false)?;
        if unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
            let error = std::io::Error::last_os_error();
            if error.kind() == std::io::ErrorKind::WouldBlock {
                return Ok(None);
            }
            return Err(error.into());
        }
        Ok(Some(file))
    }

    pub(crate) fn read_status(&self) -> Result<Option<Vec<u8>>> {
        let Some(file) = self.open_record("status.json")? else {
            return Ok(None);
        };
        let mut bytes = Vec::new();
        file.take(1024 * 1024 + 1).read_to_end(&mut bytes)?;
        if bytes.len() > 1024 * 1024 {
            return Err("Mesa status exceeds size limit".into());
        }
        Ok(Some(bytes))
    }

    pub(crate) fn modified(&self, name: &str) -> Result<Option<std::time::SystemTime>> {
        self.open_record(name)?
            .map(|file| Ok(file.metadata()?.modified()?))
            .transpose()
    }

    fn open_record(&self, name: &str) -> Result<Option<File>> {
        if !crate::contract::valid_asset(name) {
            return Err("Invalid storage record name".into());
        }
        let name = CString::new(name)?;
        let fd = unsafe {
            libc::openat(
                self.directory.as_raw_fd(),
                name.as_ptr(),
                libc::O_RDONLY | libc::O_NOFOLLOW | libc::O_CLOEXEC | libc::O_NONBLOCK,
            )
        };
        if fd < 0 {
            if std::io::Error::last_os_error().kind() == std::io::ErrorKind::NotFound {
                return Ok(None);
            }
            return Err("Cannot safely read Mesa status".into());
        }
        let file = unsafe { File::from_raw_fd(fd) };
        self.validate_file(&file, self.public)?;
        Ok(Some(file))
    }

    pub(crate) fn write(&self, name: &str, bytes: &[u8]) -> Result<()> {
        if !crate::contract::valid_asset(name) {
            return Err("Invalid storage file name".into());
        }
        let temporary = CString::new(format!("pending-{}", uuid::Uuid::new_v4()))?;
        let destination = CString::new(name)?;
        let mode = if self.public { 0o644 } else { 0o600 };
        let fd = unsafe {
            libc::openat(
                self.directory.as_raw_fd(),
                temporary.as_ptr(),
                libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL | libc::O_NOFOLLOW | libc::O_CLOEXEC,
                mode,
            )
        };
        if fd < 0 {
            return Err("Cannot create private Mesa staging file".into());
        }
        let mut file = unsafe { File::from_raw_fd(fd) };
        let result = (|| {
            file.write_all(bytes)?;
            // Explicit modes also apply when the system service has UMask=0077.
            if unsafe { libc::fchmod(file.as_raw_fd(), mode) } != 0 {
                return Err(std::io::Error::last_os_error().into());
            }
            file.sync_all()?;
            if unsafe {
                libc::renameat(
                    self.directory.as_raw_fd(),
                    temporary.as_ptr(),
                    self.directory.as_raw_fd(),
                    destination.as_ptr(),
                )
            } != 0
            {
                return Err(std::io::Error::last_os_error().into());
            }
            self.directory.sync_all()?;
            Ok(())
        })();
        if result.is_err() {
            unsafe { libc::unlinkat(self.directory.as_raw_fd(), temporary.as_ptr(), 0) };
        }
        result
    }

    fn validate_file(&self, file: &File, public: bool) -> Result<()> {
        let info = file.metadata()?;
        if !info.is_file()
            || info.uid() != self.owner
            || info.nlink() != 1
            || info.mode() & if public { 0o022 } else { 0o077 } != 0
        {
            return Err("Mesa state or lock is not a safe regular file".into());
        }
        Ok(())
    }
}

fn open_directory_at(directory: &File, name: &CString) -> i32 {
    unsafe {
        libc::openat(
            directory.as_raw_fd(),
            name.as_ptr(),
            libc::O_RDONLY | libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::symlink;

    fn temporary(path: &Path) -> Store {
        Store {
            directory: File::open(path).unwrap(),
            owner: unsafe { libc::geteuid() },
            public: false,
        }
    }

    #[test]
    fn publication_replaces_a_symlink_without_touching_its_target() {
        let root = tempfile::tempdir().unwrap();
        let outside = root.path().join("outside");
        std::fs::write(&outside, b"keep").unwrap();
        let directory = root.path().join("cache");
        std::fs::create_dir(&directory).unwrap();
        symlink(&outside, directory.join("status.json")).unwrap();
        let store = temporary(&directory);
        assert!(store.read_status().is_err());
        store.write("status.json", b"{}\n").unwrap();
        assert_eq!(store.read_status().unwrap().unwrap(), b"{}\n");
        assert_eq!(std::fs::read(outside).unwrap(), b"keep");
    }

    #[test]
    fn locking_and_file_boundaries_fail_closed() {
        let root = tempfile::tempdir().unwrap();
        let store = temporary(root.path());
        let lock = store.lock().unwrap();
        assert!(store.lock().is_err());
        assert!(store.try_lock().unwrap().is_none());
        drop(lock);
        assert!(store.try_lock().unwrap().is_some());
        assert!(store.write("../outside", b"bad").is_err());
        symlink("missing", root.path().join("status.json")).unwrap();
        assert!(store.read_status().is_err());
    }
}
