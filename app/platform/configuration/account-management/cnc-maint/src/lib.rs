//! Fixed cnc-maint account, build workspace and local package request boundary.
//! CLI: provision (root, one-time revocation), enable/disable/status (root),
//! serve (root, systemd connected socket on stdin), request OP (operator).
//! The operator socket also exposes admin-sudo-status, admin-sudo-enable and
//! admin-sudo-disable. Both mutations authenticate the separate cnc_admin account.
//! Passwords enter stdin/socket only. Replies contain booleans, never credentials.
//--------//
// BEGIN: MaintenanceAccountService
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::Duration;

mod operator_screen;
mod sudo_access;
mod workspace;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
const SOCKET: &str = "/run/betterlinuxcnc-cnc-maint.sock";
const LEDGER: &str = "/var/lib/betterlinuxcnc/cnc-maint-policy-v1";
const UNIT: &str = "betterlinuxcnc-cnc-maint";
const SOCKET_UNIT: &str = "[Unit]\nDescription=Local maintenance account requests\n[Socket]\nListenStream=/run/betterlinuxcnc-cnc-maint.sock\nSocketUser=linuxcnc\nSocketMode=0600\nAccept=yes\nMaxConnections=4\nRemoveOnStop=yes\n[Install]\nWantedBy=sockets.target\n";
const SERVICE_UNIT: &str = "[Unit]\nDescription=Fixed maintenance account operation\n[Service]\nExecStart=/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account serve\nUser=root\nStandardInput=socket\nStandardOutput=null\nStandardError=null\nTimeoutStartSec=30\nRuntimeMaxSec=30\nUMask=0077\nNoNewPrivileges=yes\nPrivateTmp=yes\nProtectHome=yes\nProtectSystem=strict\nReadWritePaths=/etc /var/lib/betterlinuxcnc\nProtectKernelTunables=yes\nProtectKernelModules=yes\nProtectControlGroups=yes\nLockPersonality=yes\nLimitCORE=0\n";

