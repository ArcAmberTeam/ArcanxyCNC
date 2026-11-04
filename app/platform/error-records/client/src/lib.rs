//! Best-effort, nonblocking local error submission; no database or machine access.
use serde_json::json;
use std::os::unix::net::UnixDatagram;

pub const SOCKET: &str = "/run/betterlinuxcnc-error-records/events.sock";

/// Submit one bounded error. A collector failure never changes an operation's outcome.
pub fn report(source: &str, code: &str, message: &str) {
    let message: String = message.chars().take(4096).collect();
    let event = json!({"schema_version":1,"source":source,"code":code,
        "message":message,"context":{}});
    if let (Ok(bytes), Ok(socket)) = (serde_json::to_vec(&event), UnixDatagram::unbound()) {
        if bytes.len() <= 16384 && socket.set_nonblocking(true).is_ok() {
            let _ = socket.send_to(&bytes, SOCKET);
        }
    }
}
