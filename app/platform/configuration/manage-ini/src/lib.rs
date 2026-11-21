//! Public process entry point for the restricted maintenance terminal.

mod axis_parameters;
mod axis_preview;
mod commands;
mod configuration;
mod ini;
mod pa;
mod permissions;
mod targets;
mod terminal;

pub fn run() -> u8 {
    match permissions::authorize() {
        Ok(()) => pa::run(),
        Err(message) => {
            eprintln!("pa: {message}");
            77
        }
    }
}

/// Open an isolated presentation preview without account or configuration access.
/// This is a development entry point, not an authentication mode of the PA CLI.
pub fn preview() -> std::io::Result<()> {
    terminal::preview()
}

/// Dispatch the fixed configuration transports. The maintenance sudo rule allows no arguments.
pub fn configuration_service() -> u8 {
    if std::env::args_os()
        .skip(1)
        .eq([std::ffi::OsString::from("preview-parameters")])
    {
        return axis_preview::run();
    }
    if std::env::args_os().len() > 1 {
        return axis_parameters::run();
    }
    configuration::serve()
}
