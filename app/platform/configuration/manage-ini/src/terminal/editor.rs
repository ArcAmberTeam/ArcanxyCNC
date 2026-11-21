//! Bounded text editor model for the managed document; persistence stays with Session.

use super::input::Key;

pub(super) enum Action {
    None,
    Save(String),
    Close,
}

//--------//
// BEGIN: ConfigurationTextEditor
pub(super) struct Editor {
    lines: Vec<Vec<char>>,
    row: usize,
    column: usize,
    pub dirty: bool,
    pub confirming: bool,
    pub message: String,
    pub label: String,
    original: String,
}
impl Editor {
    pub fn new(text: &str, label: &str, section: Option<&str>) -> Self {
        let lines: Vec<Vec<char>> = text
            .split('\n')
            .map(|line| line.chars().collect())
            .collect();
        let row = section
            .and_then(|section| {
                text.lines()
                    .position(|line| line.trim().eq_ignore_ascii_case(section))
            })
            .unwrap_or(0);
        Self {
            lines,
            row,
            column: 0,
            dirty: false,
            confirming: false,
            message: String::new(),
            label: label.into(),
            original: text.into(),
        }
    }
    fn text(&self) -> String {
        self.lines
            .iter()
            .map(|line| line.iter().collect::<String>())
            .collect::<Vec<_>>()
            .join("\n")
    }
    pub fn saved(&mut self) {
        self.original = self.text();
        self.dirty = false;
        self.confirming = false;
        self.message = "Configuration saved".into();
    }
    pub fn viewport(&self, height: usize, width: usize) -> (Vec<String>, usize, usize, usize) {
        use unicode_width::UnicodeWidthChar;
        let top = self.row.saturating_sub(height.saturating_sub(1));
        let cursor_cells: usize = self.lines[self.row][..self.column]
            .iter()
            .map(|ch| ch.width().unwrap_or(1))
            .sum();
        let left = cursor_cells.saturating_sub(width.saturating_sub(1));
        let lines = self
            .lines
            .iter()
            .skip(top)
            .take(height)
            .map(|line| {
                let mut cells = 0;
                line.iter()
                    .filter_map(|ch| {
                        let start = cells;
                        cells += ch.width().unwrap_or(1);
                        if start < left {
                            None
                        } else if ch.is_control() {
                            Some(' ')
                        } else {
                            Some(*ch)
                        }
                    })
                    .collect()
            })
            .collect();
        (lines, self.row - top, cursor_cells - left, top)
    }
    pub fn handle(&mut self, key: &Key) -> Action {
        if self.confirming {
            return match key {
                Key::Close => Action::Close,
                Key::Save => Action::Save(self.text()),
                Key::Escape => {
                    self.confirming = false;
                    self.message.clear();
                    Action::None
                }
                _ => Action::None,
            };
        }
        match key {
            Key::Escape | Key::Close => {
                if !self.dirty {
                    return Action::Close;
                }
                self.confirming = true;
                self.message = "Unsaved edits: Ctrl+S saves, Ctrl+X discards, Esc continues".into();
            }
            Key::Save => return Action::Save(self.text()),
            Key::Up => self.row = self.row.saturating_sub(1),
            Key::Down => self.row = (self.row + 1).min(self.lines.len() - 1),
            Key::Left => {
                if self.column > 0 {
                    self.column -= 1;
                } else if self.row > 0 {
                    self.row -= 1;
                    self.column = self.lines[self.row].len();
                }
            }
            Key::Right => {
                if self.column < self.lines[self.row].len() {
                    self.column += 1;
                } else if self.row + 1 < self.lines.len() {
                    self.row += 1;
                    self.column = 0;
                }
            }
            Key::Home => self.column = 0,
            Key::End => self.column = self.lines[self.row].len(),
            Key::Character(ch) => {
                if self.text().len() + ch.len_utf8() <= 256 * 1024 {
                    self.lines[self.row].insert(self.column, *ch);
                    self.column += 1;
                }
            }
            Key::Tab if self.text().len() + 4 <= 256 * 1024 => {
                for _ in 0..4 {
                    self.lines[self.row].insert(self.column, ' ');
                    self.column += 1;
                }
            }
            Key::Activate => {
                if self.text().len() < 256 * 1024 {
                    let tail = self.lines[self.row].split_off(self.column);
                    self.row += 1;
                    self.column = 0;
                    self.lines.insert(self.row, tail);
                }
            }
            Key::Backspace => {
                if self.column > 0 {
                    self.column -= 1;
                    self.lines[self.row].remove(self.column);
                } else if self.row > 0 {
                    let tail = self.lines.remove(self.row);
                    self.row -= 1;
                    self.column = self.lines[self.row].len();
                    self.lines[self.row].extend(tail);
                }
            }
            Key::Delete => {
                if self.column < self.lines[self.row].len() {
                    self.lines[self.row].remove(self.column);
                } else if self.row + 1 < self.lines.len() {
                    let next = self.lines.remove(self.row + 1);
                    self.lines[self.row].extend(next);
                }
            }
            Key::Clear => {
                self.lines[self.row].drain(..self.column);
                self.column = 0;
            }
            _ => {}
        }
        self.column = self.column.min(self.lines[self.row].len());
        self.dirty = self.text() != self.original;
        Action::None
    }
}

// END: ConfigurationTextEditor
//--------//
