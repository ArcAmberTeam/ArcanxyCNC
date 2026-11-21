//! Blue/gray management-terminal presentation. This layer never opens configuration files.

use super::input::{self, Key};
use super::language::Language;
use super::motion::MotionSettings;
use super::{
    cam::CamSettings,
    document::Session,
    editor::{Action, Editor},
};
use unicode_width::{UnicodeWidthChar, UnicodeWidthStr};

const TABS: [&str; 7] = [
    "General",
    "Motion",
    "Advanced",
    "CAM",
    "Files",
    "Review",
    "Language / 語言",
];
const LANGUAGE_TAB: usize = TABS.len() - 1;
use std::io::{self, IsTerminal, Write};

const BLUE: &str = "\x1b[37;44m";
const MUTED: &str = "\x1b[90;47m";
const GRAY: &str = "\x1b[30;47m";
const SELECTED: &str = "\x1b[97;44m";
const WHITE: &str = "\x1b[97;100m";

struct Screen {
    original: libc::termios,
}

impl Screen {
    fn enter() -> io::Result<Self> {
        if !io::stdin().is_terminal() || !io::stdout().is_terminal() {
            return Err(io::Error::other(
                "Open the preview in an interactive terminal",
            ));
        }
        let mut original = std::mem::MaybeUninit::uninit();
        // SAFETY: fd 0 is a terminal and original is writable termios storage.
        if unsafe { libc::tcgetattr(0, original.as_mut_ptr()) } != 0 {
            return Err(io::Error::last_os_error());
        }
        // SAFETY: tcgetattr successfully initialized original.
        let original = unsafe { original.assume_init() };
        let mut raw = original;
        // SAFETY: raw is an initialized termios value and fd 0 is a terminal.
        unsafe { libc::cfmakeraw(&mut raw) };
        if unsafe { libc::tcsetattr(0, libc::TCSANOW, &raw) } != 0 {
            return Err(io::Error::last_os_error());
        }
        let guard = Self { original };
        print!("\x1b[?1049h\x1b[?25l");
        io::stdout().flush()?;
        Ok(guard)
    }
}

impl Drop for Screen {
    fn drop(&mut self) {
        // SAFETY: original came from tcgetattr on this process's stdin.
        unsafe { libc::tcsetattr(0, libc::TCSANOW, &self.original) };
        let _ = write!(io::stdout(), "\x1b[0m\x1b[?25h\x1b[?1049l");
        let _ = io::stdout().flush();
    }
}

fn dimensions() -> (usize, usize) {
    let mut size: libc::winsize = unsafe { std::mem::zeroed() };
    // SAFETY: size is a writable winsize and fd 1 is the output terminal.
    if unsafe { libc::ioctl(1, libc::TIOCGWINSZ, &mut size) } == 0 {
        (
            usize::from(size.ws_col).min(240),
            usize::from(size.ws_row).min(80),
        )
    } else {
        (80, 24)
    }
}

fn line(output: &mut String, row: usize, column: usize, width: usize, color: &str, text: &str) {
    use std::fmt::Write;
    let mut used = 0;
    let clipped: String = text
        .chars()
        .take_while(|ch| {
            let cells = ch.width().unwrap_or(0);
            if used + cells > width {
                return false;
            }
            used += cells;
            true
        })
        .collect();
    let padding = width.saturating_sub(used);
    let _ = write!(
        output,
        "\x1b[{row};{column}H{color}{clipped}{}",
        " ".repeat(padding)
    );
}

