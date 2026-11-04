//! Fixed system-service boundary. No user supplied package, URL, or command enters root work.
use super::{
    install, package, release,
    storage::{self, Store},
    system::{Manager, PausedLauncher, UnitState, UPDATE_UNIT},
    Event, Result,
};
use serde::Deserialize;
use std::{
    ffi::{CStr, CString},
    fs::{self, OpenOptions},
    io::Read,
    os::unix::fs::{DirBuilderExt, FileTypeExt, MetadataExt, OpenOptionsExt, PermissionsExt},
    path::{Path, PathBuf},
};

const CONFIG: &str = "/etc/betterlinuxcnc/updater.json";
const CACHE: &str = "/var/cache/betterlinuxcnc/update";
const PUBLIC: &str = "/var/lib/betterlinuxcnc/update";

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Config {
    user: String,
    config: PathBuf,
}

fn validate_config(config: &Config) -> Result<()> {
    if config.user != "linuxcnc" || config.config != Path::new("/etc/betterlinuxcnc/launcher.json")
    {
        return Err("系统更新仅允许固定 linuxcnc 账户及系统机床配置".into());
    }
    Ok(())
}

fn secure_directory(path: &Path, owner: u32, create: bool, mode: u32) -> Result<()> {
    if !path.is_absolute() {
        return Err("系统更新目录必须是绝对路径".into());
    }
    let mut current = PathBuf::new();
    for component in path.components() {
        if !matches!(
            component,
            std::path::Component::RootDir | std::path::Component::Normal(_)
        ) {
            return Err("系统更新路径包含非法组成部分".into());
        }
        current.push(component);
        if create && !current.try_exists()? {
            fs::DirBuilder::new()
                .mode(if current == path { mode } else { 0o755 })
                .create(&current)?;
        }
        let info = fs::symlink_metadata(&current)?;
        if !info.is_dir() || info.uid() != owner || info.mode() & 0o022 != 0 {
            return Err(format!(
                "系统更新目录必须由 root 拥有且不可由其他用户写入：{}",
                current.display()
            )
            .into());
        }
    }
    Ok(())
}

fn trusted_read(path: &Path) -> Result<Vec<u8>> {
    secure_directory(path.parent().ok_or("系统文件路径无效")?, 0, false, 0o755)?;
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW)
        .open(path)?;
    let info = file.metadata()?;
    if !info.is_file() || info.uid() != 0 || info.mode() & 0o022 != 0 || info.len() > 65536 {
        return Err("系统更新配置或状态文件不可信".into());
    }
    let mut body = Vec::new();
    file.take(65537).read_to_end(&mut body)?;
    if body.len() > 65536 {
        return Err("系统更新记录过大".into());
    }
    Ok(body)
}

fn uid(user: &str) -> Result<u32> {
    let name = CString::new(user)?;
    let entry = unsafe { libc::getpwnam(name.as_ptr()) };
    if entry.is_null() {
        return Err("系统更新操作账户不存在".into());
    }
    let entry = unsafe { &*entry };
    if entry.pw_uid == 0 || unsafe { CStr::from_ptr(entry.pw_name) }.to_bytes() != user.as_bytes() {
        return Err("系统更新操作账户无效".into());
    }
    Ok(entry.pw_uid)
}

fn runtime(uid: u32) -> Result<PathBuf> {
    let directory = PathBuf::from(format!("/run/user/{uid}"));
    let info = fs::symlink_metadata(&directory)?;
    let bus = fs::symlink_metadata(directory.join("bus"))?;
    if !info.is_dir()
        || info.uid() != uid
        || info.mode() & 0o077 != 0
        || !bus.file_type().is_socket()
        || bus.uid() != uid
    {
        return Err("操作账户未建立可信的图形用户会话，未执行安装".into());
    }
    Ok(directory.join("betterlinuxcnc/control.sock"))
}

pub(super) fn root_store() -> Result<Store> {
    secure_directory(Path::new(CACHE), 0, true, 0o700)?;
    secure_directory(Path::new(PUBLIC), 0, true, 0o755)?;
    fs::set_permissions(CACHE, fs::Permissions::from_mode(0o700))?;
    Ok(Store {
        directory: CACHE.into(),
        public_directory: Some(PUBLIC.into()),
    })
}

pub(super) fn machine_context() -> Result<(Manager, PathBuf, u32)> {
    let config: Config = serde_json::from_slice(&trusted_read(Path::new(CONFIG))?)?;
    validate_config(&config)?;
    let _launcher_config = trusted_read(&config.config)?;
    let uid = uid(&config.user)?;
    let socket = runtime(uid)?;
    Ok((Manager::account(&config.user, uid), socket, uid))
}

