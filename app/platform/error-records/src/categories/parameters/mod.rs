//! Parameters error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    [
        "允许范围",
        "有限数值",
        "必须是整数",
        "必须为整数",
        "无效坐标系",
        "invalid parameter",
        "invalid_params",
        "invalid argument",
    ]
    .iter()
    .any(|word| text.contains(word))
}
