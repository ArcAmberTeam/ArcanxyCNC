//! The manage verb selects a registered logical target, never an arbitrary path.

use crate::targets::{self, Target};
use std::ffi::OsString;

pub(crate) const NAME: &str = "manage";

pub(crate) fn parse(arguments: &[OsString]) -> Result<Target, &'static str> {
    match arguments {
        [name] => targets::resolve(name).ok_or("Unknown management target"),
        _ => Err("Expected exactly one management target"),
    }
}

pub(crate) fn print_help() {
    for target in targets::ALL {
        println!("  {NAME} {}", target.name);
    }
}
