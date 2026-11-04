//! Account error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    [
        "permission",
        "denied",
        "权限",
        "认证",
        "password",
        "account",
        "unauthorized",
    ]
    .iter()
    .any(|word| text.contains(word))
}
