//! Independent local error ingestion, classification, MySQL storage and export.
mod categories;
mod config;
mod database;
mod event;
mod export;
mod native_logs;
mod provision;
mod service;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error + Send + Sync>>;
const STATE: &str = "/var/lib/betterlinuxcnc/error-records";
const EXPORT: &str = "/var/log/betterlinuxcnc/errors";
const RUNTIME: &str = "/run/betterlinuxcnc-error-records";
const BASE: &str = "/usr/lib/betterlinuxcnc/error-records";

/// Fixed service and read-only maintenance entry points.
pub fn run() -> Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.as_slice() {
        [command] if command == "provision" => provision::run(),
        [command] if command == "serve" => service::run(),
        [command, rest @ ..] if command == "query" => service::query(rest),
        _ => Err("Use provision, serve, or query [category|event-id|status]".into()),
    }
}
