//! Motion error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    [
        "点动",
        "运动",
        "跟随误差",
        "jog",
        "following error",
        "motion",
        "command_timeout",
    ]
    .iter()
    .any(|word| text.contains(word))
}
