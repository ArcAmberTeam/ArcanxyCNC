fn main() {
    if betterlinuxcnc_cnc_maint::run().is_err() {
        eprintln!("Maintenance account operation failed");
        std::process::exit(1);
    }
}
