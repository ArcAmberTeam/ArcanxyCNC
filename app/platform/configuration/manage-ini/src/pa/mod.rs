//! PA owns the executable grammar; individual verbs live under commands.

use crate::{commands, terminal};

pub(crate) fn run() -> u8 {
    let arguments: Vec<_> = std::env::args_os().skip(1).collect();
    if arguments.is_empty() || arguments == ["--help"] || arguments == ["help"] {
        println!("Usage: pa manage <target>");
        commands::manage::print_help();
        return 0;
    }
    if arguments[0] != commands::manage::NAME {
        eprintln!("pa: Unknown command. Use pa --help.");
        return 64;
    }
    let target = match commands::manage::parse(&arguments[1..]) {
        Ok(target) => target,
        Err(message) => {
            eprintln!("pa: {message}");
            return 64;
        }
    };
    match terminal::open(target, &mut std::io::stdin().lock(), &mut std::io::stdout()) {
        Ok(()) => 0,
        Err(error) => {
            betterlinuxcnc_error_client::report(
                "configuration",
                "ini_operation_failed",
                &error.to_string(),
            );
            eprintln!("pa: {error}");
            74
        }
    }
}
