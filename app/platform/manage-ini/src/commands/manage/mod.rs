//! The manage verb selects a registered logical target, never an arbitrary path.

pub(crate) mod sudo;

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
    println!("  manage sudo open  (authenticate cnc-maint; allow sudo for 15 minutes)");
    for target in targets::ALL {
        println!("  {NAME} {}", target.name);
    }
}
