//! One category per event; origin remains a separate field.
mod account;
mod build;
mod configuration;
mod connection;
mod hardware;
mod homing;
mod internal;
mod motion;
mod parameters;
mod program;
mod storage;
mod update;
pub(crate) const ALL: &[&str] = &[
    "parameters",
    "motion",
    "homing",
    "hardware",
    "program",
    "connection",
    "configuration",
    "update",
    "build",
    "account",
    "storage",
    "internal",
];
pub(crate) fn classify(source: &str, code: &str, message: &str) -> &'static str {
    let text = format!("{code} {message}").to_lowercase();
    if parameters::matches(&text) {
        return "parameters";
    }
    if account::matches(&text) {
        return "account";
    }
    if storage::matches(&text) {
        return "storage";
    }
    if homing::matches(&text) {
        return "homing";
    }
    if hardware::matches(&text) {
        return "hardware";
    }
    if configuration::matches(&text) {
        return "configuration";
    }
    if update::matches(&text) {
        return "update";
    }
    if build::matches(&text) {
        return "build";
    }
    if motion::matches(&text) {
        return "motion";
    }
    if program::matches(&text) {
        return "program";
    }
    if connection::matches(&text) {
        return "connection";
    }
    if internal::matches(&text) {
        return "internal";
    }
    match source {
        "updater" | "local-update" | "mesa-update" => "update",
        "package-build" => "build",
        "account" => "account",
        "configuration" => "configuration",
        "cam-link" => "connection",
        _ => "internal",
    }
}