pub(super) fn apply() -> Result<()> {
    if !cfg!(target_os = "linux") || unsafe { libc::geteuid() } != 0 {
        return Err("系统更新仅能由固定 root systemd 服务执行".into());
    }
    // All child processes receive a clean environment; network transport ignores proxies.
    let store = root_store()?;
    let _lock = store.lock()?;
    let result = apply_locked(&store);
    if let Err(error) = &result {
        let _ = store.publish(&Event::new("error", error.to_string(), "", 0));
    }
    result
}

fn apply_locked(store: &Store) -> Result<()> {
    store.publish(&Event::new(
        "installing",
        "系统更新服务正在独立验证正式 Release…",
        "",
        0,
    ))?;
    let (manager, socket, uid) = machine_context()?;
    install::preflight(&socket, &manager, uid)?;
    // Never use a user's downloaded payload or manifest, even when the GUI says ready.
    release::fetch(store, "0")?;
    if store.status()?.phase != "ready" {
        return Ok(());
    }
    let staged = store.staged()?;
    let package = store.directory.join("package.deb");
    verify_package(&package, &staged)?;
    package::validate(&package)?;
    let original = install::preflight(&socket, &manager, uid)?;
    store.publish(&Event::new(
        "installing",
        "正在正常停止控制系统、备份配置并安装已验证更新…",
        &staged.version,
        100,
    ))?;
    let launcher = PausedLauncher::stop(manager, original)?;
    if install::present(&socket)? || install::present(Path::new("/tmp/linuxcnc.lock"))? {
        return Err("控制系统仍在运行，未安装更新，请检查启动器日志".into());
    }
    // Root-only directories cannot be renamed or modified by the operator during apt.
    store.staged()?;
    verify_package(&package, &staged)?;
    let output = install_with_backup(&package, std::process::Command::output)?;
    let mut log = output.stdout;
    log.extend_from_slice(&output.stderr);
    let mut file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .mode(0o600)
        .custom_flags(libc::O_NOFOLLOW)
        .open(store.directory.join("install.log"))?;
    std::io::Write::write_all(&mut file, &log)?;
    if !output.status.success() {
        return Err("安装失败；控制系统保持停止，请管理员检查系统更新日志".into());
    }
    if storage::installed_version("0")? != staged.version {
        return Err("安装后版本核验不符；控制系统保持停止".into());
    }
    betterlinuxcnc_local_update::clear_origin()?;
    launcher
        .resume()
        .map_err(|error| format!("更新已安装，但控制系统恢复失败：{error}"))?;
    store.publish(&Event::new(
        "complete",
        format!("已更新至 {}", staged.version),
        &staged.version,
        100,
    ))
}

fn install_with_backup(
    package: &Path,
    mut execute: impl FnMut(&mut std::process::Command) -> std::io::Result<std::process::Output>,
) -> Result<std::process::Output> {
    let mut backup = super::command("/usr/sbin/betterlinuxcnc-appliance");
    backup.arg("backup");
    let output =
        execute(&mut backup).map_err(|error| format!("创建更新前备份失败，未安装更新：{error}"))?;
    if !output.status.success() {
        let detail: String = String::from_utf8_lossy(&output.stderr)
            .chars()
            .take(512)
            .collect();
        return Err(format!("创建更新前备份失败，未安装更新：{}", detail.trim()).into());
    }
    let mut install = super::command("/usr/bin/apt-get");
    install
        .args(["--yes", "--no-remove", "--reinstall", "install"])
        .arg(package);
    Ok(execute(&mut install)?)
}

fn verify_package(path: &Path, staged: &storage::Staged) -> Result<()> {
    let (version, architecture) = storage::package_info(path)?;
    if version != staged.version
        || architecture != staged.architecture
        || architecture != install::architecture()?
    {
        return Err("系统缓存安装包的版本或架构不符".into());
    }
    if !betterlinuxcnc_local_update::accepts_official(&version, &storage::installed_version("0")?)?
    {
        return Err("拒绝安装相同或更低版本".into());
    }
    Ok(())
}

pub(super) fn schedule(store: &Store) -> Result<()> {
    if !cfg!(target_os = "linux") {
        return Err("系统更新仅支持 Debian".into());
    }
    let config: Config = serde_json::from_slice(&trusted_read(Path::new(CONFIG))?)?;
    validate_config(&config)?;
    if unsafe { libc::getuid() } != uid(&config.user)? {
        return Err("当前账户没有系统更新权限".into());
    }
    let manager = Manager::system();
    if !matches!(manager.state(UPDATE_UNIT)?, UnitState::Stopped) {
        return Err("系统更新服务不可用或已有更新正在执行".into());
    }
    // Persist before dispatch: the root worker can finish before systemctl returns.
    let pending = Event::new(
        "scheduled",
        "已请求系统更新；系统服务将独立下载并验证正式 Release",
        "",
        0,
    );
    store.save("status.json", &pending)?;
    // No path, version, URL, or package option crosses this privilege boundary.
    manager.control(&["--no-block", "start", UPDATE_UNIT])?;
    pending.emit()
}

