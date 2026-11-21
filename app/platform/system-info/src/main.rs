use std::process::ExitCode;

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    if arguments == ["--help"] {
        println!(
            "betterlinuxcnc-system-info --json\nRead Linux host information without privileges."
        );
        return ExitCode::SUCCESS;
    }
    if arguments != ["--json"] {
        eprintln!("Expected --json or --help");
        return ExitCode::from(2);
    }
    if !cfg!(target_os = "linux") {
        eprintln!("System information is available only on Linux");
        return ExitCode::FAILURE;
    }
    match serde_json::to_writer(
        std::io::stdout().lock(),
        &betterlinuxcnc_system_info::collect(),
    ) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("Could not write system information: {error}");
            ExitCode::FAILURE
        }
    }
}
