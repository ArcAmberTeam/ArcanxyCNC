//! Local package policy and build origin. Controller quiescence belongs to the updater.
mod client;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::Path;
use std::process::{Command, Stdio};
pub type Result<T> = std::result::Result<T, Box<dyn std::error::Error + Send + Sync>>;
const ORIGIN: &str = "/var/lib/betterlinuxcnc/build-origin.json";
const PACKAGE: &str = "betterlinuxcnc-qt";
const LIMIT: u64 = 256 * 1024 * 1024;

pub(crate) fn command(path: &str) -> Command {
    let mut command = Command::new(path);
    command
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LANG", "C.UTF-8");
    command
}
fn root() -> Result<()> {
    if unsafe { libc::getuid() } != 0 || unsafe { libc::geteuid() } != 0 {
        return Err("Fixed root maintenance service required".into());
    }
    Ok(())
}
fn trusted_directory(path: &Path) -> Result<()> {
    for part in path.ancestors() {
        let info = fs::symlink_metadata(part)?;
        if !info.is_dir() || info.uid() != 0 || info.mode() & 0o022 != 0 {
            return Err("Untrusted maintenance directory".into());
        }
    }
    Ok(())
}
fn query(program: &str, args: &[&str]) -> Result<String> {
    let output = command(program).args(args).stdin(Stdio::null()).output()?;
    if !output.status.success() {
        return Err("Package metadata query failed".into());
    }
    Ok(String::from_utf8(output.stdout)?.trim().to_owned())
}
pub fn installed_version() -> Result<String> {
    query("/usr/bin/dpkg-query", &["-W", "-f=${Version}", PACKAGE])
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Origin {
    schema_version: u32,
    version: String,
    sha256: String,
}
/// Read only the root-owned successful-install record for the actual installed version.
pub fn is_self_compiled(version: &str) -> Result<bool> {
    let path = Path::new(ORIGIN);
    match fs::symlink_metadata(path) {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(false),
        Err(error) => return Err(error.into()),
        Ok(_) => {}
    }
    trusted_directory(path.parent().ok_or("Missing origin parent")?)?;
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)?;
    let info = file.metadata()?;
    if !info.is_file()
        || info.uid() != 0
        || info.mode() & 0o022 != 0
        || info.nlink() != 1
        || info.len() > 4096
    {
        return Err("Untrusted build origin record".into());
    }
    let origin: Origin = serde_json::from_reader(file.take(4097))?;
    if origin.schema_version != 1
        || origin.sha256.len() != 64
        || !origin.sha256.bytes().all(|b| b.is_ascii_hexdigit())
    {
        return Err("Invalid build origin record".into());
    }
    Ok(origin.version == version)
}
fn official_policy(candidate: &str, installed: &str, local: bool) -> Result<bool> {
    for version in [candidate, installed] {
        if version.is_empty()
            || version.len() > 128
            || !version.as_bytes()[0].is_ascii_digit()
            || !version
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b".+:~-".contains(&b))
        {
            return Err("Invalid Debian version".into());
        }
    }
    let result = command("/usr/bin/dpkg")
        .args(["--compare-versions", candidate, "gt", installed])
        .status()?;
    match result.code() {
        Some(0) => Ok(true),
        Some(1) => Ok(local && candidate == installed),
        _ => Err("Version comparison failed".into()),
    }
}
/// Official packages may replace a local build at the same version, never downgrade it.
pub fn accepts_official(candidate: &str, installed: &str) -> Result<bool> {
    official_policy(candidate, installed, is_self_compiled(installed)?)
}
/// Call after a verified official package has installed successfully, before restarting UI.
pub fn clear_origin() -> Result<()> {
    root()?;
    trusted_directory(Path::new(ORIGIN).parent().ok_or("Missing origin parent")?)?;
    match fs::remove_file(ORIGIN) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(error.into()),
    }
}
//--------//
// BEGIN: PreparedLocalPackage
/// Root-owned snapshot of an explicit maintenance upload. No user path reaches APT.
pub struct PreparedLocalPackage {
    file: tempfile::NamedTempFile,
    version: String,
    sha256: String,
}
impl PreparedLocalPackage {
    /// The caller must hold the shared update lock and validate the archive contents next.
    pub fn receive(input: impl Read, cache: &Path) -> Result<Self> {
        root()?;
        trusted_directory(cache)?;
        let mut file = tempfile::Builder::new()
            .prefix("maintenance-")
            .suffix(".deb")
            .tempfile_in(cache)?;
        let size = std::io::copy(&mut input.take(LIMIT + 1), &mut file)?;
        if size == 0 || size > LIMIT {
            return Err("Local package is empty or exceeds 256 MiB".into());
        }
        file.as_file().sync_all()?;
        file.seek(SeekFrom::Start(0))?;
        let mut digest = Sha256::new();
        let mut bytes = [0; 65536];
        loop {
            let count = file.read(&mut bytes)?;
            if count == 0 {
                break;
            }
            digest.update(&bytes[..count]);
        }
        let output = command("/usr/bin/dpkg-deb")
            .args([
                "--show",
                "--showformat=${Package}\n${Version}\n${Architecture}\n",
            ])
            .arg(file.path())
            .output()?;
        if !output.status.success() {
            return Err("Invalid Debian package".into());
        }
        let text = String::from_utf8(output.stdout)?;
        let fields: Vec<_> = text.lines().collect();
        let installed = installed_version()?;
        let arch = query("/usr/bin/dpkg", &["--print-architecture"])?;
        if fields.len() != 3 || fields[0] != PACKAGE || fields[1] != installed || fields[2] != arch
        {
            return Err(
                "Local package must match the installed application name, version and architecture"
                    .into(),
            );
        }
        Ok(Self {
            file,
            version: installed,
            sha256: format!("{:x}", digest.finalize()),
        })
    }
    pub fn path(&self) -> &Path {
        self.file.path()
    }
    pub fn version(&self) -> &str {
        &self.version
    }
    /// Requires successful archive validation, normal controller shutdown and backup.
    pub fn install_after_backup(self) -> Result<()> {
        root()?;
        if installed_version()? != self.version {
            return Err("Installed version changed during preparation".into());
        }
        let output = command("/usr/bin/apt-get")
            .args(["--yes", "--no-remove", "--reinstall", "install"])
            .arg(self.file.path())
            .stdin(Stdio::null())
            .output()?;
        let log_path = self
            .file
            .path()
            .parent()
            .ok_or("Missing cache")?
            .join("local-install.log");
        let mut log = OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW)
            .open(log_path)?;
        log.write_all(&output.stdout)?;
        log.write_all(&output.stderr)?;
        if !output.status.success() || installed_version()? != self.version {
            return Err(
                "Local installation failed; control remains stopped; inspect local-install.log"
                    .into(),
            );
        }
        let parent = Path::new(ORIGIN).parent().ok_or("Missing origin parent")?;
        trusted_directory(parent)?;
        let mut marker = tempfile::NamedTempFile::new_in(parent)?;
        serde_json::to_writer(
            &mut marker,
            &Origin {
                schema_version: 1,
                version: self.version,
                sha256: self.sha256,
            },
        )?;
        marker
            .as_file()
            .set_permissions(fs::Permissions::from_mode(0o644))?;
        marker.as_file().sync_all()?;
        marker.persist(ORIGIN)?;
        File::open(parent)?.sync_all()?;
        Ok(())
    }
}
// END: PreparedLocalPackage
//--------//

pub fn run() -> Result<()> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    client::run(&args)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn official_release_can_replace_same_version_local_build_but_never_downgrade() {
        if !cfg!(target_os = "linux") {
            return;
        }
        assert!(official_policy("26.11.04.7", "26.11.04.6", false).unwrap());
        assert!(official_policy("26.11.04.6", "26.11.04.6", true).unwrap());
        assert!(!official_policy("26.11.04.6", "26.11.04.6", false).unwrap());
        assert!(!official_policy("26.11.04.5", "26.11.04.6", true).unwrap());
        assert!(official_policy("--help", "26.11.04.6", true).is_err());
    }
}
