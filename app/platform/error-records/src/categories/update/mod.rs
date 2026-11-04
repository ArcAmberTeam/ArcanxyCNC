//! Update error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    [
        "release",
        "github",
        "更新",
        "updater",
        "install-deb",
        "apt ",
        " apt",
        "checksum",
        "校验",
    ]
    .iter()
    .any(|word| text.contains(word))
}
