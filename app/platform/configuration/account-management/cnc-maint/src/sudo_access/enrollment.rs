//! First-time, on-device enrollment of the dedicated administrator.
//! 安装人员签发开通码，用户在本机 Web 设置密码。开通码不能用于重置已有密码。
use super::{
    active_policy, authenticate, lock, managed_file, policy_state, replace_file, OPEN, POLICY,
};
use crate::{command, set_password, valid_password, validate_identity, Result};
use sha2::{Digest, Sha256};
use std::fs::{self, File};
use std::io::{self, IsTerminal, Read};

const RECORD: &str = "/var/lib/betterlinuxcnc/cnc-admin-enrollment";
const UNISSUED: &str = "unissued\n";
const COMPLETE: &str = "complete\n";

fn record() -> Result<Option<String>> {
    let value = managed_file(RECORD)?;
    match value.as_deref() {
        None | Some(UNISSUED | COMPLETE) => Ok(value),
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
    Ok(fields[1] == "!" && matches!(fields[7], "" | "-1"))
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
    if state.is_none() {
        replace_file(RECORD, UNISSUED, 0o600)?;
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
    Ok(state != COMPLETE && pristine_account()?)
}

pub(crate) fn required() -> Result<bool> {
    let _guard = lock()?;
    Ok(!active_policy()? && eligible()?)
}

fn verifier(code: &str) -> Result<String> {
    let machine = fs::read_to_string("/etc/machine-id")?;
    let machine = machine.trim();
    if machine.len() != 32
        || machine.bytes().all(|b| b == b'0')
        || !machine.bytes().all(|b| b.is_ascii_hexdigit())
    {
        return Err("Device identity unavailable".into());
    }
    let normalized: String = code
        .chars()
        .filter(|&c| c != '-')
        .map(|c| c.to_ascii_uppercase())
        .collect();
    Ok(format!(
        "{:x}\n",
        Sha256::digest(format!("{machine}:{normalized}").as_bytes())
    ))
}

pub(crate) fn issue() -> Result<()> {
    let _guard = lock()?;
    if !io::stdout().is_terminal() || policy_state()? != Some(false) || !eligible()? {
        return Err(
            "Code issuance requires an installer terminal and an unconfigured administrator".into(),
        );
    }
    let mut random = [0u8; 16];
    File::open("/dev/urandom")?.read_exact(&mut random)?;
    let code = random
        .chunks_exact(2)
        .map(|pair| format!("{:02X}{:02X}", pair[0], pair[1]))
        .collect::<Vec<_>>()
        .join("-");
    replace_file(RECORD, &verifier(&code)?, 0o600)?;
    println!("{code}");
    Ok(())
}

pub(crate) fn credentials(input: &str) -> Result<(&str, &str)> {
    let (code, password) = input
        .split_once('\n')
        .ok_or("Missing enrollment credentials")?;
    if code.len() > 39
        || !code.bytes().all(|b| b == b'-' || b.is_ascii_hexdigit())
        || code.bytes().filter(u8::is_ascii_hexdigit).count() != 32
        || !valid_password(password)
    {
        return Err("Invalid enrollment credentials".into());
    }
    Ok((code, password))
}

pub(crate) fn enroll(input: &str) -> Result<bool> {
    let (code, password) = credentials(input)?;
    let _guard = lock()?;
    let expected = verifier(code)?;
    if active_policy()? || record()?.as_deref() != Some(expected.as_str()) || !pristine_account()? {
        return Err("Administrator enrollment refused".into());
    }
    // Consume before changing shadow. On interruption a new code can only be
    // issued while the account still has its original locked password field.
    replace_file(RECORD, UNISSUED, 0o600)?;
    if let Err(error) = set_password("cnc_admin", password) {
        if pristine_account()? {
            replace_file(RECORD, &expected, 0o600)?;
        }
        return Err(error);
    }
    finish()?;
    authenticate(password)?;
    replace_file(POLICY, OPEN, 0o440)?;
    Ok(true)
}
