fn main() {
    if let Err(error) = betterlinuxcnc_package_build::run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