fn rows(
    tab: usize,
    launcher: bool,
    demo: bool,
    language: Language,
) -> Vec<(&'static str, &'static str, &'static str)> {
    if tab == LANGUAGE_TAB {
        return [Language::English, Language::TraditionalChinese]
            .into_iter()
            .map(|choice| {
                (
                    if choice == Language::English {
                        "English"
                    } else {
                        "繁體中文"
                    },
                    if choice == language {
                        "Current"
                    } else {
                        "Select"
                    },
                    "Press Enter to use this language. Applies to this session only.",
                )
            })
            .collect();
    }
    if launcher {
        return vec![
            (
                "Configuration",
                "launcher.json",
                "Launcher settings are managed independently from machine INI.",
            ),
            (
                "CAM service",
                "--",
                "Enable or disable CAM integration after configuration editing is implemented.",
            ),
            (
                "Listen port",
                "--",
                "The configured CAM service port. This screen has not read a device.",
            ),
        ];
    }
    match tab {
        2 => vec![
            ("Axis / joint mapping", ">", "Enter opens the managed INI at KINS for axis/joint mapping and kinematics. No model is inferred from axis count."),
            ("Motor / encoder", ">", "Enter opens the managed INI at JOINT_0 for motor scale, pulse timing and encoder parameters. HAL wiring is not rewritten."),
            ("Limit / home signals", ">", "Enter opens the managed INI at HAL. Signal mappings implemented in HAL remain in their own files; this editor only changes INI."),
            ("Expert INI", ">", "Enter loads the current INI in the text editor. Ctrl+S saves after backup while CNC is stopped. Esc returns; unsaved edits require a choice."),
        ],
        4 => vec![
            ("Management target", "ini", "INI is a registered logical target, not an arbitrary caller-supplied path."),
            ("Configuration source", "Not loaded", "The installed launcher selects the managed INI. External edits are detected before saving."),
            ("Write access", "Unavailable", "Production saves require maintenance authorization, stopped CNC, a fresh file revision and successful backup."),
        ],
        5 => vec![
            ("Saved changes", "None", "Structured edits and the text editor share one document. Production changes take effect after a manual CNC restart."),
            ("Save configuration", "Enter / Ctrl+S", "Enter saves structured edits. Ctrl+S saves the text editor. Preview saves remain in this session."),
            ("Restart machine", "Unavailable", "This terminal does not start or restart machine services."),
        ],
        _ => vec![
            ("Management target", "ini", "Use pa manage ini or pa manage launcher.json to select a management target."),
            ("Session", if demo { "UI PREVIEW" } else { "cnc-maint" }, "Production PA validates the real and effective OS user IDs."),
            ("Machine connection", "Not connected", "This interface does not open the LinuxCNC controller connection."),
            ("Editor", if demo { "Preview only" } else { "INI / JSON" }, "Use Motion for structured settings or Advanced for the INI text editor. Launcher JSON opens from its Configuration item."),
        ],
    }
}

//--------//
// BEGIN: ManagementTerminal
struct State {
    target: String,
    demo: bool,
    tab: usize,
    selected: usize,
    help: bool,
    language: Language,
    motion: MotionSettings,
    cam: CamSettings,
    session: Session,
    editor: Option<Editor>,
}

