use crate::contract::Manifest;
use crate::release::{self, Fetch, OfficialHttp};
use crate::storage::Store;
use crate::Result;
use crate::{guard::Guard, hardware, platform};
use serde::{Deserialize, Serialize};
use std::io::Write;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Status {
    schema_version: u32,
    component: String,
    phase: String,
    message: String,
    updated_unix: u64,
    #[serde(default)]
    host_boot_id: Option<String>,
    installed_app_version: Option<String>,
    available_version: Option<String>,
    app_latest_version: Option<String>,
    mesa_latest_version: Option<String>,
    manifest: Option<Manifest>,
    firmware_downloaded: bool,
    flash_enabled: bool,
}

impl Status {
    fn new(component: &str, phase: &str, message: &str) -> Self {
        Self {
            schema_version: 1,
            component: component.into(),
            phase: phase.into(),
            message: message.into(),
            updated_unix: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
            host_boot_id: None,
            installed_app_version: None,
            available_version: None,
            app_latest_version: None,
            mesa_latest_version: None,
            manifest: None,
            firmware_downloaded: false,
            // UI eligibility is never a substitute for the root maintenance guard.
            flash_enabled: false,
        }
    }

    fn observe_host_boot(&mut self, current: Option<&str>) {
        if self.component != "mesa-flash" || self.phase != "programmed_pending_power_cycle" {
            return;
        }
        let Some((recorded, current)) = self.host_boot_id.as_deref().zip(current) else {
            return;
        };
        if recorded != current
            && platform::valid_boot_id(recorded)
            && platform::valid_boot_id(current)
        {
            self.phase = "host_restarted_board_unconfirmed".into();
            self.message = "The host has restarted since verified flash readback. This does not establish a board power cycle or active firmware version; supervised board acceptance is still required. A new explicit request must pass the complete maintenance guard.".into();
            self.flash_enabled = false;
        }
    }
}

pub(crate) fn update_status() -> Result<()> {
    let uid = platform::require_operator()?;
    show_status(Store::user(uid, false)?, "mesa-update")
}

pub(crate) fn flash_status() -> Result<()> {
    let root = Store::root_state(false)?;
    // Only the operating user's own process inspects its request marker. The
    // root service never reads this cache or uses it as authorization.
    if let Ok(uid) = platform::operating_user() {
        if unsafe { libc::geteuid() } == uid {
            if let Some(cache) = Store::user(uid, false)? {
                if let Some(requested) = cache.modified("flash-request.json")? {
                    let published = root
                        .as_ref()
                        .map(|store| store.modified("status.json"))
                        .transpose()?
                        .flatten();
                    if published.is_none_or(|published| published < requested) {
                        let active = flash_unit_state()?;
                        return print_status(&Status::new("mesa-flash", if active == "inactive" || active == "failed" { "error" } else { "scheduled" }, "Waiting for the requested root Mesa service; an older result is not this request's outcome"));
                    }
                }
            }
        }
    }
    show_status(root, "mesa-flash")
}

const FLASH_UNIT: &str = "betterlinuxcnc-mesa-flash.service";

fn flash_unit_state() -> Result<String> {
    let output = platform::command("/usr/bin/systemctl")
        .args([
            "--system",
            "--no-ask-password",
            "show",
            "--property=ActiveState",
            "--value",
            FLASH_UNIT,
        ])
        .output()?;
    let state = String::from_utf8(output.stdout)?.trim().to_owned();
    if !output.status.success()
        || !matches!(
            state.as_str(),
            "active" | "activating" | "deactivating" | "inactive" | "failed"
        )
    {
        return Err("Cannot establish the root Mesa service state".into());
    }
    Ok(state)
}

pub(crate) fn request() -> Result<()> {
    let uid = platform::require_operator()?;
    if !matches!(flash_unit_state()?.as_str(), "inactive" | "failed") {
        return Err("The root Mesa service is already running".into());
    }
    let cache = Store::user(uid, true)?.ok_or("Missing Mesa request cache")?;
    let _lock = cache.lock()?;
    let pending = Status::new("mesa-flash", "scheduled", "Requested the fixed root Mesa service; root will independently verify firmware and machine safety");
    cache.write("flash-request.json", &serde_json::to_vec(&pending)?)?;
    let output = request_command().output()?;
    if !output.status.success() {
        return Err("The fixed Mesa service request was refused".into());
    }
    print_status(&pending)
}

