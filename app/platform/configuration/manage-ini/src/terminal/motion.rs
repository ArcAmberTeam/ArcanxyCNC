//! Motion-settings navigation and session-only drafts; no machine or file access.

use super::{input::Key, language::Language};
use crate::ini;

struct Field {
    name: String,
    values: Vec<String>,
    unit: &'static str,
    rule: Rule,
    bindings: Vec<(String, String)>,
}

#[derive(Clone, Copy)]
enum Rule {
    Range,
    Positive,
    Number,
    Integer,
}

struct Group {
    name: &'static str,
    inline: bool,
    fields: Vec<Field>,
    help: &'static str,
}

struct Edit {
    values: Vec<Vec<String>>,
    field: usize,
    column: usize,
    replace: bool,
}

pub(super) struct Row {
    pub label: String,
    pub value: String,
    pub selected: bool,
    pub muted: bool,
}

//--------//
// BEGIN: MotionSettings
pub(super) struct MotionSettings {
    groups: Vec<Group>,
    group: usize,
    page: bool,
    field: usize,
    edit: Option<Edit>,
    demo: bool,
    saved: bool,
    message: String,
    pending: bool,
    loaded: bool,
}

impl MotionSettings {
    pub fn new(demo: bool) -> Self {
        let mut travel = Vec::new();
        let mut dynamics = Vec::new();
        let mut homing = Vec::new();
        for (axis, minimum, maximum) in [
            ("X", "-0.100", "410.000"),
            ("Y", "0.000", "310.000"),
            ("Z", "-100.000", "0.000"),
            ("A", "-180.000", "180.000"),
            ("B", "-90.000", "90.000"),
        ] {
            let rotary = matches!(axis, "A" | "B");
            let unit = if rotary { "deg" } else { "mm" };
            travel.push(Field {
                name: axis.into(),
                values: vec![minimum.into(), maximum.into()],
                unit,
                rule: Rule::Range,
                bindings: vec![
                    (format!("AXIS_{axis}"), "MIN_LIMIT".into()),
                    (format!("AXIS_{axis}"), "MAX_LIMIT".into()),
                ],
            });
            dynamics.push(field(
                axis,
                "Maximum velocity",
                "25",
                if rotary { "deg/s" } else { "mm/s" },
                Rule::Positive,
            ));
            dynamics.push(field(
                axis,
                "Maximum acceleration",
                "100",
                if rotary { "deg/s^2" } else { "mm/s^2" },
                Rule::Positive,
            ));
            homing.push(field(axis, "Homing sequence", "0", "", Rule::Integer));
            homing.push(field(
                axis,
                "Search velocity",
                "5",
                if rotary { "deg/s" } else { "mm/s" },
                Rule::Number,
            ));
            homing.push(field(
                axis,
                "Latch velocity",
                "1",
                if rotary { "deg/s" } else { "mm/s" },
                Rule::Number,
            ));
            homing.push(field(axis, "Home offset", "0", unit, Rule::Number));
            homing.push(field(axis, "Home position", "0", unit, Rule::Number));
        }
        Self {
            groups: vec![
                Group { name: "Axis travel", inline: true, fields: travel, help: "Enter edits the gray children here. Up/Down selects an axis; Left/Right selects minimum/maximum. Units follow the INI. Enter saves and returns to the parent; Esc cancels." },
                Group { name: "Working volume", inline: true, fields: vec![
                    field("X", "Width", "400", "mm", Rule::Positive),
                    field("Y", "Depth", "300", "mm", Rule::Positive),
                    field("Z", "Height", "100", "mm", Rule::Positive),
                ], help: "Working-table width, depth and usable height are separate from axis travel. Enter edits the children here. Up/Down selects a dimension; Enter saves and returns to the parent; Esc cancels." },
                Group { name: "Velocity / acceleration", inline: false, fields: dynamics, help: "Enter opens per-axis velocity and acceleration settings. Esc returns to Motion. Linear and rotary units are shown separately." },
                Group { name: "Homing", inline: false, fields: homing, help: "Enter opens per-axis homing sequence, search/latch velocity, offset and home position. Editing never triggers homing. Esc returns to Motion." },
                Group { name: "Jogging", inline: false, fields: vec![
                    field("", "Linear jog speed", "10", "mm/s", Rule::Positive),
                    field("", "Angular jog speed", "10", "deg/s", Rule::Positive),
                    field("", "Linear jog step", "1", "mm", Rule::Positive),
                    field("", "Angular jog step", "1", "deg", Rule::Positive),
                ], help: "Enter opens manual jogging preferences. This preview does not send motion commands. Esc returns to Motion." },
            ],
            group: 0, page: false, field: 0, edit: None, demo, saved: false, message: String::new(),
            pending: false,
            loaded: demo,
        }
    }

