//! Machine-owned axis presets and the bounded operator parameter protocol.
use crate::{configuration, ini};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    fs,
    io::{self, Read, Write},
    path::{Path, PathBuf},
    process::{Command, Stdio},
};

const LAUNCHER: &str = "/etc/betterlinuxcnc/launcher.json";
pub(super) const HEADER: &str = "; BetterLinuxCNC axis profile from ";
type Values = BTreeMap<String, String>;

#[derive(Deserialize)]
#[serde(tag = "operation", rename_all = "snake_case", deny_unknown_fields)]
pub(super) enum Request {
    Read {
        count: u8,
    },
    Save {
        count: u8,
        revision: String,
        changes: Values,
    },
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Edit {
    revision: String,
    changes: Values,
}

fn axes(count: u8) -> io::Result<&'static str> {
    match count {
        3 => Ok("XYZ"),
        4 => Ok("XYZC"),
        5 => Ok("XYZAC"),
        _ => Err(io::Error::other("轴方案无效")),
    }
}

fn selected() -> io::Result<PathBuf> {
    configuration::ini_path(&configuration::load(Path::new(LAUNCHER))?.content)
}

pub(super) fn filename(count: u8) -> io::Result<String> {
    axes(count)?;
    Ok(format!("axis-{count}.ini"))
}

fn check_layout(text: &str, count: u8) -> io::Result<&'static str> {
    let coordinates = ini::get(text, "TRAJ", "COORDINATES")
        .unwrap_or("")
        .split_whitespace()
        .collect::<String>()
        .to_ascii_uppercase();
    let layout = if count == 5 && coordinates == "XYZBC" {
        "XYZBC"
    } else {
        axes(count)?
    };
    if coordinates != layout
        || ini::get(text, "KINS", "JOINTS").and_then(|s| s.parse::<u8>().ok()) != Some(count)
    {
        return Err(io::Error::other("INI 与所选轴方案不匹配"));
    }
    Ok(layout)
}

fn check_profile(text: &str, count: u8) -> io::Result<&str> {
    let layout = check_layout(text, count)?;
    let mut args = ini::get(text, "KINS", "KINEMATICS")
        .unwrap_or("")
        .split_whitespace();
    let model = args.next().unwrap_or("");
    let default_order = match (model, layout) {
        ("trivkins", _) => &"XYZABCUVW"[..count as usize],
        ("xyzac-trt-kins", "XYZAC") | ("xyzbc-trt-kins", "XYZBC") => layout,
        _ => return Err(io::Error::other("运动学模型与轴方案不匹配")),
    };
    let mut orders = args.filter_map(|arg| arg.strip_prefix("coordinates="));
    if !orders
        .next()
        .unwrap_or(default_order)
        .eq_ignore_ascii_case(layout)
        || orders.next().is_some()
    {
        return Err(io::Error::other("此方案的关节顺序与轴顺序不一致"));
    }
    if ini::get(text, "TRAJ", "LINEAR_UNITS").is_some_and(|unit| !matches!(unit, "mm" | "metric"))
        || (count > 3
            && ini::get(text, "TRAJ", "ANGULAR_UNITS")
                .is_some_and(|unit| !matches!(unit, "deg" | "degree")))
    {
        return Err(io::Error::other("此参数表需要毫米和度数配置"));
    }
    Ok(model)
}

fn number(raw: &str) -> io::Result<f64> {
    raw.parse::<f64>()
        .ok()
        .filter(|n| n.is_finite())
        .ok_or_else(|| io::Error::other("参数需要有限数值"))
}

const FIELDS: &[&str] = &[
    "min",
    "max",
    "maxFeed",
    "acceleration",
    "homeSequence",
    "homeOffset",
    "scale",
    "direction",
    "estimatedTravel",
    "measuredTravel",
    "ratio",
    "mechanicalZero",
    "angleMin",
    "angleMax",
];