fn request_command() -> std::process::Command {
    let mut command = platform::command("/usr/bin/systemctl");
    command.args([
        "--system",
        "--no-ask-password",
        "--no-block",
        "start",
        FLASH_UNIT,
    ]);
    command
}

fn show_status(store: Option<Store>, component: &str) -> Result<()> {
    // Hold the operation lock through the read and response when it is free.
    // A new check cannot race a stale record into an apparent active operation.
    let observation_lock = if component == "mesa-update" {
        store.as_ref().map(Store::try_lock).transpose()?.flatten()
    } else {
        None
    };
    let mut status = match store
        .as_ref()
        .map(|store| store.read_status())
        .transpose()?
        .flatten()
    {
        Some(bytes) => {
            let status: Status = serde_json::from_slice(&bytes)?;
            if status.schema_version != 1 || status.component != component {
                return Err("Unsupported Mesa status record".into());
            }
            status
        }
        None => Status::new(component, "not_checked", "No Mesa operation has completed"),
    };
    observe_interrupted_check(&mut status, observation_lock.is_some());
    if component == "mesa-flash"
        && matches!(
            status.phase.as_str(),
            "checking" | "verified" | "verifying_identity" | "writing" | "verifying"
        )
        && matches!(flash_unit_state()?.as_str(), "inactive" | "failed")
    {
        status.phase = "error".into();
        status.message = "The root Mesa operation stopped without a completed readback; inspect maintenance logs before restoring control".into();
        status.flash_enabled = false;
    }
    if component == "mesa-flash" && status.phase == "programmed_pending_power_cycle" {
        // This is an observation only: retain the original operation record,
        // including its firmware manifest, version, time and writing boot ID.
        status.observe_host_boot(platform::host_boot_id().ok().as_deref());
    }
    print_status(&status)
}

fn observe_interrupted_check(status: &mut Status, lock_acquired: bool) {
    if status.component == "mesa-update" && status.phase == "checking" && lock_acquired {
        status.phase = "error".into();
        status.message = "The previous Mesa check was interrupted; run Check again".into();
        status.flash_enabled = false;
    }
}

pub(crate) fn check() -> Result<()> {
    let uid = platform::require_operator()?;
    let store = Store::user(uid, true)?.ok_or("Missing Mesa download cache")?;
    let _lock = store.lock()?;
    operation(&store, "mesa-update", || {
        let installed = platform::installed_version()?;
        check_with(&OfficialHttp::new()?, &installed)
    })
}

fn check_with(fetch: &impl Fetch, installed: &str) -> Result<Status> {
    let (app, mesa) = release::latest_pair(fetch)?;
    let paired = app == mesa.manifest.compatible_app_version;
    let mut status = if !paired {
        Status::new(
            "mesa-update",
            "version_mismatch",
            "Latest application and Mesa releases are not paired",
        )
    } else if !mesa.manifest.firmware.available {
        Status::new(
            "mesa-update",
            "source_only",
            "Paired source update is published; no verified firmware is available",
        )
    } else {
        Status::new("mesa-update", "release_available", "Paired verified firmware is published; download requires its application version to be installed")
    };
    status.installed_app_version = Some(installed.into());
    status.available_version = paired.then(|| app.clone());
    status.app_latest_version = Some(app);
    status.mesa_latest_version = Some(mesa.manifest.version.clone());
    status.flash_enabled =
        paired && mesa.manifest.version == installed && mesa.manifest.firmware.available;
    status.manifest = Some(mesa.manifest);
    Ok(status)
}

pub(crate) fn download() -> Result<()> {
    let uid = platform::require_operator()?;
    let store = Store::user(uid, true)?.ok_or("Missing Mesa download cache")?;
    let _lock = store.lock()?;
    operation(&store, "mesa-update", || {
        let installed = platform::installed_version()?;
        verify_download(&OfficialHttp::new()?, &installed, false, |bytes| {
            store.write("firmware.bit", bytes)
        })
    })
}

