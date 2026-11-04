use crate::{categories, Result};
use chrono::{SecondsFormat, Utc};
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::sync::OnceLock;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Submission {
    schema_version: u32,
    source: String,
    code: String,
    message: String,
    context: Map<String, Value>,
}

#[derive(Serialize, Deserialize)]
pub(crate) struct Event {
    pub schema_version: u32,
    pub event_id: String,
    pub timestamp: String,
    pub received_ms: i64,
    pub category: String,
    pub source: String,
    pub code: String,
    pub message: String,
    pub context: Map<String, Value>,
    pub uid: u32,
    pub pid: i32,
}

pub(crate) fn redact(text: &str) -> String {
    static SECRET: OnceLock<Regex> = OnceLock::new();
    let pattern = SECRET.get_or_init(|| Regex::new(
        r#"(?i)(password|passwd|token|authorization|secret|api[_-]?key)([\s\"']*[:=][\s\"']*)[^\s,;\"'}]+"#
    ).expect("constant credential pattern"));
    let bounded: String = text
        .chars()
        .filter(|c| !c.is_control() || *c == '\n' || *c == '\t')
        .take(4096)
        .collect();
    static BEARER: OnceLock<Regex> = OnceLock::new();
    let bounded = BEARER
        .get_or_init(|| Regex::new(r#"(?i)bearer\s+[^\s,;"']+"#).expect("constant bearer pattern"))
        .replace_all(&bounded, "Bearer [REDACTED]");
    let text = pattern.replace_all(&bounded, "$1$2[REDACTED]");
    static URL: OnceLock<Regex> = OnceLock::new();
    URL.get_or_init(|| {
        Regex::new(r"(?i)https?://[^\s/@]+:[^\s/@]+@").expect("constant URL pattern")
    })
    .replace_all(&text, "https://[REDACTED]@")
    .into_owned()
}

impl Event {
    pub fn receive(bytes: &[u8], uid: u32, pid: i32) -> Result<Self> {
        if bytes.len() > 16384 {
            return Err("Event exceeds limit".into());
        }
        let input: Submission = serde_json::from_slice(bytes)?;
        let identifier = |s: &str, n: usize| {
            !s.is_empty()
                && s.len() <= n
                && s.bytes()
                    .all(|c| c.is_ascii_alphanumeric() || b"._-".contains(&c))
        };
        if input.schema_version != 1
            || !identifier(&input.source, 64)
            || !identifier(&input.code, 96)
            || input.message.is_empty()
            || input.message.len() > 12000
        {
            return Err("Invalid error event".into());
        }
        let mut context = Map::new();
        // Never persist arbitrary payloads, programs, credentials or environment dumps.
        for key in [
            "action",
            "axis",
            "joint",
            "mode",
            "velocity",
            "increment",
            "direction",
            "limit",
            "motionMode",
            "powered",
            "estop",
            "busy",
            "commandState",
            "exit_code",
        ] {
            if let Some(value) = input.context.get(key) {
                if value.is_boolean() || value.is_number() || value.is_null() {
                    context.insert(key.into(), value.clone());
                } else if let Some(value) = value.as_str() {
                    context.insert(
                        key.into(),
                        Value::String(redact(&value.chars().take(128).collect::<String>())),
                    );
                }
            }
        }
        let now = Utc::now();
        let category = categories::classify(&input.source, &input.code, &input.message).into();
        Ok(Self {
            schema_version: 1,
            event_id: uuid::Uuid::new_v4().to_string(),
            timestamp: now.to_rfc3339_opts(SecondsFormat::Millis, true),
            received_ms: now.timestamp_millis(),
            category,
            source: input.source,
            code: input.code,
            message: redact(&input.message),
            context,
            uid,
            pid,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn refused_jog_keeps_numeric_context_without_credentials() {
        let event = Event::receive(br#"{"schema_version":1,"source":"controller","code":"command_rejected","message":"velocity invalid parameter password=abc","context":{"velocity":12,"joint":4,"password":"do-not-store"}}"#, 123, 456).unwrap();
        assert_eq!(event.category, "parameters");
        assert_eq!(event.context["joint"], 4);
        assert!(!event.context.contains_key("password"));
        assert!(!event.message.contains("abc"));
        assert_eq!(event.uid, 123);
    }
    #[test]
    fn category_and_export_paths_are_not_caller_controlled() {
        assert!(Event::receive(br#"{"schema_version":1,"source":"../../tmp","code":"bad","message":"failure","context":{}}"#, 1, 1).is_err());
        assert!(Event::receive(br#"{"schema_version":1,"source":"ui","code":"bad","message":"failure","context":{},"category":"../../tmp"}"#, 1, 1).is_err());
    }
}
