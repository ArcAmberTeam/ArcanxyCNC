fn main() {
    if let Err(error) = betterlinuxcnc_updater::run() {
        betterlinuxcnc_error_client::report("updater", "operation_failed", &error.to_string());
        eprintln!("{error}");
        std::process::exit(1);
    }
}
