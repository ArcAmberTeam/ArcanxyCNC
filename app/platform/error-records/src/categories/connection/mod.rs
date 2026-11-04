//! Connection error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    [
        "socket",
        "连接",
        "connection",
        "protocol",
        "transport",
        "cam_",
        "timeout",
    ]
    .iter()
    .any(|word| text.contains(word))
}
