//! Read terminal bytes through one unbuffered descriptor, including escape sequences.

use std::io;

pub(super) enum Key {
    Up,
    Down,
    Left,
    Right,
    Tab,
    Help,
    Activate,
    Escape,
    Character(char),
    Backspace,
    Clear,
    Save,
    Close,
    Home,
    End,
    Delete,
    Exit,
    Ignore,
}

fn byte(timeout: i32) -> io::Result<Option<u8>> {
    loop {
        let mut descriptor = libc::pollfd {
            fd: 0,
            events: libc::POLLIN,
            revents: 0,
        };
        // SAFETY: descriptor points to one initialized pollfd for stdin.
        let ready = unsafe { libc::poll(&mut descriptor, 1, timeout) };
        if ready == 0 {
            return Ok(None);
        }
        if ready < 0 {
            let error = io::Error::last_os_error();
            if error.kind() == io::ErrorKind::Interrupted {
                continue;
            }
            return Err(error);
        }
        if descriptor.revents & libc::POLLIN == 0 {
            return Err(io::Error::new(
                io::ErrorKind::UnexpectedEof,
                "Terminal input disconnected",
            ));
        }
        let mut value = 0_u8;
        // SAFETY: value is writable for one byte. Do not mix this descriptor
        // with std::io::Stdin, whose buffered bytes are invisible to poll.
        let read = unsafe { libc::read(0, (&mut value as *mut u8).cast(), 1) };
        if read == 1 {
            return Ok(Some(value));
        }
        if read == 0 {
            return Err(io::Error::new(
                io::ErrorKind::UnexpectedEof,
                "Terminal input closed",
            ));
        }
        let error = io::Error::last_os_error();
        if error.kind() != io::ErrorKind::Interrupted {
            return Err(error);
        }
    }
}

fn escape() -> io::Result<Key> {
    // Only a standalone Escape exits. A partial or unknown sequence is ignored.
    match byte(150)? {
        None => return Ok(Key::Escape),
        Some(b'[' | b'O') => {}
        Some(_) => return Ok(Key::Ignore),
    }
    let mut parameters = Vec::new();
    for _ in 0..24 {
        let Some(value) = byte(150)? else {
            return Ok(Key::Ignore);
        };
        if (0x40..=0x7e).contains(&value) {
            return Ok(match value {
                b'A' => Key::Up,
                b'B' => Key::Down,
                b'C' => Key::Right,
                b'D' => Key::Left,
                b'P' => Key::Help,
                b'H' => Key::Home,
                b'F' => Key::End,
                b'~' if parameters == b"3" => Key::Delete,
                b'~' if parameters == b"1" || parameters == b"7" => Key::Home,
                b'~' if parameters == b"4" || parameters == b"8" => Key::End,
                b'~' if parameters == b"11" => Key::Help,
                _ => Key::Ignore,
            });
        }
        if !(0x20..=0x3f).contains(&value) {
            return Ok(Key::Ignore);
        }
        parameters.push(value);
    }
    Ok(Key::Ignore)
}

pub(super) fn read() -> io::Result<Key> {
    Ok(match byte(250)? {
        Some(27) => return escape(),
        Some(3 | 4) => Key::Exit,
        Some(19) => Key::Save,
        Some(24) => Key::Close,
        Some(b'\t') => Key::Tab,
        Some(b'\r' | b'\n') => Key::Activate,
        Some(8 | 127) => Key::Backspace,
        Some(21) => Key::Clear,
        Some(value @ 32..=126) => Key::Character(char::from(value)),
        Some(first @ 0xc2..=0xf4) => {
            let count = if first < 0xe0 {
                2
            } else if first < 0xf0 {
                3
            } else {
                4
            };
            let mut bytes = vec![first];
            for _ in 1..count {
                if let Some(next @ 0x80..=0xbf) = byte(150)? {
                    bytes.push(next);
                } else {
                    return Ok(Key::Ignore);
                }
            }
            std::str::from_utf8(&bytes)
                .ok()
                .and_then(|s| s.chars().next())
                .map_or(Key::Ignore, Key::Character)
        }
        _ => Key::Ignore,
    })
}