fn entry(axis: char, joint: usize, field: &str) -> io::Result<(String, String)> {
    let ax = format!("AXIS_{axis}");
    let j = format!("JOINT_{joint}");
    let rotary = "ABC".contains(axis);
    let (section, key) = match field {
        "min" => (ax, "MIN_LIMIT"),
        "max" => (ax, "MAX_LIMIT"),
        "maxFeed" => (ax, "MAX_VELOCITY"),
        "acceleration" => (ax, "MAX_ACCELERATION"),
        "homeSequence" => (j, "HOME_SEQUENCE"),
        "homeOffset" => (j, "HOME_OFFSET"),
        "scale" | "direction" => (j, "STEP_SCALE"),
        "estimatedTravel" => (ax, "ESTIMATED_TRAVEL"),
        "measuredTravel" if !rotary => {
            return Ok(("BETTERCNC_HOMING".into(), format!("TRAVEL_{axis}_MM")))
        }
        "measuredTravel" => (ax, "MEASURED_TRAVEL_DEG"),
        "ratio" if rotary => (ax, "TRANSMISSION_RATIO"),
        "mechanicalZero" if rotary => (ax, "MECHANICAL_ZERO"),
        "angleMin" if rotary => (j, "MIN_LIMIT"),
        "angleMax" if rotary => (j, "MAX_LIMIT"),
        _ => return Err(io::Error::other("该参数需要匹配的机床接线或运动学配置")),
    };
    Ok((section, key.into()))
}

pub(super) fn values(text: &str, count: u8) -> io::Result<Values> {
    let model = check_profile(text, count)?;
    let layout = check_layout(text, count)?;
    let mut values = Values::new();
    values.insert("model".into(), model.into());
    values.insert("axes".into(), layout.into());
    for (joint, axis) in layout.chars().enumerate() {
        values.insert(format!("{axis}.joint"), joint.to_string());
        let section = format!("JOINT_{joint}");
        let enabled =
            |key| ini::get(text, &section, key).is_some_and(|s| matches!(s, "1" | "YES" | "TRUE"));
        let search = ini::get(text, &section, "HOME_SEARCH_VEL")
            .map(number)
            .transpose()?
            .unwrap_or(0.0);
        let homing = if ini::get(text, &section, "HOME_ABSOLUTE_ENCODER")
            .is_some_and(|s| matches!(s, "1" | "2"))
        {
            "absolute"
        } else {
            match (search != 0.0, enabled("HOME_USE_INDEX")) {
                (true, true) => "switch-index",
                (false, true) => "index",
                (true, false) => "switch",
                _ => "manual",
            }
        };
        if [
            "HOME",
            "HOME_OFFSET",
            "HOME_SEQUENCE",
            "HOME_SEARCH_VEL",
            "HOME_ABSOLUTE_ENCODER",
        ]
        .iter()
        .any(|key| ini::get(text, &section, key).is_some())
        {
            values.insert(format!("{axis}.homing"), homing.into());
        }
        for field in FIELDS {
            let Ok((section, key)) = entry(axis, joint, field) else {
                continue;
            };
            let Some(raw) = ini::get(text, &section, &key) else {
                continue;
            };
            let n = number(raw)?;
            let value = match *field {
                "maxFeed" => (n * 60.0).to_string(),
                "scale" => n.abs().to_string(),
                "direction" => if n < 0.0 { "negative" } else { "positive" }.into(),
                _ => raw.into(),
            };
            values.insert(format!("{axis}.{field}"), value);
        }
    }
    Ok(values)
}

