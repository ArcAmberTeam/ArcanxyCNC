mod broker;
mod install;
mod maintenance;
mod package;
mod release;
mod storage;
mod system;

use clap::{Parser, Subcommand};
use serde::{Deserialize, Serialize};
use std::{io::Write, path::Path};

type Result<T> = std::result::Result<T, Box<dyn std::error::Error + Send + Sync>>;
const PACKAGE: &str = "betterlinuxcnc-qt";
const REPOSITORY: &str = "ArcAmberTeam/ArcanxyCNC";

#[derive(Parser)]
#[command(
    name = "betterlinuxcnc-updater",
    version,
    about = "Verified GitHub Release updates"
)]
struct Options {
    #[command(subcommand)]
    command: Action,
}

#[derive(Subcommand)]
enum Action {
    /// Check the latest stable release, download and verify the matching Debian package.
    Fetch {
        #[arg(long)]
        current_version: String,
    },
    /// Read persistent update status. No network, controller or package-manager access.
    Status,
    /// Start the fixed privileged system update service. No package inputs are accepted.
    Install,
    #[command(hide = true)]
    ApplySystem,
    /// Fixed root-only guard for the independent Mesa flashing process.
    #[command(hide = true)]
    MesaMaintenance,
    /// Fixed root-only guard for automatically writing the machine axis count.
    #[command(hide = true)]
    AxisMaintenance {
        #[arg(value_parser = clap::value_parser!(u8).range(3..=5))]
        axes: u8,
    },
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Event {
    phase: String,
    message: String,
    #[serde(default)]
    version: String,
    #[serde(default)]
    progress: u8,
}

impl Event {
    fn new(phase: &str, message: impl Into<String>, version: &str, progress: u8) -> Self {
        Self {
            phase: phase.into(),
            message: message.into(),
            version: version.into(),
            progress,
        }
    }
    fn emit(&self) -> Result<()> {
        println!("{}", serde_json::to_string(self)?);
        std::io::stdout().flush()?;
        Ok(())
    }
}

pub(super) fn run() -> Result<()> {
    let options = Options::parse();
    if matches!(options.command, Action::ApplySystem) {
        return broker::apply();
    }
    if matches!(options.command, Action::MesaMaintenance) {
        return maintenance::run();
    }
    if let Action::AxisMaintenance { axes } = options.command {
        return maintenance::run_axes(axes);
    }
    let store = storage::Store::open()?;
    if matches!(options.command, Action::Status) {
        if let Some(status) = broker::visible_status(&store)? {
            return status.emit();
        }
        let status = store.status()?;
        if transient(&status) {
            if let Ok(_lock) = store.lock() {
                let latest = store.status()?;
                return if transient(&latest) {
                    Event::new("error", "上次更新已中断，请检查安装日志或重新下载", "", 0).emit()
                } else {
                    latest.emit()
                };
            }
        }
        return status.emit();
    }
    let result = match options.command {
        Action::Fetch { current_version } => {
            let _lock = store.lock()?;
            release::fetch(&store, &current_version)
        }
        Action::Install => {
            let _lock = store.lock()?;
            broker::schedule(&store)
        }
        Action::ApplySystem => unreachable!(),
        Action::MesaMaintenance => unreachable!(),
        Action::AxisMaintenance { .. } => unreachable!(),
        Action::Status => unreachable!(),
    };
    if let Err(error) = &result {
        let event = Event::new("error", error.to_string(), "", 0);
        // A read-only status process can retrieve errors after the GUI restarts.
        let _ = store.publish(&event);
    }
    result
}

fn transient(event: &Event) -> bool {
    matches!(
        event.phase.as_str(),
        "checking" | "downloading" | "verifying" | "scheduled" | "installing"
    )
}

// Commands never inherit APT_CONFIG, dynamic loader settings, user PATH, or proxies.
fn command(path: impl AsRef<Path>) -> std::process::Command {
    let mut command = std::process::Command::new(path.as_ref());
    command
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LANG", "C.UTF-8");
    command
}

#[cfg(test)]
mod cli_tests {
    use super::*;
    #[test]
    fn axis_maintenance_accepts_only_a_fixed_axis_count() {
        for count in ["3", "4", "5"] {
            assert!(Options::try_parse_from(["updater", "axis-maintenance", count]).is_ok());
        }
        for count in ["0", "2", "6", "-1", "/tmp/machine.ini", "3;id"] {
            assert!(Options::try_parse_from(["updater", "axis-maintenance", count]).is_err());
        }
        assert!(Options::try_parse_from([
            "updater",
            "axis-maintenance",
            "5",
            "--ini",
            "/tmp/machine.ini"
        ])
        .is_err());
    }
    #[test]
    fn install_rejects_paths_urls_commands_and_legacy_privileged_apply() {
        for extra in [
            "--socket",
            "--package",
            "--url",
            "--command",
            "--apt-option",
        ] {
            assert!(
                Options::try_parse_from(["updater", "install", extra, "/tmp/user-controlled"])
                    .is_err()
            );
        }
        assert!(Options::try_parse_from(["updater", "apply"]).is_err());
        assert!(Options::try_parse_from([
            "updater",
            "apply-system",
            "--package",
            "/tmp/package.deb"
        ])
        .is_err());
        let process = command("/usr/bin/apt-get");
        assert!(process
            .get_envs()
            .all(|(key, _)| key == "PATH" || key == "LANG"));
    }
}
