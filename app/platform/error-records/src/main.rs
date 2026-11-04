fn main() {
    if let Err(error) = betterlinuxcnc_error_records::run() {
        eprintln!("Error records: {error}");
        std::process::exit(1);
    }
}