//--------//
// BEGIN: AxisParameterEdits
pub(super) fn edit(text: &str, count: u8, changes: &Values) -> io::Result<String> {
    let model = check_profile(text, count)?;
    let layout = check_layout(text, count)?;
    let mut content = text.to_owned();
    for (name, raw) in changes {
        let (axis, field) = name
            .split_once('.')
            .ok_or_else(|| io::Error::other("参数名无效"))?;
        let joint = layout
            .find(axis)
            .filter(|_| axis.len() == 1)
            .ok_or_else(|| io::Error::other("方案中没有此轴"))?;
        let letter = layout.as_bytes()[joint] as char;
        let (section, key) = entry(letter, joint, field)?;
        let joint_section = format!("JOINT_{joint}");
        let mut n = if field == "direction" {
            let magnitude = changes
                .get(&format!("{axis}.scale"))
                .map(String::as_str)
                .or_else(|| ini::get(text, &section, &key))
                .ok_or_else(|| io::Error::other("需要先设置脉冲当量"))?;
            match raw.as_str() {
                "positive" => number(magnitude)?.abs(),
                "negative" => -number(magnitude)?.abs(),
                _ => return Err(io::Error::other("方向值无效")),
            }
        } else {
            number(raw)?
        };
        if matches!(
            field,
            "maxFeed" | "acceleration" | "scale" | "ratio" | "estimatedTravel" | "measuredTravel"
        ) && n <= 0.0
        {
            return Err(io::Error::other("速度、加速度、比例和行程必须大于零"));
        }
        if field == "direction" && n == 0.0 {
            return Err(io::Error::other("需要非零脉冲当量"));
        }
        if field == "homeSequence" && raw.parse::<i32>().is_err() {
            return Err(io::Error::other("回零顺序必须为整数"));
        }
        if field == "scale"
            && ini::get(&content, &section, &key)
                .map(number)
                .transpose()?
                .unwrap_or(1.0)
                < 0.0
        {
            n = -n;
        }
        if field == "maxFeed" {
            n /= 60.0;
        }
        if model == "trivkins" && matches!(field, "maxFeed" | "acceleration") {
            let limit = if field == "maxFeed" {
                "STEPGEN_MAXVEL"
            } else {
                "STEPGEN_MAXACCEL"
            };
            if let Some(raw_limit) = ini::get(text, &joint_section, limit) {
                if n > number(raw_limit)? {
                    return Err(io::Error::other(format!(
                        "{axis} 轴数值超过已配置的 {limit}"
                    )));
                }
            }
        }
        let value = n.to_string();
        content = ini::set(&content, &section, &key, &value)?;
        if model == "trivkins"
            && (matches!(field, "maxFeed" | "acceleration")
                || ("XYZ".contains(letter) && matches!(field, "min" | "max")))
        {
            content = ini::set(&content, &joint_section, &key, &value)?;
        }
        if matches!(field, "direction" | "scale")
            && ini::get(text, "BETTERCNC_HOMING", "PROFILE").is_some()
        {
            content = ini::set(
                &content,
                "BETTERCNC_HOMING",
                "MOTOR_DIRECTIONS_VERIFIED",
                "NO",
            )?;
        }
    }
    for (joint, axis) in layout.chars().enumerate() {
        for section in [format!("AXIS_{axis}"), format!("JOINT_{joint}")] {
            if let (Some(min), Some(max)) = (
                ini::get(&content, &section, "MIN_LIMIT"),
                ini::get(&content, &section, "MAX_LIMIT"),
            ) {
                if number(min)? >= number(max)? {
                    return Err(io::Error::other(format!("{axis} 轴行程上下限无效")));
                }
            }
        }
    }
    if content.len() > 65536 {
        return Err(io::Error::other("轴配置超过 64 KiB"));
    }
    ini::validate(&content)?;
    Ok(content)
}
// END: AxisParameterEdits
//--------//

pub(super) fn input(limit: usize) -> io::Result<Vec<u8>> {
    let mut buf = Vec::new();
    io::stdin().take(limit as u64 + 1).read_to_end(&mut buf)?;
    if buf.len() > limit {
        return Err(io::Error::other("请求超过长度限制"));
    }
    Ok(buf)
}

