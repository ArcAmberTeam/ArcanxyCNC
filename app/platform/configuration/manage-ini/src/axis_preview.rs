//! Non-privileged file storage for the browser development server.
use crate::{axis_parameters, configuration};
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::{self, Write},
    os::{
        fd::AsRawFd,
        unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt},
    },
    path::{Path, PathBuf},
};

const PRESETS: [&str; 3] = [
    include_str!("../../../../../tools/appliance/templates/axis-3.ini"),
    include_str!("../../../../../tools/appliance/templates/axis-4.ini"),
    include_str!("../../../../../tools/appliance/templates/axis-5.ini"),
];

fn reply(dir: &Path, request: axis_parameters::Request) -> io::Result<serde_json::Value> {
    let lock = fs::OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .custom_flags(libc::O_NOFOLLOW)
        .open(dir.join(".lock"))?;
    // SAFETY: lock stays open across preset initialization and revision comparison.
    if unsafe { libc::flock(lock.as_raw_fd(), libc::LOCK_EX) } != 0 {
        return Err(io::Error::last_os_error());
    }
    for (index, template) in PRESETS.iter().enumerate() {
        let path = dir.join(format!("axis-{}.ini", index + 3));
        if !path.try_exists()? {
            let stage = dir.join(".seed");
            let mut file = fs::OpenOptions::new()
                .write(true)
                .create(true)
                .truncate(true)
                .mode(0o600)
                .custom_flags(libc::O_NOFOLLOW)
                .open(&stage)?;
            writeln!(file, "{}preview", axis_parameters::HEADER)?;
            file.write_all(template.as_bytes())?;
            file.sync_all()?;
            fs::rename(stage, path)?;
            fs::File::open(dir)?.sync_all()?;
        }
    }
    let count = match &request {
        axis_parameters::Request::Read { count } | axis_parameters::Request::Save { count, .. } => {
            *count
        }
    };
    let path = dir.join(axis_parameters::filename(count)?);
    let info = fs::symlink_metadata(&path)?;
    if !info.is_file() || info.nlink() != 1 || info.len() > 65536 {
        return Err(io::Error::other("Invalid preview profile"));
    }
    let mut content = fs::read_to_string(&path)?;
    if let axis_parameters::Request::Save {
        revision, changes, ..
    } = request
    {
        if revision != format!("{:x}", Sha256::digest(&content)) {
            return Err(io::Error::other("方案已被修改，请重新读取后保存"));
        }
        content = axis_parameters::edit(&content, count, &changes)?;
        configuration::replace(&path, &content, &path)?;
    }
    Ok(
        serde_json::json!({"revision":format!("{:x}",Sha256::digest(&content)), "values": axis_parameters::values(&content,count)?}),
    )
}

pub(super) fn run() -> u8 {
    let result = (|| {
        // SAFETY: these calls only inspect process credentials.
        let uid = unsafe { libc::getuid() };
        if uid == 0 || unsafe { libc::geteuid() } != uid {
            return Err(io::Error::other("Preview requires a non-privileged user"));
        }
        let dir = PathBuf::from(
            std::env::var_os("HOME").ok_or_else(|| io::Error::other("Missing home directory"))?,
        )
        .join(".local/share/betterlinuxcnc/axis-preview");
        fs::DirBuilder::new()
            .recursive(true)
            .mode(0o700)
            .create(&dir)?;
        let info = fs::symlink_metadata(&dir)?;
        if !info.is_dir() || info.uid() != uid || info.mode() & 0o077 != 0 {
            return Err(io::Error::other("Invalid preview directory"));
        }
        reply(
            &dir,
            serde_json::from_slice(&axis_parameters::input(16384)?)?,
        )
    })();
    let value = result.unwrap_or_else(|e| serde_json::json!({"error":e.to_string()}));
    if serde_json::to_writer(io::stdout(), &value).is_ok() {
        0
    } else {
        1
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axis_parameters::Request;

    #[test]
    fn edit_overwrites_only_the_selected_file_and_survives_reopening() {
        let dir = tempfile::tempdir().unwrap();
        let read = |count| reply(dir.path(), Request::Read { count }).unwrap();
        let before = read(4);
        let others = [read(3), read(5)];
        let save = || Request::Save {
            count: 4,
            revision: before["revision"].as_str().unwrap().into(),
            changes: [("C.measuredTravel".into(), "270".into())].into(),
        };
        assert_eq!(
            reply(dir.path(), save()).unwrap()["values"]["C.measuredTravel"],
            "270"
        );
        assert!(reply(dir.path(), save()).is_err());
        assert_eq!(read(4)["values"]["C.measuredTravel"], "270");
        assert_eq!([read(3), read(5)], others);
        assert!(fs::read_to_string(dir.path().join("axis-4.ini"))
            .unwrap()
            .contains("MEASURED_TRAVEL_DEG = 270"));
        assert_eq!(
            fs::read_dir(dir.path())
                .unwrap()
                .filter_map(Result::ok)
                .filter(|e| e.path().extension().is_some_and(|x| x == "ini"))
                .count(),
            3
        );
    }
}
