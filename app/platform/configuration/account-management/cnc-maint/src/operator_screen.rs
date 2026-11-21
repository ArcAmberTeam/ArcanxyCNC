//! Authorize account setup from the supervised desktop on the active machine seat.
use super::{command, Credentials, Result};
use std::fs;

fn loginctl(args: &[&str]) -> Result<String> {
    let output = command("/usr/bin/loginctl").args(args).output()?;
    if !output.status.success() {
        return Err("Local graphical session unavailable".into());
    }
    Ok(String::from_utf8(output.stdout)?)
}

pub(super) fn require(peer: &Credentials) -> Result<()> {
    let groups = fs::read_to_string(format!("/proc/{}/cgroup", peer.pid))?;
    let user = format!("user@{}.service", peer.uid);
    if !groups
        .lines()
        .filter_map(|line| line.strip_prefix("0::"))
        .any(|path| {
            path.split('/').any(|part| part == user)
                && path.ends_with("/betterlinuxcnc-launcher.service")
        })
    {
        return Err("Machine desktop required".into());
    }
    let session = loginctl(&["show-user", "linuxcnc", "--property=Display", "--value"])?;
    let id = session.trim();
    if id.is_empty() || !id.bytes().all(|c| c.is_ascii_alphanumeric()) {
        return Err("Missing graphical session".into());
    }
    let properties = loginctl(&["show-session", id])?;
    if ![
        "Name=linuxcnc",
        "Seat=seat0",
        "Active=yes",
        "Remote=no",
        "Type=x11",
        "LockedHint=no",
    ]
    .iter()
    .all(|expected| properties.lines().any(|line| line == *expected))
    {
        return Err("Active local operator screen required".into());
    }
    Ok(())
}
