//! First-time administrator setup with the existing maintenance credential.
use super::{
    active_policy, authenticate, lock, managed_file, policy_state, replace_file, OPEN, POLICY,
};
use crate::{
    command, enabled, ledger, set_password, valid_password, validate_account, validate_identity,
    Result,
};

const RECORD: &str = "/var/lib/betterlinuxcnc/cnc-admin-enrollment";
const PENDING: &str = "pending\n";
const COMPLETE: &str = "complete\n";

fn record() -> Result<Option<String>> {
    let value = managed_file(RECORD)?;
    match value.as_deref() {
        None | Some(PENDING | COMPLETE | "unissued\n") => Ok(value),
        Some(text)
            if text.strip_suffix('\n').is_some_and(|hash| {
                hash.len() == 64 && hash.bytes().all(|b| b.is_ascii_hexdigit())
            }) =>
        {
            Ok(value)
        }
        _ => Err("Unrecognized administrator enrollment record".into()),
    }
}

fn pristine_account() -> Result<bool> {
    validate_identity("cnc_admin", "/var/lib/betterlinuxcnc/admin")?;
    let output = command("/usr/bin/getent")
        .args(["shadow", "cnc_admin"])
        .output()?;
    let fields: Vec<_> = std::str::from_utf8(&output.stdout)?
        .trim_end()
        .split(':')
        .collect();
    if !output.status.success() || fields.len() != 9 || fields[0] != "cnc_admin" {
        return Err("Administrator shadow entry unavailable".into());
    }
    Ok(fields[1] == "!" && matches!(fields[7], "" | "-1" | "1"))
}

// The caller holds the same lock used for password enrollment and sudo changes.
pub(super) fn provision() -> Result<()> {
    let state = record()?;
    if state.as_deref() == Some(COMPLETE) {
        return Ok(());
    }
    if !pristine_account()? || policy_state()? == Some(true) {
        return replace_file(RECORD, COMPLETE, 0o600);
    }
    if state.as_deref() != Some(PENDING) {
        // Discard any verifier issued by an earlier package.
        replace_file(RECORD, PENDING, 0o600)?;
    }
    Ok(())
}

pub(super) fn finish() -> Result<()> {
    if record()?.as_deref() != Some(COMPLETE) {
        replace_file(RECORD, COMPLETE, 0o600)?;
    }
    Ok(())
}

fn eligible() -> Result<bool> {
    let state = record()?.ok_or("Missing administrator enrollment record")?;
    Ok(state == PENDING && pristine_account()?)
}

pub(crate) fn required() -> Result<bool> {
    let _guard = lock()?;
    Ok(!active_policy()? && eligible()?)
}

pub(crate) fn credentials(input: &str) -> Result<(&str, &str)> {
    let (maintenance_password, new_password) =
        input.split_once('\n').ok_or("Missing setup credentials")?;
    if maintenance_password.is_empty()
        || maintenance_password.len() > 512
        || maintenance_password.chars().any(char::is_control)
        || !valid_password(new_password)
    {
        return Err("Invalid setup credentials".into());
    }
    Ok((maintenance_password, new_password))
}

pub(crate) fn enroll(input: &str) -> Result<bool> {
    let (maintenance_password, new_password) = credentials(input)?;
    let _maintenance_guard = ledger()?;
    let _admin_guard = lock()?;
    validate_account()?;
    if active_policy()? || !eligible()? || !enabled()? {
        return Err("Administrator setup unavailable".into());
    }
    authenticate("cnc-maint", maintenance_password)?;
    set_password("cnc_admin", new_password)?;
    finish()?;
    authenticate("cnc_admin", new_password)?;
    replace_file(POLICY, OPEN, 0o440)?;
    Ok(true)
}
