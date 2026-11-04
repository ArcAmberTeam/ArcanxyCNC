//! The two command entry points are the module's only public interface.
//! Release downloads never authorize a hardware write.

mod contract;
mod guard;
mod hardware;
mod platform;
mod release;
mod service;
mod storage;

use clap::{Parser, Subcommand};
use std::process::ExitCode;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error + Send + Sync>>;

#[derive(Parser)]
#[command(
    name = "betterlinuxcnc-mesa-update",
    version,
    about = "Check and download paired official Mesa releases; never flash hardware"
)]
struct UpdateCli {
    #[command(subcommand)]
    command: UpdateCommand,
}

#[derive(Subcommand)]
enum UpdateCommand {
    /// Check the two official latest releases for a matching application version.
    Check,
    /// Read the last check/download result without network or hardware access.
    Status,
    /// Download verified firmware for the installed application version, if available.
    Download,
}

#[derive(Parser)]
#[command(
    name = "betterlinuxcnc-mesa-flash",
    version,
    about = "Independent, guarded Mesa firmware flashing service"
)]
struct FlashCli {
    #[command(subcommand)]
    command: FlashCommand,
}

#[derive(Subcommand)]
enum FlashCommand {
    /// Read the root service's public result; never reads the user's download cache.
    Status,
    /// Request the one fixed root service; no firmware or hardware parameters are accepted.
    Request,
    /// Root-only official verification and controlled maintenance operation.
    ApplySystem,
    #[command(hide = true)]
    PrepareSystem,
    #[command(hide = true)]
    WriteSystem,
}

/// Run the unprivileged updater's fixed command interface.
pub fn run_update() -> ExitCode {
    finish(match UpdateCli::parse().command {
        UpdateCommand::Check => service::check(),
        UpdateCommand::Status => service::update_status(),
        UpdateCommand::Download => service::download(),
    })
}

/// Run the separate root verifier's fixed command interface.
pub fn run_flash() -> ExitCode {
    finish(match FlashCli::parse().command {
        FlashCommand::Status => service::flash_status(),
        FlashCommand::Request => service::request(),
        FlashCommand::ApplySystem => service::apply_system(),
        FlashCommand::PrepareSystem => service::prepare_system(),
        FlashCommand::WriteSystem => service::write_system(),
    })
}

fn finish(result: Result<()>) -> ExitCode {
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            betterlinuxcnc_error_client::report(
                "mesa-update",
                "operation_failed",
                &error.to_string(),
            );
            // HTTP errors are reduced to fixed descriptions by the release adapter.
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}
