use crate::{event::Event, Result};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::OpenOptionsExt,
    path::Path,
};

pub(crate) fn atomic(path: &Path, bytes: &[u8]) -> Result<()> {
    let temporary = path.with_extension(format!("tmp-{}", uuid::Uuid::new_v4()));
    let result = (|| {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o640)
            .open(&temporary)?;
        file.write_all(bytes)?;
        file.sync_all()?;
        fs::rename(&temporary, path)?;
        fs::File::open(path.parent().ok_or("Missing parent")?)?.sync_all()?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result
}

pub(crate) fn spool(root: &Path, event: &Event) -> Result<()> {
    let capacity = crate::config::get().pending_events;
    let count = fs::read_dir(root)?.take(capacity + 1).count();
    if count >= capacity {
        return Err("Pending event capacity exhausted".into());
    }
    let bytes = serde_json::to_vec(event)?;
    atomic(&root.join(format!("{}.json", event.event_id)), &bytes)
}

pub(crate) fn write(root: &Path, event: &Event) -> Result<()> {
    if !crate::categories::ALL.contains(&event.category.as_str())
        || chrono::DateTime::parse_from_rfc3339(&event.timestamp).is_err()
    {
        return Err("Invalid export category or date".into());
    }
    let directory = root.join(&event.category).join(&event.timestamp[..10]);
    fs::create_dir_all(&directory)?;
    // Stable hourly segments make retries idempotent, without cross-category state.
    let prefix = &event.timestamp[11..13];
    let mut index = 1;
    loop {
        let path = directory.join(format!("events-{prefix}-{index:04}.jsonl"));
        let mut data = match fs::read(&path) {
            Ok(data) => data,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Vec::new(),
            Err(e) => return Err(e.into()),
        };
        if data
            .windows(event.event_id.len())
            .any(|s| s == event.event_id.as_bytes())
        {
            return Ok(());
        }
        if data.len() >= 1024 * 1024 {
            index += 1;
            continue;
        }
        data.extend(serde_json::to_vec(event)?);
        data.push(b'\n');
        return atomic(&path, &data);
    }
}

pub(crate) fn retain(root: &Path) -> Result<()> {
    let mut files = Vec::new();
    for category in crate::categories::ALL {
        for day in fs::read_dir(root.join(category))? {
            let day = day?;
            if !day.file_type()?.is_dir() {
                continue;
            }
            for file in fs::read_dir(day.path())? {
                let file = file?;
                if file.file_type()?.is_file()
                    && file.file_name().to_string_lossy().ends_with(".jsonl")
                {
                    let info = file.metadata()?;
                    files.push((info.modified()?, info.len(), file.path()));
                }
            }
        }
    }
    files.sort();
    let mut size: u64 = files.iter().map(|item| item.1).sum();
    for (modified, length, path) in files {
        let policy = crate::config::get();
        let old = modified
            .elapsed()
            .map(|age| age.as_secs() > policy.export_days * 86400)
            .unwrap_or(false);
        if old || size > policy.export_mib * 1024 * 1024 {
            fs::remove_file(&path)?;
            size = size.saturating_sub(length);
        }
        if let Some(parent) = path.parent() {
            let _ = fs::remove_dir(parent);
        }
    }
    Ok(())
}

pub(crate) fn query(root: &Path, filter: &str) -> Result<serde_json::Value> {
    if !filter.is_empty()
        && !crate::categories::ALL.contains(&filter)
        && uuid::Uuid::parse_str(filter).is_err()
    {
        return Err("Unknown error category or event ID".into());
    }
    let mut files = Vec::new();
    for category in crate::categories::ALL {
        if crate::categories::ALL.contains(&filter) && filter != *category {
            continue;
        }
        for day in fs::read_dir(root.join(category))? {
            let day = day?;
            if !day.file_type()?.is_dir() {
                continue;
            }
            for file in fs::read_dir(day.path())? {
                let file = file?;
                if file.file_type()?.is_file()
                    && file.path().extension().is_some_and(|s| s == "jsonl")
                {
                    files.push((file.metadata()?.modified()?, file.path()));
                }
            }
        }
    }
    files.sort();
    let mut records = Vec::<Event>::new();
    // Keep offline reads bounded even after long periods without MySQL.
    for (_, path) in files.into_iter().rev().take(32) {
        let bytes = fs::read(path)?;
        for line in bytes.split(|b| *b == b'\n').filter(|line| !line.is_empty()) {
            let event: Event = serde_json::from_slice(line)?;
            if filter.is_empty() || filter == event.category || filter == event.event_id {
                records.push(event);
            }
        }
        if records.len() >= 100 {
            break;
        }
    }
    records.sort_by_key(|e| std::cmp::Reverse(e.received_ms));
    records.truncate(100);
    Ok(
        serde_json::json!({"database":"unavailable","source":"exports","events":records,"limit":100,"bounded_files":32}),
    )
}
