//! Configuration error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    [
        " ini",
        ".ini",
        "ini ",
        "halfile",
        "configuration",
        "配置",
        "axis-profile",
        "axis_profile",
    ]
    .iter()
    .any(|word| text.contains(word))
}
