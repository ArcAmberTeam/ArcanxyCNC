//! Program error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    [
        "g-code",
        "gcode",
        "rs274",
        "interpreter",
        "程序",
        "刀具",
        "preview",
    ]
    .iter()
    .any(|word| text.contains(word))
}
