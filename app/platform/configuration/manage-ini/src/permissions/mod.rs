//! Authorize the OS account, never environment variables or SSH command text.

pub(crate) fn authorize() -> Result<(), &'static str> {
    #[cfg(target_os = "linux")]
    {
        let uid = account_uid(c"cnc-maint")?;
        // SAFETY: UID reads have no pointer arguments and do not alter credentials.
        let (real, effective) = unsafe { (libc::getuid(), libc::geteuid()) };
        if uid != 0 && real == uid && effective == uid {
            Ok(())
        } else {
            Err("Only the cnc-maint account may open PA")
        }
    }
    #[cfg(not(target_os = "linux"))]
    Err("PA requires Linux maintenance-account authentication")
}

pub(crate) fn account_uid(name: &std::ffi::CStr) -> Result<libc::uid_t, &'static str> {
    let mut record = std::mem::MaybeUninit::<libc::passwd>::uninit();
    let mut result = std::ptr::null_mut();
    let mut buffer = vec![0_u8; 4096];
    loop {
        // SAFETY: all pointers refer to initialized or writable storage for getpwnam_r.
        let error = unsafe {
            libc::getpwnam_r(
                name.as_ptr(),
                record.as_mut_ptr(),
                buffer.as_mut_ptr().cast(),
                buffer.len(),
                &mut result,
            )
        };
        if error == libc::ERANGE && buffer.len() < 1024 * 1024 {
            buffer.resize(buffer.len() * 2, 0);
            continue;
        }
        if error != 0 || result.is_null() {
            return Err("Required appliance account is unavailable");
        }
        // SAFETY: getpwnam_r succeeded and initialized record.
        return Ok(unsafe { record.assume_init().pw_uid });
    }
}