fn render(state: &State) -> io::Result<()> {
    let (target, demo, tab, selected, help, language, motion) = (
        state.target.as_str(),
        state.demo,
        state.tab,
        state.selected,
        state.help,
        state.language,
        &state.motion,
    );
    let (width, height) = dimensions();
    let mut out = String::from("\x1b[?25l\x1b[2J");
    for row in 1..=height {
        line(&mut out, row, 1, width, GRAY, "");
    }
    if width < 80 || height < 24 {
        line(
            &mut out,
            1,
            1,
            width,
            BLUE,
            language.text("PA - Resize terminal to at least 80 x 24. Esc exits."),
        );
    } else if let Some(editor) = &state.editor {
        line(
            &mut out,
            1,
            1,
            width,
            BLUE,
            &format!(" {}{}", if editor.dirty { "* " } else { "" }, editor.label),
        );
        let (lines, cursor_row, cursor_column, top) = editor.viewport(height - 5, width - 8);
        for (index, text) in lines.iter().enumerate() {
            line(
                &mut out,
                3 + index,
                1,
                7,
                MUTED,
                &format!("{:>5} ", top + index + 1),
            );
            line(&mut out, 3 + index, 8, width - 8, GRAY, text);
        }
        line(
            &mut out,
            height - 2,
            1,
            width,
            WHITE,
            language.text(if editor.message.is_empty() {
                if demo {
                    "Preview INI - saves apply to this session only"
                } else {
                    "INI editor - save requires stopped CNC; changes apply after restart"
                }
            } else {
                &editor.message
            }),
        );
        line(
            &mut out,
            height - 1,
            1,
            width,
            BLUE,
            language.text("  Ctrl+S Save    Esc Back    Ctrl+X Exit    Arrows Move"),
        );
        line(
            &mut out,
            height,
            1,
            width,
            BLUE,
            language.text("  PA Platform Management"),
        );
        use std::fmt::Write;
        let _ = write!(
            out,
            "\x1b[{};{}H\x1b[?25h",
            3 + cursor_row,
            8 + cursor_column
        );
    } else {
        let split = width * 2 / 3;
        line(
            &mut out,
            1,
            1,
            width,
            BLUE,
            language.text("  PA Configuration Utility"),
        );
        line(
            &mut out,
            2,
            1,
            width,
            BLUE,
            if demo {
                language.text("  UI PREVIEW / Demo data / No machine access")
            } else {
                language.text("  cnc-maint / Managed configuration")
            },
        );
        let mut column = 3;
        let mut tab_row = 4;
        for (index, label) in TABS.iter().enumerate() {
            let label = language.text(label);
            if column + label.width() + 3 > width {
                column = 3;
                tab_row += 1;
            }
            line(
                &mut out,
                tab_row,
                column,
                label.width() + 4,
                if index == tab { BLUE } else { GRAY },
                &format!("  {label}  "),
            );
            column += label.width() + 5;
        }
        let is_motion = tab == 1 && target == "ini";
        let heading = if is_motion {
            format!(
                "{} / {}",
                language.text("Motion"),
                language.text(motion.title())
            )
        } else {
            "─".repeat(split - 5)
        };
        line(&mut out, 6, 3, split - 5, GRAY, &heading);
        line(
            &mut out,
            6,
            split + 2,
            width - split - 4,
            GRAY,
            language.text("Item Help"),
        );
        for row in 6..height - 3 {
            line(&mut out, row, split, 1, GRAY, "│");
        }
        let items = rows(tab, target == "launcher.json", demo, language);
        let is_cam = tab == 3 && target == "ini";
        if is_motion || is_cam {
            let motion_rows = if is_motion {
                motion.rows(language)
            } else {
                state.cam.rows(language)
            };
            let active = motion_rows.iter().position(|row| row.selected).unwrap_or(0);
            let available = height - 11;
            let start = active.saturating_sub(available - 1);
            for (index, row) in motion_rows.iter().skip(start).take(available).enumerate() {
                let padding = 19_usize.saturating_sub(row.label.width());
                let text = format!(" {}{} {}", row.label, " ".repeat(padding), row.value);
                line(
                    &mut out,
                    8 + index,
                    3,
                    split - 5,
                    if row.selected {
                        SELECTED
                    } else if row.muted {
                        MUTED
                    } else {
                        GRAY
                    },
                    &text,
                );
            }
        } else {
            for (index, (name, value, _)) in items.iter().enumerate() {
                let value = if *name == "Configuration source" {
                    state
                        .session
                        .document
                        .as_ref()
                        .map_or("Not loaded", |document| document.label.as_str())
                } else if *name == "Write access" && state.session.document.is_some() {
                    if demo {
                        "Session only"
                    } else {
                        "Stop CNC to save"
                    }
                } else if tab == 5 && index == 0 && state.session.saved {
                    if demo {
                        "Session draft"
                    } else {
                        "Saved to disk"
                    }
                } else {
                    value
                };
                let name = language.text(name);
                let value = language.text(value);
                let text = format!(
                    " {name}{} [{value}]",
                    " ".repeat(25_usize.saturating_sub(name.width()))
                );
                line(
                    &mut out,
                    8 + index * 2,
                    3,
                    split - 5,
                    if selected == index { SELECTED } else { GRAY },
                    &text,
                );
            }
        }
        let description = if help {
            "Left/Right or Tab: change category. Up/Down: select an item. Enter: apply language or show item help. F1: show help. Esc or Q: exit. This preview cannot save configuration."
        } else if is_motion {
            motion.description()
        } else if is_cam {
            state.cam.description()
        } else {
            items[selected % items.len()].2
        };
        let description = language.text(description);
        let mut row = 8;
        let mut text = String::new();
        let help_width = width - split - 4;
        for ch in description.chars() {
            if text.width() + ch.width().unwrap_or(0) > help_width {
                line(&mut out, row, split + 2, help_width, GRAY, &text);
                text.clear();
                row += 1;
                if row >= height - 3 {
                    break;
                }
            }
            text.push(ch);
        }
        if row < height - 3 {
            line(&mut out, row, split + 2, help_width, GRAY, &text);
        }
        let status = if !state.session.error.is_empty() {
            state.session.error.as_str()
        } else if is_motion {
            motion.status()
        } else if is_cam && !state.cam.message.is_empty() {
            &state.cam.message
        } else if demo {
            "  Status: interface preview only - no configuration files opened"
        } else {
            "Managed configuration loaded - saves require stopped CNC"
        };
        line(&mut out, height - 2, 1, width, WHITE, language.text(status));
        line(
            &mut out,
            height - 1,
            1,
            width,
            BLUE,
            language.text(if is_motion {
                motion.footer()
            } else {
                "  <- -> Category    Up/Down Select    Enter Apply  F1 Help    Esc Exit"
            }),
        );
        line(
            &mut out,
            height,
            1,
            width,
            BLUE,
            language.text("  PA Platform Management"),
        );
    }
    write!(io::stdout(), "{out}")?;
    io::stdout().flush()
}