// Linux socket and flock ABI. This crate is only installed on the Linux appliance.
unsafe extern "C" {
    fn geteuid() -> u32;
    fn flock(fd: i32, operation: i32) -> i32;
    fn getsockopt(
        fd: i32,
        level: i32,
        option: i32,
        value: *mut std::ffi::c_void,
        length: *mut u32,
    ) -> i32;
}
#[repr(C)]
#[derive(Default)]
struct Credentials {
    pid: i32,
    uid: u32,
    gid: u32,
}
fn command(program: &str) -> Command {
    let mut command = Command::new(program);
    command
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LANG", "C");
    command
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    command
}
fn fixed(program: &str, args: &[&str]) -> Result<()> {
    if !command(program).args(args).status()?.success() {
        return Err("System account operation rejected".into());
    }
    Ok(())
}
fn operator_uid() -> Result<u32> {
    let output = command("/usr/bin/id").args(["-u", "linuxcnc"]).output()?;
    if !output.status.success() {
        return Err("Missing operator".into());
    }
    let uid = String::from_utf8(output.stdout)?.trim().parse::<u32>()?;
    if uid < 1000 || uid == 65534 {
        return Err("Invalid operator identity".into());
    }
    Ok(uid)
}
fn validate_account() -> Result<()> {
    validate_identity("cnc-maint", "/var/lib/betterlinuxcnc/maintenance")
}
fn validate_identity(name: &str, home: &str) -> Result<()> {
    let output = command("/usr/bin/getent").args(["passwd", name]).output()?;
    let text = String::from_utf8(output.stdout)?;
    let fields: Vec<_> = text.trim().split(':').collect();
    if !output.status.success()
        || fields.len() != 7
        || fields[0] != name
        || fields[5] != home
        || fields[6] != "/bin/sh"
        || fields[2].parse::<u32>()? < 1000
        || fields[2] == "65534"
    {
        return Err("Unexpected appliance account identity".into());
    }
    Ok(())
}
fn trusted_parent(path: &Path) -> Result<()> {
    for parent in path.ancestors().skip(1) {
        let info = fs::symlink_metadata(parent)?;
        if !info.is_dir() || info.uid() != 0 || info.mode() & 0o022 != 0 {
            return Err("Untrusted account path".into());
        }
    }
    Ok(())
}
fn ledger() -> Result<File> {
    trusted_parent(Path::new(LEDGER))?;
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .custom_flags(0x20000)
        .open(LEDGER)?;
    let info = file.metadata()?;
    if !info.is_file() || info.uid() != 0 || info.nlink() != 1 || info.mode() & 0o077 != 0 {
        return Err("Invalid policy ledger".into());
    }
    if unsafe { flock(file.as_raw_fd(), 2 | 4) } != 0 {
        return Err("Account operation busy".into());
    }
    Ok(file)
}
fn valid_password(value: &str) -> bool {
    (8..=256).contains(&value.len()) && !value.chars().any(|c| c.is_control() || c == ':')
}
fn enable(value: &str) -> Result<()> {
    set_password("cnc-maint", value)?;
    fixed("/usr/sbin/usermod", &["--expiredate", "", "cnc-maint"])
}
fn set_password(account: &str, value: &str) -> Result<()> {
    if !valid_password(value) {
        return Err("Password must contain 8 to 256 bytes without controls or colon".into());
    }
    let mut child = command("/usr/sbin/chpasswd")
        .stdin(Stdio::piped())
        .spawn()?;
    let written = child
        .stdin
        .take()
        .ok_or("Missing password pipe")?
        .write_all(format!("{account}:{value}\n").as_bytes());
    let status = child.wait()?;
    written?;
    if !status.success() {
        return Err("Password update rejected".into());
    }
    Ok(())
}
fn disable() -> Result<()> {
    // Replace the hash, rather than prefixing it, so unlocking cannot restore it.
    // Expiry also rejects public-key authentication under the existing PAM policy.
    fixed(
        "/usr/sbin/usermod",
        &["--password", "!", "--expiredate", "1", "cnc-maint"],
    )
}
fn enabled() -> Result<bool> {
    let shadow = fs::read_to_string("/etc/shadow")?;
    let entry = shadow
        .lines()
        .find(|line| line.starts_with("cnc-maint:"))
        .ok_or("Missing account")?;
    let fields: Vec<_> = entry.split(':').collect();
    if fields.len() != 9 {
        return Err("Invalid shadow entry".into());
    }
    Ok(!fields[1].is_empty()
        && !fields[1].starts_with(['!', '*'])
        && (fields[7].is_empty() || fields[7] == "-1"))
}
fn response(state: bool) -> String {
    format!("{{\"ok\":true,\"enabled\":{state}}}\n")
}
fn socket_response(operation: &str, state: bool) -> String {
    if operation == "admin-setup-required" {
        format!("{{\"ok\":true,\"setupRequired\":{state}}}\n")
    } else {
        response(state)
    }
}
fn bounded(mut input: impl Read) -> Result<String> {
    let mut bytes = Vec::new();
    input.by_ref().take(1025).read_to_end(&mut bytes)?;
    if bytes.len() > 1024 {
        return Err("Request too large".into());
    }
    Ok(String::from_utf8(bytes)?)
}
fn parse_request(request: &str) -> Result<(&str, &str)> {
    let (operation, password) = request.split_once('\n').ok_or("Invalid request")?;
    match operation {
        "status" | "admin-sudo-status" | "admin-setup-required" if password.is_empty() => {
            Ok((operation, password))
        }
        "admin-sudo-enroll" if sudo_access::enrollment::credentials(password).is_ok() => {
            Ok((operation, password))
        }
        "disable" | "admin-sudo-enable" | "admin-sudo-disable"
            if !password.is_empty()
                && password.len() <= 512
                && !password.chars().any(char::is_control) =>
        {
            Ok((operation, password))
        }
        "enable" if valid_password(password) => Ok((operation, password)),
        _ => Err("Invalid account request".into()),
    }
}
fn apply(operation: &str, password: &str) -> Result<bool> {
    match operation {
        "admin-sudo-status" => return sudo_access::request(None, ""),
        "admin-setup-required" => return sudo_access::enrollment::required(),
        "admin-sudo-enroll" => return sudo_access::enrollment::enroll(password),
        "admin-sudo-enable" => return sudo_access::request(Some(true), password),
        "admin-sudo-disable" => return sudo_access::request(Some(false), password),
        _ => {}
    }
    maintenance(operation, password, true)
}

