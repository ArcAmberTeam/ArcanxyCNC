fn main() {
    if let Err(error) = betterlinuxcnc_package_build::run() {
        betterlinuxcnc_error_client::report(
            "package-build",
            "operation_failed",
            &error.to_string(),
        );
        eprintln!("{error}");
        std::process::exit(1);
    }
}