    pub fn load(&mut self, text: &str) {
        self.loaded = !text.is_empty();
        let units = ini::get(text, "TRAJ", "LINEAR_UNITS").unwrap_or("unknown");
        let linear = if matches!(units, "inch" | "in") {
            "in"
        } else if units == "mm" {
            "mm"
        } else {
            "native"
        };
        let joints = ini::get(text, "KINS", "JOINTS")
            .and_then(|v| v.parse::<usize>().ok())
            .unwrap_or(0)
            .min(16);
        self.groups[3].fields.clear();
        for joint in 0..joints {
            for (name, rule) in [
                ("Homing sequence", Rule::Integer),
                ("Search velocity", Rule::Number),
                ("Latch velocity", Rule::Number),
                ("Home offset", Rule::Number),
                ("Home position", Rule::Number),
            ] {
                let mut value = field(
                    &joint.to_string(),
                    name,
                    "--",
                    if name == "Homing sequence" {
                        ""
                    } else {
                        "native"
                    },
                    rule,
                );
                value.name = format!("J{joint}|{name}");
                self.groups[3].fields.push(value);
            }
        }
        for group in &mut self.groups {
            for field in &mut group.fields {
                for (value, (section, key)) in field.values.iter_mut().zip(&field.bindings) {
                    *value = ini::get(text, section, key).unwrap_or("--").into();
                }
                let (section, key) = &field.bindings[0];
                if section == "PA_CAM" {
                    continue;
                }
                let angular = if section.starts_with("JOINT_") {
                    ini::get(text, section, "TYPE")
                        .is_some_and(|value| value.eq_ignore_ascii_case("ANGULAR"))
                } else {
                    matches!(section.as_str(), "AXIS_A" | "AXIS_B") || key.contains("ANGULAR")
                };
                let unit = if angular {
                    match ini::get(text, "TRAJ", "ANGULAR_UNITS").unwrap_or("degree") {
                        "degree" | "deg" => "deg",
                        "rad" | "radian" => "rad",
                        _ => "native",
                    }
                } else {
                    linear
                };
                field.unit = if key == "HOME_SEQUENCE" {
                    ""
                } else if key.contains("ACCELERATION") {
                    match unit {
                        "mm" => "mm/s^2",
                        "in" => "in/s^2",
                        "deg" => "deg/s^2",
                        "rad" => "rad/s^2",
                        _ => "native/s^2",
                    }
                } else if key.contains("VEL") {
                    match unit {
                        "mm" => "mm/s",
                        "in" => "in/s",
                        "deg" => "deg/s",
                        "rad" => "rad/s",
                        _ => "native/s",
                    }
                } else {
                    unit
                };
            }
        }
        self.field = self
            .field
            .min(self.groups[self.group].fields.len().saturating_sub(1));
    }

    pub fn changes(&mut self) -> Option<Vec<(String, String, String)>> {
        if !std::mem::take(&mut self.pending) {
            return None;
        }
        let edit = self.edit.as_ref()?;
        let mut changes = Vec::new();
        for (field, values) in self.groups[self.group].fields.iter().zip(&edit.values) {
            for ((old, value), (section, key)) in
                field.values.iter().zip(values).zip(&field.bindings)
            {
                if old != value {
                    changes.push((section.clone(), key.clone(), value.clone()));
                }
            }
        }
        Some(changes)
    }

    pub fn finish_save(&mut self, result: Result<(), String>) {
        match result {
            Ok(()) => {
                let edit = self.edit.take().expect("active editor");
                for (field, values) in self.groups[self.group].fields.iter_mut().zip(edit.values) {
                    field.values = values;
                }
                self.saved = true;
                self.message = if self.demo {
                    "Saved to this session only - no configuration files changed"
                } else {
                    "Configuration saved - restart CNC manually to apply"
                }
                .into();
            }
            Err(error) => self.message = error,
        }
    }

