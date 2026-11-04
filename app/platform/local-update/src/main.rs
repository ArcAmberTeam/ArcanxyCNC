fn main() {
    if let Err(error) = betterlinuxcnc_local_update::run() {
        betterlinuxcnc_error_client::report("local-update", "operation_failed", &error.to_string());
        eprintln!("{error}");
        std::process::exit(1);
    }
}