pub(crate) fn apply_system() -> Result<()> {
    platform::require_root()?;
    let state = Store::root_state(true)?.ok_or("Missing Mesa flash state directory")?;
    let _request_lock = state.lock()?;
    let pending = Status::new("mesa-flash", "checking", "Root Mesa maintenance is checking the installed version, official firmware and machine state");
    state.write("status.json", &serde_json::to_vec(&pending)?)?;
    platform::trusted_file(Path::new("/usr/bin/betterlinuxcnc-updater"), false)?;
    let result = platform::command("/usr/bin/betterlinuxcnc-updater")
        .arg("mesa-maintenance")
        .status();
    if !result.is_ok_and(|status| status.success()) {
        let previous: Option<Status> = state
            .read_status()?
            .map(|bytes| serde_json::from_slice(&bytes))
            .transpose()?;
        if !previous
            .as_ref()
            .is_some_and(|status| matches!(status.phase.as_str(), "blocked" | "error"))
        {
            let error = Status::new("mesa-flash", "error", "Mesa maintenance failed or was refused; no automatic controller restart is performed");
            state.write("status.json", &serde_json::to_vec(&error)?)?;
        }
        return Err("Mesa maintenance failed; inspect its root status and logs".into());
    }
    show_status(Some(state), "mesa-flash")
}

pub(crate) fn prepare_system() -> Result<()> {
    platform::require_root()?;
    let cache = Store::root_cache()?;
    let _lock = cache.lock()?;
    let state = Store::root_state(true)?.ok_or("Missing Mesa flash state directory")?;
    let mut available = false;
    operation(&state, "mesa-flash", || {
        let installed = platform::installed_version()?;
        let status = verify_download(&OfficialHttp::new()?, &installed, true, |bytes| {
            cache.write("firmware.bit", bytes)
        })?;
        available = status.firmware_downloaded;
        Ok(status)
    })?;
    if available {
        Ok(())
    } else {
        Err("No verified firmware exists; flashing is blocked".into())
    }
}

pub(crate) fn write_system() -> Result<()> {
    let mut guard = Guard::inherited()?;
    let cache = Store::root_cache()?;
    let _lock = cache.lock()?;
    let state = Store::root_state(true)?.ok_or("Missing Mesa flash state directory")?;
    operation(&state, "mesa-flash", || {
        let installed = platform::installed_version()?;
        if installed != guard.version() {
            return Err("Application version changed during Mesa maintenance".into());
        }
        let mut status = verify_download(&OfficialHttp::new()?, &installed, true, |bytes| {
            cache.write("firmware.bit", bytes)
        })?;
        if !status.firmware_downloaded {
            return Err(
                "Firmware disappeared or is no longer verified; control remains stopped".into(),
            );
        }
        // Obtain a trustworthy host identity before any hardware access, so a
        // later host reboot cannot be mistaken for board firmware activation.
        status.host_boot_id = Some(platform::host_boot_id()?);
        hardware::write_and_verify(
            Path::new("/var/cache/betterlinuxcnc/mesa-flash/firmware.bit"),
            |step| {
                guard.authorize(step)?;
                status.phase = match step {
                    "probe" => "verifying_identity",
                    "write" => "writing",
                    _ => "verifying",
                }
                .into();
                status.flash_enabled = false;
                state.write("status.json", &serde_json::to_vec(&status)?)
            },
            |step, log| cache.write(&format!("{step}.log"), log),
        )?;
        status.phase = "programmed_pending_power_cycle".into();
        status.message = "Firmware flash readback verified. The card was not reloaded; control remains stopped and masked until a supervised power cycle and acceptance.".into();
        Ok(status)
    })
}

fn verify_download(
    fetch: &impl Fetch,
    installed: &str,
    root: bool,
    mut save: impl FnMut(&[u8]) -> Result<()>,
) -> Result<Status> {
    // Both processes construct a fresh official release request. The root path
    // accepts neither a manifest nor a bitstream from the operating account.
    let release = release::installed_release(fetch, installed)?;
    let bytes = release::firmware(fetch, &release)?;
    let downloaded = if let Some(bytes) = bytes {
        hardware::validate_bit(&bytes)?;
        save(&bytes)?;
        true
    } else {
        false
    };
    let (phase, message) = if root {
        if downloaded {
            ("verified", "Root independently verified the firmware; hardware access still requires the live maintenance guard")
        } else {
            (
                "blocked",
                "No verified firmware exists for this application version; flashing is forbidden",
            )
        }
    } else if downloaded {
        (
            "downloaded",
            "Firmware hash and version verified in the user cache; the board has not been flashed",
        )
    } else {
        (
            "firmware_unavailable",
            "Source release exists, but there is no verified firmware to download or flash",
        )
    };
    let mut status = Status::new(
        if root { "mesa-flash" } else { "mesa-update" },
        phase,
        message,
    );
    status.installed_app_version = Some(installed.into());
    status.available_version = Some(release.manifest.version.clone());
    status.firmware_downloaded = downloaded;
    status.flash_enabled = downloaded && !root;
    status.manifest = Some(release.manifest);
    Ok(status)
}