    pub fn title(&self) -> &'static str {
        if self.page {
            self.groups[self.group].name
        } else {
            "Motion parameters"
        }
    }

    pub fn description(&self) -> &'static str {
        if self.page {
            "Up/Down selects a parameter. Enter starts editing; type a number, then Enter saves. Ctrl+U clears. Esc cancels editing or returns to Motion. Production saves the managed INI."
        } else {
            self.groups[self.group].help
        }
    }

    pub fn status(&self) -> &str {
        if !self.message.is_empty() {
            return &self.message;
        }
        if self.edit.is_some() {
            if self.demo {
                "Editing session draft - Enter saves, Esc cancels; no file writes"
            } else {
                "Editing configuration - Enter saves, Esc cancels"
            }
        } else if self.saved {
            if self.demo {
                "Saved to this session only - no configuration files changed"
            } else {
                "Configuration saved - restart CNC manually to apply"
            }
        } else if self.demo {
            "Preview values only - no machine configuration loaded"
        } else {
            "Managed configuration loaded - saves require stopped CNC"
        }
    }

    pub fn footer(&self) -> &'static str {
        if self.edit.is_some() {
            "  Arrows Field  Type Value  Enter Save  Esc Cancel  Ctrl+U Clear"
        } else if self.page {
            "  Up/Down Select    Enter Edit    Esc Back    F1 Help"
        } else {
            "  <- -> Category    Up/Down Select    Enter Open/Edit    Esc Exit"
        }
    }

    pub fn rows(&self, language: Language) -> Vec<Row> {
        let mut result = Vec::new();
        for (index, group) in self.groups.iter().enumerate() {
            if self.page && index != self.group {
                continue;
            }
            if !self.page {
                result.push(Row {
                    label: language.text(group.name).into(),
                    value: if group.inline { "".into() } else { ">".into() },
                    selected: index == self.group && self.edit.is_none(),
                    muted: false,
                });
            }
            if !group.inline && !self.page {
                continue;
            }
            for (field_index, field) in group.fields.iter().enumerate() {
                let editing = self.edit.as_ref().filter(|_| index == self.group);
                let values = editing.map_or(&field.values, |edit| &edit.values[field_index]);
                let value = values
                    .iter()
                    .enumerate()
                    .map(|(column, value)| {
                        let value = value.as_str();
                        if editing.is_some_and(|e| e.field == field_index && e.column == column) {
                            format!("<{value}>")
                        } else {
                            format!("[{value}]")
                        }
                    })
                    .collect::<Vec<_>>()
                    .join(" .. ");
                let (axis, name) = field.name.split_once('|').unwrap_or(("", &field.name));
                let label = format!(
                    "{}{}{}{}",
                    if self.page { "" } else { "  " },
                    axis,
                    if axis.is_empty() { "" } else { " " },
                    language.text(name)
                );
                result.push(Row {
                    label,
                    value: format!("{value} {}", field.unit),
                    selected: editing.map_or(self.page && self.field == field_index, |e| {
                        e.field == field_index
                    }),
                    muted: !self.page && editing.is_none(),
                });
            }
        }
        result
    }

    /// Returns true when navigation is owned by this page/editor instead of the tab bar.
    pub fn handle(&mut self, key: &Key) -> bool {
        if self.edit.is_some() {
            return self.edit_key(key);
        }
        match key {
            Key::Escape if self.page => {
                self.page = false;
                self.message.clear();
            }
            Key::Up => {
                if self.page {
                    self.field = self.field.saturating_sub(1);
                } else {
                    self.group = self.group.saturating_sub(1);
                }
                self.message.clear();
            }
            Key::Down => {
                if self.page {
                    self.field = (self.field + 1) % self.groups[self.group].fields.len().max(1);
                } else {
                    self.group = (self.group + 1) % self.groups.len();
                }
                self.message.clear();
            }
            Key::Activate => {
                if !self.page && !self.groups[self.group].inline {
                    self.page = true;
                    self.field = 0;
                    self.message.clear();
                } else if !self.loaded || self.groups[self.group].fields.is_empty() {
                    self.message = "Editing unavailable - no machine configuration loaded".into();
                } else {
                    self.edit = Some(Edit {
                        values: self.groups[self.group]
                            .fields
                            .iter()
                            .map(|f| f.values.clone())
                            .collect(),
                        field: if self.page { self.field } else { 0 },
                        column: 0,
                        replace: true,
                    });
                    self.message.clear();
                }
            }
            Key::Left | Key::Right | Key::Tab if self.page => {}
            _ => return false,
        }
        true
    }

    fn edit_key(&mut self, key: &Key) -> bool {
        if matches!(key, Key::Escape) {
            self.edit = None;
            self.message = "Edit cancelled - previous session values retained".into();
            return true;
        }
        if matches!(key, Key::Activate) {
            let edit = self.edit.as_ref().expect("active editor");
            for (field_index, (field, values)) in self.groups[self.group]
                .fields
                .iter()
                .zip(&edit.values)
                .enumerate()
            {
                if values != &field.values && !valid(values, field.rule) {
                    let edit = self.edit.as_mut().expect("active editor");
                    edit.field = field_index;
                    edit.column = 0;
                    edit.replace = true;
                    self.message = "Invalid value: finite number required; dimensions/speeds > 0; min < max; sequence integer".into();
                    return true;
                }
            }
            self.pending = true;
            return true;
        }
        let edit = self.edit.as_mut().expect("active editor");
        match key {
            Key::Up | Key::Down if !self.page => {
                edit.field = if matches!(key, Key::Up) {
                    edit.field.saturating_sub(1)
                } else {
                    (edit.field + 1) % edit.values.len()
                };
                edit.column = edit.column.min(edit.values[edit.field].len() - 1);
                edit.replace = true;
            }
            Key::Left | Key::Right | Key::Tab if !self.page => {
                edit.column = (edit.column + 1) % edit.values[edit.field].len();
                edit.replace = true;
            }
            Key::Character(ch) if ch.is_ascii_digit() || matches!(ch, '.' | '-' | '+') => {
                let value = &mut edit.values[edit.field][edit.column];
                if edit.replace {
                    value.clear();
                    edit.replace = false;
                }
                if value.len() < 18 {
                    value.push(*ch);
                }
                self.message.clear();
            }
            Key::Backspace => {
                edit.values[edit.field][edit.column].pop();
                edit.replace = false;
                self.message.clear();
            }
            Key::Clear => {
                edit.values[edit.field][edit.column].clear();
                edit.replace = false;
                self.message.clear();
            }
            Key::Help | Key::Exit => return false,
            _ => {}
        }
        true
    }
}
// END: MotionSettings
//--------//

