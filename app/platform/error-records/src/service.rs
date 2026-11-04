use crate::{
    categories, database, event::Event, export, provision, Result, EXPORT, RUNTIME, STATE,
};
use serde_json::json;
use std::{
    fs,
    io::{Read, Write},
    os::{
        fd::AsRawFd,
        unix::{
            fs::PermissionsExt,
            net::{UnixDatagram, UnixListener, UnixStream},
        },
    },
    path::Path,
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc, Mutex,
    },
    time::Duration,
};

#[derive(Default)]
struct Health {
    accepted: AtomicU64,
    rejected: AtomicU64,
    dropped: AtomicU64,
    database: Mutex<String>,
}

fn allowed(uid: u32) -> bool {
    uid == 0
        || ["linuxcnc", "cnc-maint", "cnc-errors"]
            .iter()
            .any(|name| provision::uid(name).ok() == Some(uid))
}

#[cfg(target_os = "linux")]
fn receive(socket: &UnixDatagram) -> Result<(Vec<u8>, u32, i32)> {
    let mut data = vec![0u8; 16384];
    let mut control = [0usize; 16];
    let mut iov = libc::iovec {
        iov_base: data.as_mut_ptr().cast(),
        iov_len: data.len(),
    };
    let mut message: libc::msghdr = unsafe { std::mem::zeroed() };
    message.msg_iov = &mut iov;
    message.msg_iovlen = 1;
    message.msg_control = control.as_mut_ptr().cast();
    message.msg_controllen = std::mem::size_of_val(&control);
    let size = unsafe { libc::recvmsg(socket.as_raw_fd(), &mut message, 0) };
    if size < 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    if message.msg_flags & (libc::MSG_TRUNC | libc::MSG_CTRUNC) != 0 {
        return Err("Truncated event".into());
    }
    let header = unsafe { libc::CMSG_FIRSTHDR(&message) };
    if header.is_null()
        || unsafe {
            (*header).cmsg_type != libc::SCM_CREDENTIALS || (*header).cmsg_level != libc::SOL_SOCKET
        }
    {
        return Err("Missing sender credentials".into());
    }
    let peer = unsafe { std::ptr::read_unaligned(libc::CMSG_DATA(header).cast::<libc::ucred>()) };
    if !allowed(peer.uid) {
        return Err("Unauthorized event sender".into());
    }
    data.truncate(size as usize);
    Ok((data, peer.uid, peer.pid))
}
#[cfg(not(target_os = "linux"))]
fn receive(_: &UnixDatagram) -> Result<(Vec<u8>, u32, i32)> {
    Err("Linux credentials required".into())
}

fn process_pending(cursor: &mut String) -> Result<()> {
    let mut connection = database::connect().ok();
    let pending = Path::new(STATE).join("pending");
    let mut entries = fs::read_dir(pending)?.collect::<std::io::Result<Vec<_>>>()?;
    entries.sort_by_key(|entry| entry.file_name());
    let split = entries
        .partition_point(|entry| entry.file_name().to_string_lossy().as_ref() <= cursor.as_str());
    let entries = entries[split..].iter().chain(entries[..split].iter());
    for entry in entries.take(256) {
        *cursor = entry.file_name().to_string_lossy().into_owned();
        if !entry.file_type()?.is_file()
            || entry.path().extension().and_then(|x| x.to_str()) != Some("json")
        {
            continue;
        }
        let event: Event = serde_json::from_slice(&fs::read(entry.path())?)?;
        export::write(Path::new(EXPORT), &event)?;
        if let Some(c) = &mut connection {
            database::insert(c, &event)?;
            fs::remove_file(entry.path())?;
        }
    }
    if let Some(c) = &mut connection {
        database::retain(c)?;
    } else {
        return Err("MySQL unavailable; events remain queued and exported".into());
    }
    Ok(())
}

fn query_server(listener: UnixListener, health: Arc<Health>) {
    for stream in listener.incoming() {
        let Ok(mut stream) = stream else {
            continue;
        };
        let reply = (|| -> Result<serde_json::Value> {
            stream.set_read_timeout(Some(Duration::from_secs(2)))?;
            stream.set_write_timeout(Some(Duration::from_secs(2)))?;
            #[cfg(target_os = "linux")]
            {
                let mut peer: libc::ucred = unsafe { std::mem::zeroed() };
                let mut length = std::mem::size_of_val(&peer) as libc::socklen_t;
                if unsafe {
                    libc::getsockopt(
                        stream.as_raw_fd(),
                        libc::SOL_SOCKET,
                        libc::SO_PEERCRED,
                        (&mut peer as *mut libc::ucred).cast(),
                        &mut length,
                    )
                } != 0
                    || !allowed(peer.uid)
                {
                    return Err("Unauthorized diagnostic reader".into());
                }
            }
            let mut buffer = Vec::new();
            (&mut stream).take(129).read_to_end(&mut buffer)?;
            if buffer.len() > 128 {
                return Err("Query too long".into());
            }
            let filter = std::str::from_utf8(&buffer)?.trim();
            if filter == "status" {
                return Ok(
                    json!({"categories":categories::ALL,"database":*health.database.lock().map_err(|_| "Health unavailable")?,
                    "accepted":health.accepted.load(Ordering::Relaxed),"rejected":health.rejected.load(Ordering::Relaxed),
                    "dropped":health.dropped.load(Ordering::Relaxed),"pending":fs::read_dir(Path::new(STATE).join("pending"))?.count(),
                    "exports":EXPORT}),
                );
            }
            database::query(filter).or_else(|_| export::query(Path::new(EXPORT), filter))
        })();
        let reply = match reply {
            Ok(value) => value,
            Err(error) => json!({"error":crate::event::redact(&error.to_string())}),
        };
        if let Ok(bytes) = serde_json::to_vec(&reply) {
            let _ = stream.write_all(&bytes);
        }
    }
}

