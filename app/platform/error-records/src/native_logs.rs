//! Observe native startup/driver stderr that has no structured application callback.
use crate::{event::Event, export, STATE};
use std::{
    collections::HashMap,
    fs,
    io::{Read, Seek, SeekFrom},
    os::unix::fs::MetadataExt,
    path::{Path, PathBuf},
    time::Duration,
};

pub(crate) fn run() {
    let errors =
        regex::Regex::new(r"(?i)\b(error|failed|failure|fault|traceback|exception|cannot)\b|错误")
            .expect("constant native error pattern");
    let ledger = Path::new(STATE).join("native-offsets.json");
    let mut offsets: HashMap<String, (u64, u64)> = fs::read(&ledger)
        .ok()
        .and_then(|bytes| serde_json::from_slice(&bytes).ok())
        .unwrap_or_default();
    loop {
        let mut paths = Vec::<PathBuf>::new();
        if let Ok(runs) = fs::read_dir("/var/log/betterlinuxcnc/launcher") {
            let mut runs: Vec<_> = runs
                .flatten()
                .filter(|r| r.file_type().is_ok_and(|kind| kind.is_dir()))
                .collect();
            runs.sort_by_key(|run| run.file_name());
            for run in runs.iter().rev().take(3) {
                if let Ok(files) = fs::read_dir(run.path()) {
                    for file in files.flatten() {
                        let name = file.file_name().to_string_lossy().into_owned();
                        if name.starts_with("linuxcnc-")
                            && name.ends_with(".log")
                            && file.file_type().is_ok_and(|kind| kind.is_file())
                        {
                            paths.push(file.path());
                        }
                    }
                }
            }
        }
        for path in &paths {
            let result = (|| -> crate::Result<()> {
                let mut file = fs::File::open(path)?;
                let info = file.metadata()?;
                let key = path.to_string_lossy().into_owned();
                let (inode, previous) = offsets.get(&key).copied().unwrap_or((info.ino(), 0));
                let start = if inode == info.ino() && previous <= info.len() {
                    previous
                } else {
                    0
                };
                file.seek(SeekFrom::Start(start))?;
                let mut bytes = Vec::new();
                file.take(65536).read_to_end(&mut bytes)?;
                let consumed = bytes
                    .iter()
                    .rposition(|byte| *byte == b'\n')
                    .map(|index| index + 1)
                    .unwrap_or(if bytes.len() == 65536 { 65536 } else { 0 });
                for line in String::from_utf8_lossy(&bytes[..consumed]).lines() {
                    if !errors.is_match(line) {
                        continue;
                    }
                    let input = serde_json::to_vec(
                        &serde_json::json!({"schema_version":1,"source":"native","code":"native_log_error","message":line.chars().take(2048).collect::<String>(),"context":{}}),
                    )?;
                    let event = Event::receive(&input, info.uid(), 0)?;
                    export::spool(&Path::new(STATE).join("pending"), &event)?;
                }
                offsets.insert(key, (info.ino(), start + consumed as u64));
                Ok(())
            })();
            if result.is_err() {
                continue;
            }
        }
        offsets.retain(|path, _| paths.iter().any(|p| p.to_string_lossy() == path.as_str()));
        if let Ok(bytes) = serde_json::to_vec(&offsets) {
            let _ = export::atomic(&ledger, &bytes);
        }
        std::thread::sleep(Duration::from_secs(2));
    }
}