fn operation(store: &Store, component: &str, run: impl FnOnce() -> Result<Status>) -> Result<()> {
    let pending = Status::new(
        component,
        "checking",
        "Fetching official version-paired Mesa metadata",
    );
    store.write("status.json", &serde_json::to_vec(&pending)?)?;
    match run() {
        Ok(status) => {
            store.write("status.json", &serde_json::to_vec(&status)?)?;
            print_status(&status)
        }
        Err(error) => {
            let status = Status::new(component, "error", &error.to_string());
            store.write("status.json", &serde_json::to_vec(&status)?)?;
            print_status(&status)?;
            Err(error)
        }
    }
}

fn print_status(status: &Status) -> Result<()> {
    let mut stdout = std::io::stdout().lock();
    serde_json::to_writer(&mut stdout, status)?;
    writeln!(stdout)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contract;
    use std::cell::RefCell;

    const WRITING_BOOT: &str = "c6076b8e-a07e-4c6d-93a1-0b1f99551b63";
    const LATER_BOOT: &str = "83900f86-d894-4e74-9cc4-23167314e1e9";

    #[test]
    fn interrupted_check_is_distinct_from_an_active_check_or_flash() {
        let mut status = Status::new("mesa-update", "checking", "pending");
        let timestamp = status.updated_unix;
        observe_interrupted_check(&mut status, false);
        assert_eq!(status.phase, "checking");
        observe_interrupted_check(&mut status, true);
        assert_eq!(status.phase, "error");
        assert_eq!(status.updated_unix, timestamp);
        assert!(!status.flash_enabled);
        let mut flash = Status::new("mesa-flash", "checking", "pending");
        observe_interrupted_check(&mut flash, true);
        assert_eq!(flash.phase, "checking");
    }

    #[test]
    fn host_restart_derives_an_unconfirmed_view_without_changing_operation_evidence() {
        let mut status = Status::new("mesa-flash", "programmed_pending_power_cycle", "pending");
        status.host_boot_id = Some(WRITING_BOOT.into());
        status.installed_app_version = Some("26.10.26.1".into());
        status.available_version = Some("26.10.26.1".into());
        let mut manifest = contract::fixture();
        manifest.firmware.sha256 = Some("a".repeat(64));
        status.manifest = Some(manifest);
        status.firmware_downloaded = true;
        let persisted = serde_json::to_vec(&status).unwrap();
        let original = serde_json::to_value(&status).unwrap();

        status.observe_host_boot(Some(LATER_BOOT));

        let mut observed = serde_json::to_value(&status).unwrap();
        assert_eq!(observed["phase"], "host_restarted_board_unconfirmed");
        assert!(!status.flash_enabled);
        assert!(status.message.contains("does not establish"));
        observed["phase"] = original["phase"].clone();
        observed["message"] = original["message"].clone();
        assert_eq!(observed, original);
        let record: Status = serde_json::from_slice(&persisted).unwrap();
        assert_eq!(record.phase, "programmed_pending_power_cycle");
        assert_eq!(record.host_boot_id.as_deref(), Some(WRITING_BOOT));
    }

    #[test]
    fn absent_invalid_or_unchanged_boot_evidence_keeps_pending() {
        for (recorded, current) in [
            (Some(WRITING_BOOT), Some(WRITING_BOOT)),
            (Some(WRITING_BOOT), None),
            (None, Some(LATER_BOOT)),
            (Some("invalid"), Some(LATER_BOOT)),
            (Some(WRITING_BOOT), Some("invalid")),
        ] {
            let mut status = Status::new("mesa-flash", "programmed_pending_power_cycle", "pending");
            status.host_boot_id = recorded.map(str::to_owned);
            let original = serde_json::to_vec(&status).unwrap();
            status.observe_host_boot(current);
            assert_eq!(serde_json::to_vec(&status).unwrap(), original);
        }
        let status = Status::new("mesa-flash", "programmed_pending_power_cycle", "legacy");
        let mut legacy = serde_json::to_value(status).unwrap();
        legacy.as_object_mut().unwrap().remove("host_boot_id");
        let mut parsed: Status = serde_json::from_value(legacy).unwrap();
        parsed.observe_host_boot(Some(LATER_BOOT));
        assert_eq!(parsed.phase, "programmed_pending_power_cycle");
    }

    #[test]
    fn host_restart_never_upgrades_incomplete_or_user_operations() {
        for (component, phase) in [
            ("mesa-flash", "writing"),
            ("mesa-flash", "verifying"),
            ("mesa-flash", "error"),
            ("mesa-update", "programmed_pending_power_cycle"),
        ] {
            let mut status = Status::new(component, phase, "unchanged");
            status.host_boot_id = Some(WRITING_BOOT.into());
            let original = serde_json::to_vec(&status).unwrap();
            status.observe_host_boot(Some(LATER_BOOT));
            assert_eq!(serde_json::to_vec(&status).unwrap(), original);
        }
    }

    #[test]
    fn request_only_starts_the_fixed_unit_with_a_clean_environment() {
        let command = request_command();
        assert_eq!(command.get_program(), "/usr/bin/systemctl");
        assert_eq!(
            command.get_args().collect::<Vec<_>>(),
            [
                "--system",
                "--no-ask-password",
                "--no-block",
                "start",
                "betterlinuxcnc-mesa-flash.service"
            ]
        );
        assert!(command.get_envs().all(|(name, _)| ["PATH", "HOME", "LANG"]
            .iter()
            .any(|allowed| name == *allowed)));
    }

    struct SourceRelease {
        calls: RefCell<Vec<String>>,
    }

    impl Fetch for SourceRelease {
        fn get(&self, url: &str, _limit: u64) -> Result<Vec<u8>> {
            self.calls.borrow_mut().push(url.into());
            let manifest = contract::fixture();
            if url.ends_with("/mesa-release.json") {
                return Ok(serde_json::to_vec(&manifest)?);
            }
            if url.contains("/git/ref/tags/") {
                return Ok(serde_json::to_vec(&serde_json::json!({
                    "object": {"type": "commit", "sha": manifest.source_commit},
                }))?);
            }
            if url.contains("/releases/") {
                let mut assets = vec![serde_json::json!({
                    "name": "mesa-release.json", "size": serde_json::to_vec(&manifest)?.len(),
                    "browser_download_url": "https://github.com/ArcAmberTeam/CNC-Mesa/releases/download/v26.10.26.1/mesa-release.json",
                })];
                for artifact in [&manifest.artifacts.source, &manifest.artifacts.integration] {
                    assets.push(serde_json::json!({
                        "name": artifact.asset, "size": artifact.size_bytes,
                        "browser_download_url": format!("https://github.com/ArcAmberTeam/CNC-Mesa/releases/download/v26.10.26.1/{}", artifact.asset),
                    }));
                }
                return Ok(serde_json::to_vec(&serde_json::json!({
                    "tag_name": "v26.10.26.1", "draft": false, "prerelease": false, "assets": assets,
                }))?);
            }
            Err("Unexpected network request".into())
        }
    }

    #[test]
    fn root_refetches_metadata_and_cannot_flash_a_source_only_release() {
        let fetch = SourceRelease {
            calls: RefCell::new(Vec::new()),
        };
        let user = verify_download(&fetch, "26.10.26.1", false, |_| {
            panic!("No firmware exists")
        })
        .unwrap();
        let user_calls = fetch.calls.borrow().len();
        let root =
            verify_download(&fetch, "26.10.26.1", true, |_| panic!("No firmware exists")).unwrap();
        assert_eq!(fetch.calls.borrow().len(), user_calls * 2);
        assert_eq!(user.phase, "firmware_unavailable");
        assert_eq!(root.phase, "blocked");
        assert!(!root.flash_enabled);
        assert!(!root.firmware_downloaded);
        let check = check_with(&fetch, "26.10.25.1").unwrap();
        assert_eq!(check.phase, "source_only");
        assert_eq!(check.available_version.as_deref(), Some("26.10.26.1"));
    }
}
