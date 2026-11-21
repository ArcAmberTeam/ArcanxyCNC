//! Target definitions are independent of the PA executable and manage verb.

mod ini;
mod launcher;

#[derive(Clone, Copy)]
pub(crate) struct Target {
    pub name: &'static str,
    pub title: &'static str,
}

pub(crate) const ALL: &[Target] = &[ini::TARGET, launcher::TARGET];

pub(crate) fn resolve(name: &std::ffi::OsStr) -> Option<Target> {
    ALL.iter().copied().find(|target| name == target.name)
}