pub(super) fn open(target: &str, demo: bool) -> io::Result<()> {
    let session = Session::new(target, demo);
    let mut motion = MotionSettings::new(demo);
    motion.load(session.text());
    let cam = CamSettings::new(session.text());
    let mut state = State {
        target: target.into(),
        demo,
        tab: 0,
        selected: 0,
        help: false,
        language: Language::English,
        motion,
        cam,
        session,
        editor: None,
    };
    let _screen = Screen::enter()?;
    loop {
        render(&state)?;
        let key = input::read()?;
        if let Some(editor) = &mut state.editor {
            match editor.handle(&key) {
                Action::Save(content) => match state.session.save(content) {
                    Ok(()) => {
                        editor.saved();
                        editor.message = if demo {
                            "Saved to this session only - no configuration files changed"
                        } else {
                            "Configuration saved - restart CNC manually to apply"
                        }
                        .into();
                        state.motion.load(state.session.text());
                        state.cam = CamSettings::new(state.session.text());
                    }
                    Err(error) => editor.message = error.to_string(),
                },
                Action::Close => state.editor = None,
                Action::None => {}
            }
            continue;
        }
        if state.tab == 1 && target == "ini" && state.motion.handle(&key) {
            if let Some(changes) = state.motion.changes() {
                let result = if changes.is_empty() {
                    Ok(())
                } else {
                    state
                        .session
                        .patch(&changes)
                        .map_err(|error| error.to_string())
                };
                state.motion.finish_save(result);
            }
            state.help = false;
            continue;
        }
        if state.tab == 3 && target == "ini" && state.cam.handle(&key) {
            if let Some(changes) = state.cam.changes() {
                let result = state
                    .session
                    .patch(&changes)
                    .map_err(|error| error.to_string());
                state.cam.finish_save(state.session.text(), result, demo);
            }
            state.help = false;
            continue;
        }
        match key {
            Key::Exit | Key::Escape | Key::Close | Key::Character('q' | 'Q') => return Ok(()),
            Key::Tab | Key::Right => {
                state.tab = (state.tab + 1) % TABS.len();
                state.selected = 0;
                state.help = false;
            }
            Key::Left => {
                state.tab = (state.tab + TABS.len() - 1) % TABS.len();
                state.selected = 0;
                state.help = false;
            }
            Key::Up => state.selected = state.selected.saturating_sub(1),
            Key::Down => {
                state.selected = (state.selected + 1)
                    % rows(state.tab, target == "launcher.json", demo, state.language).len()
            }
            Key::Activate if state.tab == LANGUAGE_TAB => {
                state.language = if state.selected == 0 {
                    Language::English
                } else {
                    Language::TraditionalChinese
                };
                state.help = false;
            }
            Key::Activate
                if state.tab == 2 || (target == "launcher.json" && state.selected == 0) =>
            {
                state.session.reload();
                state.motion.load(state.session.text());
                state.cam = CamSettings::new(state.session.text());
                if let Some(document) = &state.session.document {
                    let section = if target == "ini" {
                        [Some("[KINS]"), Some("[JOINT_0]"), Some("[HAL]"), None]
                            [state.selected.min(3)]
                    } else {
                        None
                    };
                    state.editor = Some(Editor::new(&document.content, &document.label, section));
                }
            }
            Key::Help | Key::Character('?') | Key::Activate => state.help = !state.help,
            _ => {}
        }
    }
}

// END: ManagementTerminal
//--------//