fn profile(count: u8) -> io::Result<(PathBuf, configuration::Document)> {
    let active = selected()?;
    let path = active.with_file_name(filename(count)?);
    let doc = configuration::load(&path)?;
    check_profile(&doc.content, count)?;
    let source = doc
        .content
        .lines()
        .next()
        .and_then(|s| s.strip_prefix(HEADER));
    let active_doc = configuration::load(&active)?;
    let active_source = active_doc
        .content
        .lines()
        .next()
        .and_then(|s| s.strip_prefix(HEADER))
        .or_else(|| active.file_name()?.to_str());
    if source.or_else(|| path.file_name()?.to_str()) != active_source {
        return Err(io::Error::other("方案所属机床已改变"));
    }
    Ok((path, doc))
}

fn profile_hal(path: &Path) -> impl Fn(&str) -> io::Result<String> + '_ {
    move |name| Ok(configuration::load(&path.with_file_name(name))?.content)
}

fn read_wiring(
    text: &str,
    load_hal: impl Fn(&str) -> io::Result<String>,
    count: u8,
    values: &mut Values,
) -> io::Result<Values> {
    let layout = check_layout(text, count)?;
    let model = check_profile(text, count)?;
    let mut geometry = Values::new();
    let mut net_pins = std::collections::BTreeSet::new();
    let mut owners = Values::new();
    let mut commands = Vec::new();
    let mut read_line = |line: &str, uses_ini: bool| -> io::Result<()> {
        let mut words = line.split('#').next().unwrap_or("").split_whitespace();
        match words.next() {
            Some("net" | "linksp" | "linkps" | "linkpp") => {
                net_pins.extend(
                    words
                        .filter(|pin| pin.starts_with(model))
                        .map(str::to_owned),
                );
                return Ok(());
            }
            Some("setp") => {}
            _ => return Ok(()),
        }
        let (Some(pin), Some(setting), None) = (words.next(), words.next(), words.next()) else {
            return Ok(());
        };
        if let Some((_, suffix)) = pin.rsplit_once(".stepgen.") {
            let channel = suffix
                .strip_suffix(".position-scale")
                .and_then(|s| s.parse::<u32>().ok());
            let joint = setting
                .strip_prefix("[JOINT_")
                .and_then(|s| s.strip_suffix("]STEP_SCALE"))
                .and_then(|s| s.parse::<usize>().ok());
            if let (Some(channel), Some(axis)) =
                (channel, joint.and_then(|n| layout.chars().nth(n)))
            {
                values.insert(format!("{axis}.drive"), channel.to_string());
            }
        }
        if model == "trivkins" {
            return Ok(());
        }
        let Some(field) = pin.strip_prefix(model).and_then(|s| s.strip_prefix('.')) else {
            return Ok(());
        };
        let (name, key) = match field {
            "x-rot-point" => ("centerX", "CENTER_X"),
            "y-rot-point" => ("centerY", "CENTER_Y"),
            "z-rot-point" => ("centerZ", "CENTER_Z"),
            "x-offset" if model == "xyzbc-trt-kins" => ("offsetX", "OFFSET_X"),
            "y-offset" if model == "xyzac-trt-kins" => ("offsetY", "OFFSET_Y"),
            "z-offset" => ("offsetZ", "OFFSET_Z"),
            _ => return Ok(()),
        };
        let name = format!("{model}.{name}");
        geometry.remove(&name);
        values.remove(&name);
        if uses_ini && setting == format!("[RTCP]{key}") {
            if let Some(raw) = ini::get(text, "RTCP", key) {
                number(raw)?;
                owners.insert(name.clone(), pin.into());
                geometry.insert(name.clone(), key.into());
                values.insert(name, raw.into());
            }
        }
        Ok(())
    };
    let mut section = "";
    for line in text.lines() {
        let line = line.split(['#', ';']).next().unwrap_or("").trim();
        if line.starts_with('[') {
            section = line;
            continue;
        }
        if section != "[HAL]" {
            continue;
        }
        let Some((key, setting)) = line.split_once('=') else {
            continue;
        };
        match key.trim() {
            "HALCMD" => commands.push(setting),
            "HALFILE" => {
                let name = setting.trim().trim_matches('"');
                if name.contains(['/', '\\']) || !name.ends_with(".hal") {
                    return Err(io::Error::other("不支持的 HAL 路径"));
                }
                let hal = load_hal(name)?;
                for line in hal.lines() {
                    read_line(line, true)?;
                }
            }
            _ => {}
        }
    }
    for command in commands {
        read_line(command, false)?;
    }
    for (name, pin) in owners {
        if net_pins.contains(&pin) {
            geometry.remove(&name);
            values.remove(&name);
        }
    }
    Ok(geometry)
}

