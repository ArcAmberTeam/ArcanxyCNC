//! Lossless edits of explicit INI entries. Repeated unrelated keys and comments survive.

use std::io;

pub(crate) fn get<'a>(text: &'a str, section: &str, key: &str) -> Option<&'a str> {
    let mut current = "";
    for line in text.lines() {
        let trimmed = line.trim();
        if let Some(name) = trimmed.strip_prefix('[').and_then(|s| s.split_once(']')) {
            current = name.0.trim();
        } else if current.eq_ignore_ascii_case(section) && !trimmed.starts_with(['#', ';']) {
            if let Some((name, value)) = trimmed.split_once('=') {
                if name.trim().eq_ignore_ascii_case(key) {
                    return Some(value.split(['#', ';']).next().unwrap_or("").trim());
                }
            }
        }
    }
    None
}

pub(crate) fn set(text: &str, section: &str, key: &str, value: &str) -> io::Result<String> {
    let newline = if text.contains("\r\n") { "\r\n" } else { "\n" };
    let mut current = "";
    let mut position = 0;
    let mut insertion = None;
    let mut replacement = None;
    for line in text.split_inclusive('\n') {
        let trimmed = line.trim();
        if let Some(name) = trimmed.strip_prefix('[').and_then(|s| s.split_once(']')) {
            if current.eq_ignore_ascii_case(section) && insertion.is_none() {
                insertion = Some(position);
            }
            current = name.0.trim();
        } else if current.eq_ignore_ascii_case(section) && !trimmed.starts_with(['#', ';']) {
            if let Some((name, old)) = trimmed.split_once('=') {
                if name.trim().eq_ignore_ascii_case(key) {
                    if replacement.is_some() {
                        return Err(io::Error::other(
                            "Duplicate setting: use Expert INI to resolve it",
                        ));
                    }
                    let comment = old
                        .find(['#', ';'])
                        .map(|index| format!(" {}", &old[index..]))
                        .unwrap_or_default();
                    replacement = Some((
                        position,
                        position + line.len(),
                        format!("{key} = {value}{comment}{newline}"),
                    ));
                }
            }
        }
        position += line.len();
    }
    if let Some((start, end, value)) = replacement {
        return Ok(format!("{}{}{}", &text[..start], value, &text[end..]));
    }
    if current.eq_ignore_ascii_case(section) {
        insertion = insertion.or(Some(text.len()));
    }
    let entry = format!("{key} = {value}{newline}");
    let separator = if text.ends_with('\n') || text.is_empty() {
        ""
    } else {
        newline
    };
    Ok(if let Some(index) = insertion {
        format!(
            "{}{}{}{}",
            &text[..index],
            if index == text.len() { separator } else { "" },
            entry,
            &text[index..]
        )
    } else {
        format!("{text}{separator}{newline}[{section}]{newline}{entry}")
    })
}

pub(crate) fn validate(text: &str) -> io::Result<()> {
    if text.len() > 256 * 1024
        || text
            .chars()
            .any(|c| c.is_control() && !matches!(c, '\n' | '\r' | '\t'))
    {
        return Err(io::Error::other(
            "INI exceeds 256 KiB or contains control characters",
        ));
    }
    let mut section = false;
    let mut continuation = false;
    for line in text.lines() {
        let line = line.trim();
        if continuation {
            continuation = line.ends_with('\\');
            continue;
        }
        if line.is_empty() || line.starts_with(['#', ';']) {
            continue;
        }
        if let Some(header) = line.strip_prefix('[') {
            let Some((name, suffix)) = header.split_once(']') else {
                return Err(io::Error::other("Invalid INI section"));
            };
            if name.trim().is_empty()
                || !(suffix.trim().is_empty() || suffix.trim().starts_with(['#', ';']))
            {
                return Err(io::Error::other("Invalid INI section"));
            }
            section = true;
        } else if !section
            || !line
                .split_once('=')
                .is_some_and(|(key, _)| !key.trim().is_empty())
        {
            return Err(io::Error::other(
                "Expected an INI key = value inside a section",
            ));
        }
        continuation = line.ends_with('\\');
    }
    if !section || continuation {
        return Err(io::Error::other("Incomplete INI document"));
    }
    Ok(())
}
