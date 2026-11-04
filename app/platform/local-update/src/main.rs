fn main() {
    if let Err(error) = betterlinuxcnc_local_update::run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
