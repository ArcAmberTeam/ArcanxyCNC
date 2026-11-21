//! Interactive management session with a bounded help-only non-TTY fallback.

use crate::targets::Target;
use std::io::{self, BufRead, Read, Write};

mod cam;
mod document;
mod editor;
mod input;
mod language;
mod motion;
mod screen;

pub(crate) fn preview() -> io::Result<()> {
    screen::open("ini", true)
}

pub(crate) fn open(
    target: Target,
    input: &mut impl BufRead,
    output: &mut impl Write,
) -> io::Result<()> {
    use std::io::IsTerminal;
    if std::io::stdin().is_terminal() && std::io::stdout().is_terminal() {
        return screen::open(target.name, false);
    }
    writeln!(output, "PA / {}", target.title)?;
    writeln!(
        output,
        "Full-screen editing requires an interactive terminal. Connect with ssh -t."
    )?;
    writeln!(output, "Commands: help, exit")?;
    loop {
        write!(output, "pa manage {}> ", target.name)?;
        output.flush()?;
        let mut line = Vec::new();
        let length = (&mut *input).take(4097).read_until(b'\n', &mut line)?;
        if length == 0 {
            writeln!(output)?;
            return Ok(());
        }
        if length > 4096 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "Input exceeds 4096 bytes",
            ));
        }
        match line.as_slice() {
            b"exit\n" | b"exit\r\n" | b"exit" => return Ok(()),
            b"help\n" | b"help\r\n" | b"help" => {
                writeln!(
                    output,
                    "Commands: help, exit. Open an interactive terminal to edit configuration."
                )?;
            }
            b"\n" | b"\r\n" => {}
            _ => writeln!(output, "Unknown command. Use help or exit.")?,
        }
    }
}
