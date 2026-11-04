//! Storage error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    [
        "mysql",
        "database",
        "disk",
        "storage",
        "no space",
        "磁盘",
        "数据库",
        "文件读写",
    ]
    .iter()
    .any(|word| text.contains(word))
}
