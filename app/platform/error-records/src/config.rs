use crate::Result;
use serde::{Deserialize, Serialize};
use std::{fs, os::unix::fs::MetadataExt, path::Path, sync::OnceLock};

pub(crate) const PATH: &str = "/etc/betterlinuxcnc/error-records/config.toml";

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Config {
    pub pending_events: usize,
    pub export_days: u64,
    pub export_mib: u64,
    pub database_days: i64,
    pub database_events: u64,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            pending_events: 8192,
            export_days: 30,
            export_mib: 256,
            database_days: 90,
            database_events: 100000,
        }
    }
}
static POLICY: OnceLock<Config> = OnceLock::new();
pub(crate) fn get() -> &'static Config {
    POLICY.get_or_init(Config::default)
}
pub(crate) fn load() -> Result<()> {
    let path = Path::new(PATH);
    let info = fs::symlink_metadata(path)?;
    if !info.is_file() || info.uid() != 0 || info.mode() & 0o022 != 0 || info.len() > 4096 {
        return Err("Untrusted error-record retention configuration".into());
    }
    let value: Config = toml::from_str(&fs::read_to_string(path)?)?;
    if !(128..=32768).contains(&value.pending_events)
        || !(1..=90).contains(&value.export_days)
        || !(16..=1024).contains(&value.export_mib)
        || !(1..=365).contains(&value.database_days)
        || !(1000..=500000).contains(&value.database_events)
    {
        return Err("Error retention configuration exceeds supported bounds".into());
    }
    POLICY
        .set(value)
        .map_err(|_| "Error policy already loaded".into())
}
