//! Source checkout and same-version application packaging, always as cnc-maint.
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::fd::AsRawFd;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
const ROOT: &str = "/var/lib/betterlinuxcnc/build";
const REPOSITORY: &str = "https://github.com/ArcAmberTeam/ArcanxyCNC.git";
const MAX_PACKAGE: u64 = 256 * 1024 * 1024;
unsafe extern "C" {
    fn getuid() -> u32;
    fn geteuid() -> u32;
    fn getgid() -> u32;
    fn flock(fd: i32, operation: i32) -> i32;
    fn umask(mask: u32) -> u32;
}
fn command(program: &str) -> Command {
    let mut command = Command::new(program);
    command
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LANG", "C.UTF-8")
        .stdin(Stdio::null());
    command
}
fn identity() -> Result<(u32, u32)> {
    let read = |flag: &str| -> Result<u32> {
        let result = command("/usr/bin/id").args([flag, "cnc-maint"]).output()?;
        if !result.status.success() {
            return Err("Maintenance account unavailable".into());
        }
        Ok(String::from_utf8(result.stdout)?.trim().parse()?)
    };
    let uid = read("-u")?;
    if uid == 0 {
        return Err("Maintenance account cannot be root".into());
    }
    Ok((uid, read("-g")?))
}
fn trusted_parent(path: &Path) -> Result<()> {
    for parent in path.ancestors().skip(1) {
        let info = fs::symlink_metadata(parent)?;
        if !info.is_dir() || info.uid() != 0 || info.mode() & 0o022 != 0 {
            return Err("Untrusted workspace parent".into());
        }
    }
    Ok(())
}
fn workspace() -> Result<()> {
    let (uid, gid) = identity()?;
    if unsafe { getuid() } != uid || unsafe { geteuid() } != uid || unsafe { getgid() } != gid {
        return Err("The cnc-maint OS account is required".into());
    }
    for child in ["src", "work", "packages", "home"] {
        let path = Path::new(ROOT).join(child);
        trusted_parent(&path)?;
        let info = fs::symlink_metadata(path)?;
        if !info.is_dir() || info.uid() != uid || info.mode() & 0o077 != 0 {
            return Err("Workspace directory is not private to cnc-maint".into());
        }
    }
    Ok(())
}
fn process(program: &str) -> Command {
    let mut process = command(program);
    process
        .env("HOME", format!("{ROOT}/home"))
        .env("CARGO_HOME", format!("{ROOT}/home/.cargo"))
        .env("RUSTUP_HOME", format!("{ROOT}/home/.rustup"))
        .env("GIT_CONFIG_NOSYSTEM", "1")
        .env("GIT_CONFIG_GLOBAL", "/dev/null")
        .env("GIT_TERMINAL_PROMPT", "0")
        .env("GIT_ALLOW_PROTOCOL", "https")
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());
    process
}
fn execute(process: &mut Command) -> Result<()> {
    let mut child = process.stderr(Stdio::piped()).spawn()?;
    let mut stderr = child.stderr.take().ok_or("Missing build stderr")?;
    let mut tail = Vec::new();
    let mut buffer = [0u8; 4096];
    loop {
        let size = stderr.read(&mut buffer)?;
        if size == 0 {
            break;
        }
        let _ = io::stderr().write_all(&buffer[..size]);
        tail.extend_from_slice(&buffer[..size]);
        if tail.len() > 8192 {
            tail.drain(..tail.len() - 8192);
        }
    }
    if !child.wait()?.success() {
        betterlinuxcnc_error_client::report(
            "package-build",
            "build_command_failed",
            &String::from_utf8_lossy(&tail),
        );
        return Err("Command failed; see the output above".into());
    }
    Ok(())
}
fn checkout() -> Result<PathBuf> {
    let path = Path::new(ROOT).join("src/ArcanxyCNC");
    let info = fs::symlink_metadata(&path)?;
    if !info.is_dir() || info.uid() != unsafe { getuid() } {
        return Err("Invalid source checkout".into());
    }
    Ok(path)
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
        || info.uid() != unsafe { getuid() }
        || info.nlink() != 1
        || info.len() == 0
        || info.len() > MAX_PACKAGE
    {
        return Err("Invalid local package".into());
    }
    Ok(file)
}
fn build() -> Result<()> {
    let source = checkout()?;
    let installed = process("/usr/bin/dpkg-query")
        .args(["-W", "-f=${Version}", "betterlinuxcnc-qt"])
        .stdout(Stdio::piped())
        .output()?;
    if !installed.status.success() {
        return Err("Application is not installed".into());
    }
    let base_version = String::from_utf8(installed.stdout)?.trim().to_owned();
    // Initialize each pinned toolchain serially before CMake starts concurrent Cargo processes.
    for module in [
        "cam-link",
        "updater",
        "mesa-update",
        "manage-ini",
        "account-management/cnc-maint",
        "package-build",
        "local-update",
        "error-records",
    ] {
        execute(
            process("/usr/bin/cargo")
                .arg("--version")
                .current_dir(source.join("app/platform").join(module)),
        )?;
    }
    // Local application rebuilds retain the installed, already commissioned HOMEMOD.
    execute(process("/usr/bin/python3").args(["-I", "-S", "-c", r#"
import hashlib, json, pathlib, subprocess
module = pathlib.Path('/usr/lib/linuxcnc/modules/zhulong_homing.so')
record = json.loads(pathlib.Path('/usr/share/betterlinuxcnc/homing/provenance.json').read_text())
version = subprocess.check_output(['/usr/bin/dpkg-query', '-W', '-f=${Version}', 'betterlinuxcnc-qt'], text=True)
assert hashlib.sha256(module.read_bytes()).hexdigest() == record['sha256'], 'Installed homing module hash differs'
assert record['application_version'] == version, 'Installed homing provenance version differs'
"#]))?;
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos();
    let work = Path::new(ROOT).join(format!("work/{stamp}"));
    fs::create_dir(&work)?;
    execute(
        process("/usr/bin/cmake")
            .arg("-S")
            .arg(&source)
            .arg("-B")
            .arg(&work)
            .arg(format!("-DBETTERCNC_LOCAL_PACKAGE_VERSION={base_version}"))
            .args([
                "-DCMAKE_BUILD_TYPE=Release",
                "-DBUILD_TESTING=OFF",
                "-DCMAKE_INSTALL_PREFIX:PATH=/usr",
                "-DCMAKE_INSTALL_LIBDIR:STRING=lib",
                "-DBETTERCNC_PROJECT_DIR=/etc/betterlinuxcnc",
                "-DBETTERCNC_BUILD_SYSTEM_SERVICES=ON",
                "-DBETTERCNC_BUILD_MESA_HOMING=OFF",
                "-DBETTERCNC_REUSE_INSTALLED_HOMING=ON",
                "-DPython3_EXECUTABLE=/usr/bin/python3",
            ]),
    )?;
    execute(
        process("/usr/bin/cmake")
            .arg("--build")
            .arg(&work)
            .args(["--parallel", "2"]),
    )?;
    let output = work.join("packages");
    execute(
        process("/usr/bin/cpack")
            .arg("--config")
            .arg(work.join("CPackConfig.cmake"))
            .args(["-G", "DEB", "-B"])
            .arg(&output),
    )?;
    let packages: Vec<_> = fs::read_dir(&output)?
        .collect::<std::io::Result<Vec<_>>>()?
        .into_iter()
        .filter(|entry| entry.path().extension().is_some_and(|ext| ext == "deb"))
        .collect();
    if packages.len() != 1 {
        return Err("Expected exactly one application DEB".into());
    }
    let package = packages[0].path();
    let built = process("/usr/bin/dpkg-deb")
        .args(["-f"])
        .arg(&package)
        .arg("Version")
        .stdout(Stdio::piped())
        .output()?;
    let installed = process("/usr/bin/dpkg-query")
        .args(["-W", "-f=${Version}", "betterlinuxcnc-qt"])
        .stdout(Stdio::piped())
        .output()?;
    if !built.status.success()
        || !installed.status.success()
        || String::from_utf8(built.stdout)?.trim() != String::from_utf8(installed.stdout)?.trim()
    {
        return Err(
            "Build version must match the installed application; version was not changed".into(),
        );
    }
    let name = format!("betterlinuxcnc-local-{stamp}.deb");
    let mut destination = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(Path::new(ROOT).join("packages").join(&name))?;
    io::copy(&mut File::open(package)?, &mut destination)?;
    destination.sync_all()?;
    println!("Built {ROOT}/packages/{name}; version unchanged; not installed");
    Ok(())
}
pub fn run() -> Result<()> {
    // SSH sessions may inherit 0002. System package directories must never be
    // group-writable; the independent installer still validates every entry.
    unsafe { umask(0o022) };
    let args: Vec<_> = std::env::args().skip(1).collect();
    workspace()?;
    let lock = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .custom_flags(0x20000 | 0x800)
        .open(format!("{ROOT}/work/workspace.lock"))?;
    let info = lock.metadata()?;
    if !info.is_file()
        || info.uid() != unsafe { getuid() }
        || info.nlink() != 1
        || unsafe { flock(lock.as_raw_fd(), 2 | 4) } != 0
    {
        return Err("Workspace is busy or its lock is invalid".into());
    }
    let words: Vec<_> = args.iter().map(String::as_str).collect();
    match words.as_slice() {
        ["git", "clone"] | ["git", "clone", REPOSITORY] => execute(
            process("/usr/bin/git")
                .args(["clone", "--", REPOSITORY])
                .arg(format!("{ROOT}/src/ArcanxyCNC")),
        ),
        ["git", "pull"] | ["git", "pull", "--ff-only"] => {
            execute(process("/usr/bin/git").arg("-C").arg(checkout()?).args([
                "pull",
                "--ff-only",
                REPOSITORY,
                "main",
            ]))
        }
        ["build-deb"] => build(),
        ["build-status"] => {
            println!("Workspace: {ROOT}");
            for entry in fs::read_dir(format!("{ROOT}/packages"))? {
                let name = entry?.file_name().to_string_lossy().into_owned();
                if let Ok(file) = package_file(&name) {
                    println!("{name}\t{} bytes", file.metadata()?.len());
                }
            }
            Ok(())
        }
        _ => Err("Supported: git clone [official URL], git pull, build-deb, build-status".into()),
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn package_names_cannot_select_paths_or_options() {
        assert!(valid_filename("betterlinuxcnc-local-123.deb"));
        for name in [
            "../x.deb",
            "/tmp/x.deb",
            "--help",
            ".hidden.deb",
            "x.deb;id",
            "x\ny.deb",
        ] {
            assert!(!valid_filename(name));
        }
    }
}