fn maintenance(operation: &str, password: &str, operator_request: bool) -> Result<bool> {
    validate_account()?;
    let _guard = ledger()?;
    match operation {
        "status" => {}
        "enable" => {
            if operator_request && enabled()? {
                sudo_access::authenticate("cnc-maint", password)?;
            } else {
                enable(password)?;
            }
            sudo_access::maintenance_available(true)?;
        }
        "disable" => {
            if operator_request {
                sudo_access::authenticate("cnc-maint", password)?;
            }
            sudo_access::maintenance_available(false)?;
            disable()?;
        }
        _ => return Err("Invalid operation".into()),
    }
    enabled()
}
fn peer(stream: &UnixStream) -> Result<Credentials> {
    let mut value = Credentials::default();
    let mut size = std::mem::size_of::<Credentials>() as u32;
    if unsafe {
        getsockopt(
            stream.as_raw_fd(),
            1,
            17,
            (&mut value as *mut Credentials).cast(),
            &mut size,
        )
    } != 0
        || size as usize != std::mem::size_of::<Credentials>()
    {
        return Err("Peer credentials unavailable".into());
    }
    Ok(value)
}
fn serve() -> Result<()> {
    let mut stream = unsafe { UnixStream::from_raw_fd(0) };
    stream.set_read_timeout(Some(Duration::from_secs(10)))?;
    stream.set_write_timeout(Some(Duration::from_secs(10)))?;
    let caller = peer(&stream)?;
    if caller.uid != operator_uid()? {
        return Err("Caller is not the local operator".into());
    }
    let result = (|| {
        let text = bounded(&stream)?;
        let (op, password) = parse_request(&text)?;
        if matches!(op, "enable" | "disable") {
            operator_screen::require(&caller)?;
        }
        apply(op, password).map(|state| socket_response(op, state))
    })();
    let reply = match result {
        Ok(reply) => reply,
        Err(_) => {
            betterlinuxcnc_error_client::report(
                "account",
                "account_request_refused",
                "Maintenance account request refused",
            );
            "{\"ok\":false}\n".into()
        }
    };
    stream.write_all(reply.as_bytes())?;
    Ok(())
}
fn register() -> Result<()> {
    validate_account()?;
    sudo_access::provision()?;
    workspace::provision()?;
    let mut guard = ledger()?;
    let mut marker = String::new();
    guard.read_to_string(&mut marker)?;
    if marker.is_empty() {
        disable()?;
        guard.write_all(b"revoked-v1\n")?;
        guard.sync_all()?;
    } else if marker != "revoked-v1\n" {
        return Err("Unknown policy ledger".into());
    }
    sudo_access::maintenance_available(enabled()?)?;
    for (unit, suffix, contents) in [
        (UNIT, ".socket", SOCKET_UNIT),
        (UNIT, "@.service", SERVICE_UNIT),
        (workspace::UNIT, ".socket", workspace::SOCKET_UNIT),
        (workspace::UNIT, "@.service", workspace::SERVICE_UNIT),
    ] {
        let path = std::path::PathBuf::from(format!("/usr/lib/systemd/system/{unit}{suffix}"));
        trusted_parent(&path)?;
        if path.try_exists()? {
            let info = fs::symlink_metadata(&path)?;
            if !info.is_file() || info.uid() != 0 || info.mode() & 0o022 != 0 {
                return Err("Local service edits require review".into());
            }
            let current = fs::read_to_string(&path)?;
            if current != contents {
                let previous = contents.replace("AmbientCapabilities=CAP_SETUID CAP_SETGID\n", "");
                if unit != workspace::UNIT || suffix != "@.service" || current != previous {
                    return Err("Local service edits require review".into());
                }
                // Upgrade only the exact previously shipped local-install unit.
                let temporary = path.with_extension(format!("upgrade-{}", std::process::id()));
                let mut file = OpenOptions::new()
                    .write(true)
                    .create_new(true)
                    .mode(0o644)
                    .open(&temporary)?;
                file.write_all(contents.as_bytes())?;
                file.sync_all()?;
                fs::rename(&temporary, &path)?;
                File::open(path.parent().ok_or("Missing unit parent")?)?.sync_all()?;
            }
        } else {
            let mut file = OpenOptions::new()
                .write(true)
                .create_new(true)
                .mode(0o644)
                .open(path)?;
            file.write_all(contents.as_bytes())?;
            file.sync_all()?;
        }
    }
    fixed(
        "/usr/bin/systemctl",
        &[
            "enable",
            "betterlinuxcnc-cnc-maint.socket",
            "betterlinuxcnc-cnc-maint-build.socket",
        ],
    )?;
    if Path::new("/run/systemd/system").is_dir() {
        fixed("/usr/bin/systemctl", &["daemon-reload"])?;
        fixed(
            "/usr/bin/systemctl",
            &[
                "start",
                "betterlinuxcnc-cnc-maint.socket",
                "betterlinuxcnc-cnc-maint-build.socket",
            ],
        )?;
    }
    Ok(())
}
/// Public CLI entry point. No caller-selected account, file, executable, or socket.
pub fn run() -> Result<()> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.first().is_some_and(|arg| arg == "workspace") {
        return workspace::run(&args[1..]);
    }
    if args.len() == 2 && args[0] == "request" {
        if unsafe { geteuid() } != operator_uid()? {
            return Err("Operator required".into());
        }
        let password = if matches!(
            args[1].as_str(),
            "enable" | "disable" | "admin-sudo-enable" | "admin-sudo-disable" | "admin-sudo-enroll"
        ) {
            bounded(io::stdin())?
        } else {
            String::new()
        };
        let request = format!("{}\n{}", args[1], password);
        parse_request(&request)?;
        let mut stream = UnixStream::connect(SOCKET)?;
        if peer(&stream)?.uid != 0 {
            return Err("Account service is not root".into());
        }
        stream.set_read_timeout(Some(Duration::from_secs(15)))?;
        stream.set_write_timeout(Some(Duration::from_secs(10)))?;
        stream.write_all(request.as_bytes())?;
        stream.shutdown(std::net::Shutdown::Write)?;
        let reply = bounded(stream)?;
        if reply != socket_response(&args[1], true) && reply != socket_response(&args[1], false) {
            return Err("Account change was not confirmed".into());
        }
        print!("{reply}");
        return Ok(());
    }
    if unsafe { geteuid() } != 0 || args.len() != 1 {
        return Err("Fixed root operation required".into());
    }
    match args[0].as_str() {
        "provision" => register(),
        "serve" => serve(),
        "install-serve" => workspace::serve_install(),
        "enable" => {
            let password = bounded(io::stdin())?;
            println!(
                "{}",
                response(maintenance(
                    "enable",
                    password.trim_end_matches('\n'),
                    false
                )?)
            );
            Ok(())
        }
        "disable" | "status" => {
            print!("{}", response(maintenance(&args[0], "", false)?));
            Ok(())
        }
        _ => Err("Unknown account operation".into()),
    }
}

// END: MaintenanceAccountService
//--------//

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bounded_protocol_rejects_injection_and_weak_passwords() {
        for input in [
            "enable\n",
            "enable\nshort",
            "enable\npassword\nroot:secret",
            "enable\npassword:root",
            "disable\n",
            "other\n",
        ] {
            assert!(parse_request(input).is_err());
        }
        assert!(parse_request("enable\ncorrect horse battery").is_ok());
        assert!(parse_request("disable\ncurrent password").is_ok());
        assert!(bounded(&vec![b'x'; 1025][..]).is_err());
    }
    #[test]
    fn actual_socket_peer_is_observed() {
        let (a, _b) = UnixStream::pair().unwrap();
        assert_eq!(peer(&a).unwrap().uid, unsafe { geteuid() });
    }
}