fn checked(
    load_hal: impl Fn(&str) -> io::Result<String>,
    doc: &configuration::Document,
    count: u8,
    request: &Edit,
) -> io::Result<String> {
    if doc.revision != request.revision {
        return Err(io::Error::other("方案已被修改，请重新读取后保存"));
    }
    if !request.changes.keys().any(|key| key.contains("-trt-kins.")) {
        return edit(&doc.content, count, &request.changes);
    }
    let geometry = read_wiring(&doc.content, load_hal, count, &mut Values::new())?;
    let mut motion = Values::new();
    let mut content = doc.content.clone();
    for (name, value) in &request.changes {
        if let Some(key) = geometry.get(name) {
            content = ini::set(&content, "RTCP", key, &number(value)?.to_string())?;
        } else {
            motion.insert(name.clone(), value.clone());
        }
    }
    edit(&content, count, &motion)
}

fn save_active(count: u8, change: &Edit) -> io::Result<()> {
    let mut child = Command::new("/usr/bin/betterlinuxcnc-updater")
        .args(["axis-maintenance", &count.to_string(), "--parameters"])
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LANG", "C.UTF-8")
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()?;
    let mut pipe = child
        .stdin
        .take()
        .ok_or_else(|| io::Error::other("无法发送轴参数"))?;
    serde_json::to_writer(&mut pipe, change)?;
    drop(pipe);
    let result = child.wait_with_output()?;
    if !result.status.success() {
        return Err(io::Error::other(
            String::from_utf8_lossy(&result.stderr).trim().to_owned(),
        ));
    }
    Ok(())
}

fn service() -> io::Result<serde_json::Value> {
    #[cfg(target_os = "linux")]
    {
        use std::os::fd::AsFd;
        let stream =
            std::os::unix::net::UnixStream::from(io::stdin().as_fd().try_clone_to_owned()?);
        stream.set_read_timeout(Some(std::time::Duration::from_secs(10)))?;
        let mut cred = std::mem::MaybeUninit::<libc::ucred>::uninit();
        let mut len = std::mem::size_of::<libc::ucred>() as libc::socklen_t;
        // SAFETY: systemd supplies the connected stream on fd 0. getsockopt initializes cred on success.
        if unsafe {
            libc::getsockopt(
                0,
                libc::SOL_SOCKET,
                libc::SO_PEERCRED,
                cred.as_mut_ptr().cast(),
                &mut len,
            )
        } != 0
        {
            return Err(io::Error::last_os_error());
        }
        let uid = crate::permissions::account_uid(c"linuxcnc").map_err(io::Error::other)?;
        if uid == 0
            || len as usize != std::mem::size_of::<libc::ucred>()
            || unsafe { cred.assume_init().uid } != uid
        {
            return Err(io::Error::other("未授权的轴参数请求"));
        }
    }
    let request: Request = serde_json::from_slice(&input(16384)?)?;
    let count = match &request {
        Request::Read { count } | Request::Save { count, .. } => *count,
    };
    let (path, mut doc) = profile(count)?;
    if let Request::Save {
        revision, changes, ..
    } = request
    {
        let change = Edit { revision, changes };
        let content = checked(profile_hal(&path), &doc, count, &change)?;
        if content != doc.content {
            let active = configuration::load(&selected()?)?;
            if check_layout(&active.content, count).is_err() {
                let _lock = configuration::update_lock()?;
                let (path, latest) = profile(count)?;
                if selected()? == path {
                    return Err(io::Error::other("方案已切换，请重新读取"));
                }
                let content = checked(profile_hal(&path), &latest, count, &change)?;
                configuration::replace(&path, &content, &path)?;
            } else {
                save_active(count, &change)?;
            }
            doc = profile(count)?.1;
            if doc.content != content {
                return Err(io::Error::other("未确认参数写入，请重新读取"));
            }
        }
    }
    let mut fields = values(&doc.content, count)?;
    read_wiring(&doc.content, profile_hal(&path), count, &mut fields)?;
    Ok(serde_json::json!({"revision":doc.revision, "values":fields}))
}

