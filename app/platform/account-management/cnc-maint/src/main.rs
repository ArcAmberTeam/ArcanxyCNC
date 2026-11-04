fn main() {
    if let Err(error) = betterlinuxcnc_cnc_maint::run() {
        betterlinuxcnc_error_client::report(
            "account",
            "operation_failed",
            "Maintenance account operation failed",
        );
        // Account operations remain opaque so password validation cannot leak input.
        if std::env::args().nth(1).as_deref() == Some("workspace") {
            eprintln!("Maintenance workspace failed: {error}");
        } else if matches!(
            std::env::args().nth(1).as_deref(),
            Some("sudo-open" | "sudo-close")
        ) {
            betterlinuxcnc_error_client::report(
                "account",
                "sudo_operation_failed",
                &error.to_string(),
            );
            eprintln!("Maintenance sudo operation failed: {error}");
        } else {
            eprintln!("Maintenance account operation failed");
        }
        std::process::exit(1);
    }
}
