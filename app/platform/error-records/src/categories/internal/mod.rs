//! Internal error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    ["panic", "uncaught", "internal", "traceback", "exception"]
        .iter()
        .any(|word| text.contains(word))
}