fn command(args: &[String]) -> io::Result<()> {
    match args {
        [op] if op == "axis-parameters" => {
            let reply = service().unwrap_or_else(|e| serde_json::json!({"error":e.to_string()}));
            serde_json::to_writer(io::stdout(), &reply)?;
        }
        [op, name] => {
            let count = (3..=5)
                .find(|c| name == &format!("axis-{c}.ini"))
                .ok_or_else(|| io::Error::other("Invalid preset name"))?;
            let active = selected()?;
            let path = if op == "stage-axis" {
                let stage = std::env::current_dir()?;
                configuration::trusted(&stage)?;
                if stage.parent() != Some(Path::new("/etc/betterlinuxcnc"))
                    || !stage
                        .file_name()
                        .and_then(|s| s.to_str())
                        .is_some_and(|s| s.starts_with(".axis-upgrade-"))
                {
                    return Err(io::Error::other("Invalid axis migration stage"));
                }
                stage.join(name)
            } else {
                active.with_file_name(name)
            };
            match op.as_str() {
                "seed-axis" | "stage-axis" => {
                    let text = String::from_utf8(input(65536)?).map_err(io::Error::other)?;
                    // A migration may preserve the original headerless active preset,
                    // but cannot substitute caller-provided contents for that source.
                    if !text.starts_with(HEADER)
                        && (op != "stage-axis"
                            || configuration::load(&active.with_file_name(name))?.content != text)
                    {
                        return Err(io::Error::other("Missing preset source"));
                    }
                    check_layout(&text, count)?;
                    match fs::symlink_metadata(&path) {
                        Ok(_) if configuration::load(&path)?.content == text => return Ok(()),
                        Ok(_) => return Err(io::Error::other("Existing preset preserved")),
                        Err(e) if e.kind() == io::ErrorKind::NotFound => {}
                        Err(e) => return Err(e),
                    }
                    configuration::replace(&path, &text, &active)?;
                }
                "validate-parameters" | "commit-parameters" => {
                    let current = configuration::load(&active)?;
                    if check_layout(&current.content, count).is_err() {
                        return Err(io::Error::other("当前轴方案已改变，请重新选择"));
                    }
                    let (_, doc) = profile(count)?;
                    let change: Edit = serde_json::from_slice(&input(16384)?)?;
                    let text = checked(profile_hal(&path), &doc, count, &change)?;
                    if op == "commit-parameters" {
                        configuration::replace(&path, &text, &path)?;
                    }
                }
                _ => return Err(io::Error::other("Unknown preset command")),
            }
        }
        _ => return Err(io::Error::other("Unknown preset command")),
    }
    Ok(())
}

