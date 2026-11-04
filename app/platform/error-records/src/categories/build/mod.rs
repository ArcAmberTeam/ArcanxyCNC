//! Build error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    ["build", "cargo", "cmake", "编译", "打包", "git "]
        .iter()
        .any(|word| text.contains(word))
}
