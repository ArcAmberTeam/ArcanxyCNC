//! CAM metadata preferences in the same managed INI document.

use super::{input::Key, language::Language, motion::Row};
use crate::ini;

//--------//
// BEGIN: CamMetadataSettings
pub(super) struct CamSettings {
    selected: usize,
    choice: Option<usize>,
    editing: Option<String>,
    replace: bool,
    source: String,
    origins: [String; 3],
    pending: Option<Vec<(String, String, String)>>,
    pub message: String,
}
impl CamSettings {
    pub fn new(text: &str) -> Self {
        Self {
            selected: 0,
            choice: None,
            editing: None,
            replace: true,
            source: ini::get(text, "PA_CAM", "DIMENSION_SOURCE")
                .unwrap_or("axis_travel")
                .into(),
            origins: ["X", "Y", "Z"].map(|axis| {
                ini::get(text, "PA_CAM", &format!("ORIGIN_{axis}_MM"))
                    .unwrap_or("--")
                    .into()
            }),
            pending: None,
            message: String::new(),
        }
    }
    pub fn rows(&self, lang: Language) -> Vec<Row> {
        let mut rows = vec![Row {
            label: lang.text("Size source").into(),
            value: lang
                .text(if self.source == "axis_travel" {
                    "Axis travel"
                } else if self.source == "working_volume" {
                    "Working volume"
                } else {
                    "Invalid source"
                })
                .into(),
            selected: self.selected == 0 && self.choice.is_none(),
            muted: false,
        }];
        if let Some(choice) = self.choice {
            for (index, name) in ["Axis travel", "Working volume"].iter().enumerate() {
                rows.push(Row {
                    label: format!("  {}", lang.text(name)),
                    value: String::new(),
                    selected: index == choice,
                    muted: index != choice,
                });
            }
        }
        for (index, axis) in ["X", "Y", "Z"].iter().enumerate() {
            let value = if self.selected == index + 1 {
                self.editing.as_ref().unwrap_or(&self.origins[index])
            } else {
                &self.origins[index]
            };
            rows.push(Row {
                label: format!("{axis} {}", lang.text("Table origin")),
                value: format!("[{value}] mm"),
                selected: self.selected == index + 1,
                muted: false,
            });
        }
        rows
    }
    pub fn description(&self) -> &'static str {
        "Choose axis soft-limit ranges or configured working-table dimensions. Table origin is the lower XYZ corner in machine coordinates, in mm. Missing origin disables absolute-placement metadata. This does not set G54 or measure the workpiece."
    }
    pub fn handle(&mut self, key: &Key) -> bool {
        if let Some(choice) = &mut self.choice {
            match key {
                Key::Up | Key::Down | Key::Left | Key::Right => *choice = 1 - *choice,
                Key::Escape => self.choice = None,
                Key::Activate => {
                    self.pending = Some(vec![(
                        "PA_CAM".into(),
                        "DIMENSION_SOURCE".into(),
                        if *choice == 0 {
                            "axis_travel"
                        } else {
                            "working_volume"
                        }
                        .into(),
                    )])
                }
                Key::Exit => return false,
                _ => {}
            }
            return true;
        }
        if let Some(value) = &mut self.editing {
            match key {
                Key::Escape => self.editing = None,
                Key::Activate => {
                    if value.parse::<f64>().is_ok_and(|number| number.is_finite()) {
                        self.pending = Some(vec![(
                            "PA_CAM".into(),
                            format!("ORIGIN_{}_MM", ["X", "Y", "Z"][self.selected - 1]),
                            value.clone(),
                        )]);
                    } else {
                        self.message = "Enter a finite number".into();
                    }
                }
                Key::Character(ch) if ch.is_ascii_digit() || matches!(ch, '.' | '-' | '+') => {
                    if self.replace {
                        value.clear();
                        self.replace = false;
                    }
                    if value.len() < 18 {
                        value.push(*ch);
                    }
                }
                Key::Backspace => {
                    value.pop();
                    self.replace = false;
                }
                Key::Clear => {
                    value.clear();
                    self.replace = false;
                }
                Key::Exit => return false,
                _ => {}
            }
            return true;
        }
        match key {
            Key::Up => self.selected = self.selected.saturating_sub(1),
            Key::Down => self.selected = (self.selected + 1) % 4,
            Key::Activate if self.selected == 0 => {
                self.choice = Some(usize::from(self.source == "working_volume"))
            }
            Key::Activate => {
                self.editing = Some(self.origins[self.selected - 1].clone());
                self.replace = true;
            }
            _ => return false,
        }
        self.message.clear();
        true
    }
    pub fn changes(&mut self) -> Option<Vec<(String, String, String)>> {
        self.pending.take()
    }
    pub fn finish_save(&mut self, text: &str, result: Result<(), String>, demo: bool) {
        match result {
            Ok(()) => {
                let selected = self.selected;
                *self = Self::new(text);
                self.selected = selected;
                self.message = if demo {
                    "Saved to this session only - no configuration files changed"
                } else {
                    "Configuration saved - restart CNC manually to apply"
                }
                .into();
            }
            Err(error) => self.message = error,
        }
    }
}

// END: CamMetadataSettings
//--------//