pub(super) fn visible_status(local: &Store) -> Result<Option<Event>> {
    let path = Path::new(PUBLIC).join("status.json");
    let local_status = local.status()?;
    let scheduled = matches!(local_status.phase.as_str(), "scheduled" | "installing");
    if !install::present(&path)? {
        return if scheduled {
            Ok(Some(if running()? {
                Event::new("scheduled", "等待系统更新服务…", "", 0)
            } else {
                Event::new("error", "系统更新服务未完成请求，请查看系统日志", "", 0)
            }))
        } else {
            Ok(None)
        };
    }
    let public: Event = serde_json::from_slice(&trusted_read(&path)?)?;
    if running()? {
        return Ok(Some(if public.phase == "installing" {
            public
        } else {
            Event::new("installing", "系统更新正在准备或完成收尾…", "", 0)
        }));
    }
    let public_time = fs::metadata(&path)?.modified()?;
    let local_time = fs::metadata(local.directory.join("status.json"))
        .and_then(|m| m.modified())
        .ok();
    if local_time.is_some_and(|time| time > public_time) {
        return if scheduled {
            Ok(Some(Event::new(
                "error",
                "系统更新服务未完成请求，请查看系统日志",
                "",
                0,
            )))
        } else {
            Ok(None)
        };
    }
    if matches!(public.phase.as_str(), "scheduled" | "installing") {
        return Ok(Some(Event::new(
            "error",
            "系统更新已中断，请管理员检查更新日志",
            "",
            0,
        )));
    }
    Ok(Some(public))
}

fn running() -> Result<bool> {
    Ok(matches!(
        Manager::system().state(UPDATE_UNIT)?,
        UnitState::Running | UnitState::Transition
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::process::ExitStatusExt;

    #[test]
    fn backup_must_succeed_before_the_fixed_install_command() {
        let package = Path::new("/var/cache/betterlinuxcnc/update/package.deb");
        for backup_succeeds in [false, true] {
            let mut calls = Vec::new();
            let result = install_with_backup(package, |command| {
                calls.push((
                    command.get_program().to_str().unwrap().to_owned(),
                    command
                        .get_args()
                        .map(|arg| arg.to_str().unwrap().to_owned())
                        .collect::<Vec<_>>(),
                ));
                assert!(command
                    .get_envs()
                    .all(|(key, _)| key == "PATH" || key == "LANG"));
                Ok(std::process::Output {
                    status: std::process::ExitStatus::from_raw(if backup_succeeds {
                        0
                    } else {
                        1 << 8
                    }),
                    stdout: Vec::new(),
                    stderr: b"snapshot fixture failed".to_vec(),
                })
            });
            assert_eq!(result.is_ok(), backup_succeeds);
            assert_eq!(calls[0].0, "/usr/sbin/betterlinuxcnc-appliance");
            assert_eq!(calls[0].1, ["backup"]);
            assert_eq!(calls.len(), if backup_succeeds { 2 } else { 1 });
            if backup_succeeds {
                assert_eq!(calls[1].0, "/usr/bin/apt-get");
                assert_eq!(
                    calls[1].1,
                    [
                        "--yes",
                        "--no-remove",
                        "--reinstall",
                        "install",
                        package.to_str().unwrap()
                    ]
                );
            }
        }
    }

    #[test]
    fn inability_to_start_backup_prevents_installation() {
        let mut calls = 0;
        let result = install_with_backup(Path::new("/unused/package.deb"), |_| {
            calls += 1;
            Err(std::io::Error::from(std::io::ErrorKind::NotFound))
        });
        assert!(result.is_err());
        assert_eq!(calls, 1);
    }

    #[test]
    fn rejects_untrusted_configuration_and_extra_inputs() {
        for source in [
            r#"{"user":"root","config":"/etc/betterlinuxcnc/launcher.json"}"#,
            r#"{"user":"linuxcnc","config":"/home/linuxcnc/launcher.json"}"#,
        ] {
            assert!(validate_config(&serde_json::from_str(source).unwrap()).is_err());
        }
        assert!(serde_json::from_str::<Config>(r#"{"user":"linuxcnc","config":"/etc/betterlinuxcnc/launcher.json","package":"/tmp/pwn.deb"}"#).is_err());
        validate_config(
            &serde_json::from_str(
                r#"{"user":"linuxcnc","config":"/etc/betterlinuxcnc/launcher.json"}"#,
            )
            .unwrap(),
        )
        .unwrap();
    }
    #[test]
    fn refuses_nonroot_and_writable_system_files() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("updater.json");
        fs::write(&path, "{}").unwrap();
        assert!(trusted_read(&path).is_err()); // temp ancestors are user owned or world writable.
        let link = directory.path().join("link");
        std::os::unix::fs::symlink(&path, &link).unwrap();
        assert!(trusted_read(&link).is_err());
    }
}