pub(crate) fn query(args: &[String]) -> Result<()> {
    if args.len() > 1 {
        return Err("Use errors [category|event-id|status]".into());
    }
    let filter = args.first().map(String::as_str).unwrap_or("");
    if !filter.is_empty()
        && filter != "status"
        && !categories::ALL.contains(&filter)
        && uuid::Uuid::parse_str(filter).is_err()
    {
        return Err("Unknown error category or event ID".into());
    }
    let mut socket = UnixStream::connect(format!("{RUNTIME}/query.sock"))?;
    #[cfg(target_os = "linux")]
    {
        let mut peer: libc::ucred = unsafe { std::mem::zeroed() };
        let mut length = std::mem::size_of_val(&peer) as libc::socklen_t;
        if unsafe {
            libc::getsockopt(
                socket.as_raw_fd(),
                libc::SOL_SOCKET,
                libc::SO_PEERCRED,
                (&mut peer as *mut libc::ucred).cast(),
                &mut length,
            )
        } != 0
            || peer.uid != provision::uid("cnc-errors")?
        {
            return Err("Untrusted error-query service".into());
        }
    }
    socket.set_read_timeout(Some(Duration::from_secs(10)))?;
    socket.set_write_timeout(Some(Duration::from_secs(2)))?;
    socket.write_all(filter.as_bytes())?;
    socket.shutdown(std::net::Shutdown::Write)?;
    let mut bytes = Vec::new();
    socket.take(2 * 1024 * 1024).read_to_end(&mut bytes)?;
    let result: serde_json::Value = serde_json::from_slice(&bytes)?;
    println!("{}", serde_json::to_string_pretty(&result)?);
    if result.get("error").is_some() {
        return Err("Diagnostic query failed".into());
    }
    Ok(())
}

pub(crate) fn run() -> Result<()> {
    if unsafe { libc::geteuid() } != provision::uid("cnc-errors")? {
        return Err("Dedicated error account required".into());
    }
    crate::config::load()?;
    let health = Arc::new(Health::default());
    std::thread::spawn(crate::native_logs::run);
    for name in ["events.sock", "query.sock"] {
        let path = Path::new(RUNTIME).join(name);
        if path.exists() {
            fs::remove_file(path)?;
        }
    }
    let socket = UnixDatagram::bind(betterlinuxcnc_error_client::SOCKET)?;
    #[cfg(target_os = "linux")]
    {
        let enabled: libc::c_int = 1;
        if unsafe {
            libc::setsockopt(
                socket.as_raw_fd(),
                libc::SOL_SOCKET,
                libc::SO_PASSCRED,
                (&enabled as *const libc::c_int).cast(),
                std::mem::size_of_val(&enabled) as libc::socklen_t,
            )
        } != 0
        {
            return Err(std::io::Error::last_os_error().into());
        }
    }
    fs::set_permissions(
        betterlinuxcnc_error_client::SOCKET,
        fs::Permissions::from_mode(0o660),
    )?;
    let listener = UnixListener::bind(format!("{RUNTIME}/query.sock"))?;
    fs::set_permissions(
        format!("{RUNTIME}/query.sock"),
        fs::Permissions::from_mode(0o660),
    )?;
    let query_health = Arc::clone(&health);
    std::thread::spawn(move || query_server(listener, query_health));
    let database_health = Arc::clone(&health);
    std::thread::spawn(move || {
        let mut child: Option<std::process::Child> = None;
        let mut ticks: u64 = 0;
        let mut cursor = String::new();
        let mut last_error = String::new();
        loop {
            let running = child
                .as_mut()
                .is_some_and(|c| c.try_wait().ok() == Some(None));
            let mut startup_error = None;
            if !running {
                match database::start() {
                    Ok(process) => child = Some(process),
                    Err(error) => {
                        startup_error = Some(crate::event::redact(&error.to_string()));
                    }
                }
            }
            let result = process_pending(&mut cursor);
            let message = startup_error.unwrap_or_else(|| {
                result
                    .map(|_| "ready".to_string())
                    .unwrap_or_else(|error| crate::event::redact(&error.to_string()))
            });
            if message != "ready" && message != last_error {
                eprintln!("Error storage: {message}");
                betterlinuxcnc_error_client::report("error-records", "storage_error", &message);
            }
            last_error.clone_from(&message);
            if let Ok(mut state) = database_health.database.lock() {
                *state = message;
            }
            ticks += 1;
            if ticks.is_multiple_of(60) {
                let _ = export::retain(Path::new(EXPORT));
            }
            std::thread::sleep(Duration::from_secs(1));
        }
    });
    loop {
        match receive(&socket).and_then(|(bytes, uid, pid)| Event::receive(&bytes, uid, pid)) {
            Ok(event) => match export::spool(&Path::new(STATE).join("pending"), &event) {
                Ok(()) => {
                    health.accepted.fetch_add(1, Ordering::Relaxed);
                }
                Err(_) => {
                    health.dropped.fetch_add(1, Ordering::Relaxed);
                }
            },
            Err(_) => {
                health.rejected.fetch_add(1, Ordering::Relaxed);
            }
        }
    }
}
