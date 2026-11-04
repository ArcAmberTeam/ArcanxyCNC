//! Homing error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    ["回零", "homing", "home switch", "home_all"]
        .iter()
        .any(|word| text.contains(word))
}
