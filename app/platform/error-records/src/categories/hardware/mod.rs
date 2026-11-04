//! Hardware error classification; no storage or machine effects.
pub(super) fn matches(text: &str) -> bool {
    [
        "hostmot2",
        "hm2_",
        "encoder",
        "fpga",
        "驱动器",
        "编码器",
        "mesaflash",
        "watchdog",
    ]
    .iter()
    .any(|word| text.contains(word))
}
