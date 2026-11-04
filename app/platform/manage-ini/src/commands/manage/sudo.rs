//! PA adapter for the public, authenticated maintenance-account CLI.

pub(crate) fn open() -> u8 {
    // Sudo owns the terminal password conversation and PAM authentication.
    // -k and the command-specific policy require fresh authentication.
    match std::process::Command::new("/usr/bin/sudo")
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LANG", "C.UTF-8")
        .args([
            "-k",
            "-p",
            "cnc-maint password: ",
            "--",
            "/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account",
            "sudo-open",
        ])
        .status()
    {
        Ok(status) if status.success() => 0,
        _ => {
            betterlinuxcnc_error_client::report(
                "account",
                "sudo_open_refused",
                "Temporary sudo activation was not confirmed",
            );
            eprintln!("pa: Temporary sudo activation was not confirmed");
            77
        }
    }
}
