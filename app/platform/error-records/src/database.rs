use crate::{event::Event, Result};
use mysql::{prelude::Queryable, Conn, OptsBuilder};
use std::{
    fs,
    io::{BufRead, BufReader, Write},
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::Path,
    process::{Child, Command, Stdio},
    time::Duration,
};

pub(crate) const DATA: &str = "/var/lib/mysql/betterlinuxcnc-errors";
fn options(password: Option<String>) -> OptsBuilder {
    OptsBuilder::new()
        .socket(Some(format!("{}/mysql/mysql.sock", crate::RUNTIME)))
        .user(Some("root"))
        .pass(password)
        .read_timeout(Some(Duration::from_secs(3)))
        .write_timeout(Some(Duration::from_secs(3)))
}
pub(crate) fn connect() -> Result<Conn> {
    let password = fs::read_to_string(format!("{}/mysql-password", crate::STATE))?;
    let mut connection = Conn::new(options(Some(password)))?;
    connection.query_drop("USE betterlinuxcnc_errors")?;
    Ok(connection)
}
fn server() -> Command {
    let base = format!("{}/mysql/usr", crate::BASE);
    let mut command = Command::new(format!("{base}/sbin/mysqld"));
    command.args([
        "--no-defaults",
        &format!("--basedir={base}"),
        &format!("--datadir={DATA}"),
        &format!("--plugin-dir={base}/lib/mysql/plugin"),
        &format!("--lc-messages-dir={base}/share/mysql"),
        "--skip-networking",
        "--mysqlx=OFF",
        "--skip-log-bin",
        "--local-infile=OFF",
        "--secure-file-priv=NULL",
        "--innodb-buffer-pool-size=64M",
        "--innodb-redo-log-capacity=64M",
        "--max-connections=8",
        &format!("--socket={}/mysql/mysql.sock", crate::RUNTIME),
        &format!("--pid-file={}/mysql/mysql.pid", crate::RUNTIME),
    ]);
    command.stdin(Stdio::null());
    command
}
pub(crate) fn start() -> Result<Child> {
    let private = Path::new(crate::RUNTIME).join("mysql");
    fs::create_dir_all(&private)?;
    fs::set_permissions(&private, fs::Permissions::from_mode(0o700))?;
    let password_path = Path::new(crate::STATE).join("mysql-password");
    let marker = Path::new(crate::STATE).join("initializing");
    if !Path::new(DATA).join("mysql").exists() {
        if fs::read_dir(DATA)?.next().is_some() {
            return Err("Unrecognized partial MySQL data directory".into());
        }
        if !password_path.exists() {
            let mut file = fs::OpenOptions::new()
                .create_new(true)
                .write(true)
                .mode(0o600)
                .open(&password_path)?;
            file.write_all(
                format!(
                    "{}{}",
                    uuid::Uuid::new_v4().simple(),
                    uuid::Uuid::new_v4().simple()
                )
                .as_bytes(),
            )?;
            file.sync_all()?;
        }
        fs::write(&marker, b"private-bootstrap-v1")?;
        if !server().arg("--initialize-insecure").status()?.success() {
            return Err("Private MySQL initialization failed".into());
        }
    }
    let mut child = server().stderr(Stdio::piped()).spawn()?;
    if let Some(stderr) = child.stderr.take() {
        std::thread::spawn(move || {
            for line in BufReader::new(stderr)
                .lines()
                .map_while(std::result::Result::ok)
            {
                if line.contains("[ERROR]") {
                    betterlinuxcnc_error_client::report("error-records", "database_error", &line);
                }
                eprintln!("{}", crate::event::redact(&line));
            }
        });
    }
    let initialized = (|| -> Result<()> {
        let password = fs::read_to_string(password_path)?;
        if password.len() != 64 || !password.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err("Invalid private MySQL credential".into());
        }
        let mut connection = None;
        for _ in 0..60 {
            if let Ok(c) = Conn::new(options(Some(password.clone()))) {
                connection = Some(c);
                break;
            }
            // Passwordless bootstrap is allowed only inside the private socket directory
            // while a protected, unfinished initialization marker exists.
            if marker.exists() {
                if let Ok(mut c) = Conn::new(options(None)) {
                    c.query_drop(format!(
                        "ALTER USER 'root'@'localhost' IDENTIFIED BY '{password}'"
                    ))?;
                    connection = Some(c);
                    break;
                }
            }
            if child.try_wait()?.is_some() {
                return Err("MySQL exited during startup".into());
            }
            std::thread::sleep(Duration::from_millis(500));
        }
        let mut c = connection.ok_or("MySQL readiness timed out")?;
        c.query_drop("CREATE DATABASE IF NOT EXISTS betterlinuxcnc_errors CHARACTER SET utf8mb4")?;
        c.query_drop("USE betterlinuxcnc_errors")?;
        c.query_drop("CREATE TABLE IF NOT EXISTS events (sequence BIGINT UNSIGNED AUTO_INCREMENT UNIQUE, event_id CHAR(36) PRIMARY KEY, received_ms BIGINT NOT NULL, category VARCHAR(32) NOT NULL, source VARCHAR(64) NOT NULL, document JSON NOT NULL, INDEX category_time(category,received_ms), INDEX event_time(received_ms))")?;
        if marker.exists() {
            fs::remove_file(marker)?;
        }
        Ok(())
    })();
    if let Err(error) = initialized {
        let _ = child.kill();
        let _ = child.wait();
        return Err(error);
    }
    Ok(child)
}
pub(crate) fn insert(connection: &mut Conn, event: &Event) -> Result<()> {
    connection.exec_drop("INSERT IGNORE INTO events(event_id,received_ms,category,source,document) VALUES(?,?,?,?,?)",
        (&event.event_id, event.received_ms, &event.category, &event.source, serde_json::to_string(event)?))?;
    Ok(())
}
pub(crate) fn query(filter: &str) -> Result<serde_json::Value> {
    let mut c = connect()?;
    let version: Option<String> = c.query_first("SELECT VERSION()")?;
    let rows: Vec<String> = if filter.is_empty() {
        c.query("SELECT CAST(document AS CHAR) FROM events ORDER BY sequence DESC LIMIT 100")?
    } else if crate::categories::ALL.contains(&filter) {
        c.exec("SELECT CAST(document AS CHAR) FROM events WHERE category=? ORDER BY sequence DESC LIMIT 100", (filter,))?
    } else if uuid::Uuid::parse_str(filter).is_ok() {
        c.exec(
            "SELECT CAST(document AS CHAR) FROM events WHERE event_id=? LIMIT 1",
            (filter,),
        )?
    } else {
        return Err("Unknown error category or event ID".into());
    };
    let records: Vec<serde_json::Value> = rows
        .iter()
        .map(|row| serde_json::from_str(row))
        .collect::<std::result::Result<_, _>>()?;
    Ok(
        serde_json::json!({"database":"MySQL", "server_version":version, "events":records,"limit":100}),
    )
}
pub(crate) fn retain(c: &mut Conn) -> Result<()> {
    let policy = crate::config::get();
    c.exec_drop(
        "DELETE FROM events WHERE received_ms < ? LIMIT 10000",
        (chrono::Utc::now().timestamp_millis() - policy.database_days * 86400000,),
    )?;
    let cutoff: Option<u64> = c.exec_first(
        "SELECT sequence FROM events ORDER BY sequence DESC LIMIT 1 OFFSET ?",
        (policy.database_events - 1,),
    )?;
    if let Some(cutoff) = cutoff {
        c.exec_drop(
            "DELETE FROM events WHERE sequence < ? LIMIT 10000",
            (cutoff,),
        )?;
    }
    Ok(())
}
