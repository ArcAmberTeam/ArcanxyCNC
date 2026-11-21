use serde::Serialize;
use std::fs::{self, File};
use std::io::{self, Read};
use std::path::Path;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemInfo {
    pub schema_version: u32,
    pub cpu: Option<Cpu>,
    pub gpus: Option<Vec<Gpu>>,
    pub memory: Option<Memory>,
    pub kernel: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Cpu {
    pub model: Option<String>,
    pub logical_cores: u32,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Gpu {
    pub model: String,
    pub vendor_id: String,
    pub device_id: String,
    pub driver: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Memory {
    pub total_bytes: u64,
    pub available_bytes: Option<u64>,
}

fn read_text(path: &Path, limit: u64) -> io::Result<String> {
    let mut text = String::new();
    File::open(path)?
        .take(limit + 1)
        .read_to_string(&mut text)?;
    if text.len() as u64 > limit {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "Input too large",
        ));
    }
    Ok(text)
}

fn field<'a>(text: &'a str, name: &str) -> Option<&'a str> {
    text.lines().find_map(|line| {
        let (key, value) = line.split_once(':')?;
        (key.trim() == name).then_some(value.trim())
    })
}

fn cpu(text: &str) -> Option<Cpu> {
    let logical_cores = text
        .lines()
        .filter_map(|line| line.split_once(':'))
        .filter(|(key, value)| key.trim() == "processor" && value.trim().parse::<u32>().is_ok())
        .count();
    if logical_cores == 0 {
        return None;
    }
    let model = field(text, "model name")
        .or_else(|| field(text, "Hardware"))
        .filter(|value| !value.is_empty())
        .map(|value| value.chars().take(256).collect());
    Some(Cpu {
        model,
        logical_cores: u32::try_from(logical_cores).ok()?,
    })
}

fn memory(text: &str) -> Option<Memory> {
    let bytes = |key| {
        let mut parts = field(text, key)?.split_whitespace();
        let value = parts.next()?.parse::<u64>().ok()?;
        if parts.next()? != "kB" || parts.next().is_some() {
            return None;
        }
        value.checked_mul(1024)
    };
    let total_bytes = bytes("MemTotal").filter(|value| *value > 0)?;
    Some(Memory {
        total_bytes,
        available_bytes: bytes("MemAvailable").filter(|value| *value <= total_bytes),
    })
}

fn pci_name(database: &str, vendor: &str, device: &str) -> Option<String> {
    let mut vendor_name = None;
    for line in database.lines() {
        if line.starts_with('#') || line.is_empty() {
            continue;
        }
        if !line.starts_with('\t') {
            if vendor_name.is_some() {
                break;
            }
            if let Some(name) = line.strip_prefix(&format!("{vendor}  ")) {
                vendor_name = Some(name.trim());
            }
        } else if let Some(vendor_name) = vendor_name {
            if let Some(name) = line.strip_prefix(&format!("\t{device}  ")) {
                return Some(format!("{vendor_name} {}", name.trim()));
            }
        }
    }
    None
}

fn hex_value(path: &Path) -> io::Result<u32> {
    let text = read_text(path, 64)?;
    u32::from_str_radix(text.trim().trim_start_matches("0x"), 16)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))
}

fn gpus(root: &Path, database: &str) -> io::Result<Vec<Gpu>> {
    let mut entries = fs::read_dir(root)?.collect::<Result<Vec<_>, _>>()?;
    entries.sort_by_key(|entry| entry.file_name());
    let mut result = Vec::new();
    for entry in entries {
        let path = entry.path();
        if hex_value(&path.join("class"))? >> 16 != 3 {
            continue;
        }
        let vendor_id = format!("{:04x}", hex_value(&path.join("vendor"))?);
        let device_id = format!("{:04x}", hex_value(&path.join("device"))?);
        let driver = fs::read_link(path.join("driver")).ok().and_then(|path| {
            path.file_name()
                .map(|name| name.to_string_lossy().into_owned())
        });
        let model = pci_name(database, &vendor_id, &device_id)
            .unwrap_or_else(|| format!("PCI {vendor_id}:{device_id}"));
        result.push(Gpu {
            model,
            vendor_id,
            device_id,
            driver,
        });
        if result.len() > 32 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "Too many GPUs"));
        }
    }
    Ok(result)
}