pub(super) fn run() -> u8 {
    // SAFETY: these calls only inspect process credentials.
    if !cfg!(target_os = "linux") || unsafe { libc::getuid() != 0 || libc::geteuid() != 0 } {
        return 77;
    }
    match command(&std::env::args().skip(1).collect::<Vec<_>>()) {
        Ok(()) => 0,
        Err(e) => {
            let _ = writeln!(io::stderr(), "{e}");
            1
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const TEXT: &str = "; BetterLinuxCNC axis profile from mill.ini\n[KINS]\nJOINTS = 4\nKINEMATICS = trivkins coordinates=XYZC\n[TRAJ]\nCOORDINATES = XYZC\n[HAL]\nHALFILE = one.hal\nHALFILE = custom.hal\n[AXIS_X]\nMIN_LIMIT = -10\nMAX_LIMIT = 100\nMAX_VELOCITY = 5\n[JOINT_0]\nSTEP_SCALE = -100\n";

    #[test]
    fn saved_fields_round_trip_with_native_units_and_original_wiring() {
        let changes = Values::from([
            ("X.maxFeed".into(), "900".into()),
            ("X.scale".into(), "200".into()),
            ("X.estimatedTravel".into(), "300".into()),
            ("C.estimatedTravel".into(), "200".into()),
            ("C.measuredTravel".into(), "180".into()),
        ]);
        let saved = edit(TEXT, 4, &changes).unwrap();
        assert_eq!(ini::get(&saved, "AXIS_X", "MAX_VELOCITY"), Some("15"));
        assert_eq!(ini::get(&saved, "JOINT_0", "STEP_SCALE"), Some("-200"));
        assert_eq!(ini::get(&saved, "AXIS_X", "ESTIMATED_TRAVEL"), Some("300"));
        assert_eq!(ini::get(&saved, "BETTERCNC_HOMING", "TRAVEL_X_MM"), None);
        assert_eq!(
            ini::get(&saved, "AXIS_C", "MEASURED_TRAVEL_DEG"),
            Some("180")
        );
        assert!(saved.contains("HALFILE = one.hal\nHALFILE = custom.hal"));
        let observed = values(&saved, 4).unwrap();
        for (key, value) in changes {
            assert_eq!(observed[&key], value);
        }
    }

    #[test]
    fn bc_profile_edits_only_bound_geometry_and_preserves_joint_limits() {
        let doc = configuration::Document {
            content: "[KINS]\nJOINTS = 5\nKINEMATICS = xyzbc-trt-kins\n[TRAJ]\nCOORDINATES = XYZBC\n[RTCP]\nCENTER_X = -2\n[HAL]\nHALFILE = table.hal\n[JOINT_0]\nMAX_LIMIT = 200\n".into(),
            revision: "v1".into(),
            label: "axis-5.ini".into(),
        };
        let load_hal = |name: &str| {
            assert_eq!(name, "table.hal");
            Ok(String::from(
                "setp xyzbc-trt-kins.x-rot-point [RTCP]CENTER_X",
            ))
        };
        let mut fields = values(&doc.content, 5).unwrap();
        read_wiring(&doc.content, load_hal, 5, &mut fields).unwrap();
        assert_eq!(fields["axes"], "XYZBC");
        assert_eq!(fields["B.joint"], "3");
        assert_eq!(fields["xyzbc-trt-kins.centerX"], "-2");
        let mut change = Edit {
            revision: "v1".into(),
            changes: Values::from([
                ("xyzbc-trt-kins.centerX".into(), "1.75".into()),
                ("X.max".into(), "120".into()),
            ]),
        };
        let updated = checked(load_hal, &doc, 5, &change).unwrap();
        assert_eq!(ini::get(&updated, "RTCP", "CENTER_X"), Some("1.75"));
        assert_eq!(ini::get(&updated, "JOINT_0", "MAX_LIMIT"), Some("200"));
        change
            .changes
            .insert("xyzbc-trt-kins.offsetZ".into(), "3".into());
        assert!(checked(load_hal, &doc, 5, &change).is_err());
    }

    #[test]
    fn refuses_stale_versions_or_invalid_fields_before_any_save() {
        let doc = configuration::Document {
            content: TEXT.into(),
            revision: "v1".into(),
            label: "axis-4.ini".into(),
        };
        assert!(checked(
            profile_hal(Path::new("axis-4.ini")),
            &doc,
            4,
            &Edit {
                revision: "v0".into(),
                changes: Values::new()
            }
        )
        .is_err());
        for (key, value) in [
            ("X.min", "150"),
            ("X.maxFeed", "NaN"),
            ("X.scale", "0"),
            ("A.max", "40"),
            ("X.drive", "3"),
            ("X.min", "1\n[HAL]"),
        ] {
            assert!(edit(TEXT, 4, &Values::from([(key.into(), value.into())])).is_err());
        }
        assert!(values(TEXT, 5).is_err());
    }
}