fn field(axis: &str, name: &str, value: &str, unit: &'static str, rule: Rule) -> Field {
    let (section, key) = match name {
        "Width" => ("PA_CAM".to_owned(), "TABLE_X_MM"),
        "Depth" => ("PA_CAM".to_owned(), "TABLE_Y_MM"),
        "Height" => ("PA_CAM".to_owned(), "TABLE_Z_MM"),
        "Maximum velocity" => (format!("AXIS_{axis}"), "MAX_VELOCITY"),
        "Maximum acceleration" => (format!("AXIS_{axis}"), "MAX_ACCELERATION"),
        "Homing sequence" => (format!("JOINT_{axis}"), "HOME_SEQUENCE"),
        "Search velocity" => (format!("JOINT_{axis}"), "HOME_SEARCH_VEL"),
        "Latch velocity" => (format!("JOINT_{axis}"), "HOME_LATCH_VEL"),
        "Home offset" => (format!("JOINT_{axis}"), "HOME_OFFSET"),
        "Home position" => (format!("JOINT_{axis}"), "HOME"),
        "Linear jog speed" => ("DISPLAY".to_owned(), "DEFAULT_LINEAR_VELOCITY"),
        "Angular jog speed" => ("DISPLAY".to_owned(), "DEFAULT_ANGULAR_VELOCITY"),
        "Linear jog step" => ("PA_MANUAL".to_owned(), "LINEAR_STEP"),
        "Angular jog step" => ("PA_MANUAL".to_owned(), "ANGULAR_STEP"),
        _ => unreachable!("known field binding"),
    };
    Field {
        bindings: vec![(section, key.into())],
        name: format!("{axis}|{name}"),
        values: vec![value.into()],
        unit,
        rule,
    }
}

fn valid(values: &[String], rule: Rule) -> bool {
    let Ok(numbers) = values
        .iter()
        .map(|v| v.parse::<f64>())
        .collect::<Result<Vec<_>, _>>()
    else {
        return false;
    };
    if !numbers.iter().all(|n| n.is_finite()) {
        return false;
    }
    match rule {
        Rule::Range => numbers[0] < numbers[1],
        Rule::Positive => numbers[0] > 0.0,
        Rule::Number => true,
        Rule::Integer => {
            numbers[0].fract() == 0.0
                && (f64::from(i32::MIN)..=f64::from(i32::MAX)).contains(&numbers[0])
        }
    }
}