/// Read a host snapshot through fixed, unprivileged Linux interfaces.
pub fn collect() -> SystemInfo {
    let database = ["/usr/share/misc/pci.ids", "/usr/share/hwdata/pci.ids"]
        .iter()
        .find_map(|path| read_text(Path::new(path), 16 * 1024 * 1024).ok())
        .unwrap_or_default();
    SystemInfo {
        schema_version: 1,
        cpu: read_text(Path::new("/proc/cpuinfo"), 4 * 1024 * 1024)
            .ok()
            .and_then(|text| cpu(&text)),
        gpus: gpus(Path::new("/sys/bus/pci/devices"), &database).ok(),
        memory: read_text(Path::new("/proc/meminfo"), 64 * 1024)
            .ok()
            .and_then(|text| memory(&text)),
        kernel: read_text(Path::new("/proc/sys/kernel/osrelease"), 256)
            .ok()
            .map(|text| text.trim().to_owned())
            .filter(|text| !text.is_empty()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn memory_uses_available_not_free_and_rejects_invalid_units() {
        let info = memory("MemTotal: 8192 kB\nMemFree: 10 kB\nMemAvailable: 2048 kB").unwrap();
        assert_eq!(info.total_bytes, 8192 * 1024);
        assert_eq!(info.available_bytes, Some(2048 * 1024));
        assert!(memory("MemTotal: 100 MB").is_none());
        assert!(memory("MemTotal: 18446744073709551615 kB").is_none());
        assert_eq!(memory("MemTotal: 1 kB").unwrap().available_bytes, None);
        assert_eq!(
            memory("MemTotal: 1 kB\nMemAvailable: 2 kB")
                .unwrap()
                .available_bytes,
            None
        );
    }

    #[test]
    fn cpu_counts_logical_processors_without_inventing_a_model() {
        let info = cpu("processor: 0\nmodel name: Test CPU\n\nprocessor: 1").unwrap();
        assert_eq!(info.logical_cores, 2);
        assert_eq!(info.model.as_deref(), Some("Test CPU"));
        assert_eq!(cpu("processor: 0").unwrap().model, None);
        assert!(cpu("").is_none());
    }

    #[test]
    fn pci_names_do_not_cross_vendor_or_subsystem_boundaries() {
        let database =
            "1234  Vendor\n\t0001  GPU\n\t\t0002 0003  Subsystem\n5678  Other\n\t0004  Other GPU\n";
        assert_eq!(
            pci_name(database, "1234", "0001").as_deref(),
            Some("Vendor GPU")
        );
        assert_eq!(pci_name(database, "1234", "0004"), None);
        assert_eq!(pci_name(database, "1234", "0002"), None);
    }

    #[test]
    fn gpu_inventory_filters_non_display_devices_and_keeps_unknown_ids() {
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!("system-info-{}-{nonce}", std::process::id()));
        fs::create_dir(&root).unwrap();
        struct Cleanup(std::path::PathBuf);
        impl Drop for Cleanup {
            fn drop(&mut self) {
                let _ = fs::remove_dir_all(&self.0);
            }
        }
        let _cleanup = Cleanup(root.clone());
        for (name, class, device) in [
            ("0000:00:02.0", "0x030000", "0x0001"),
            ("0000:01:00.0", "0x030200", "0x0002"),
            ("0000:02:00.0", "0x020000", "0x0003"),
        ] {
            let path = root.join(name);
            fs::create_dir(&path).unwrap();
            fs::write(path.join("class"), class).unwrap();
            fs::write(path.join("vendor"), "0x1234").unwrap();
            fs::write(path.join("device"), device).unwrap();
        }
        let devices = gpus(&root, "1234  Vendor\n\t0001  Integrated GPU\n").unwrap();
        assert_eq!(devices.len(), 2);
        assert_eq!(devices[0].model, "Vendor Integrated GPU");
        assert_eq!(devices[1].model, "PCI 1234:0002");
        assert_eq!(devices[0].driver, None);
        fs::remove_file(root.join("0000:00:02.0/device")).unwrap();
        assert!(gpus(&root, "").is_err());
        assert!(gpus(&root.join("missing"), "").is_err());
    }
}
