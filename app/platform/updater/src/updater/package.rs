//! Validate both Debian archive streams against this product's installation boundary.
use super::Result;
use std::{path::Path, process::Stdio};
const INSPECTOR: &str = include_str!("package_members.py");

pub(super) fn validate(path: &Path) -> Result<()> {
    for (option, kind) in [("--fsys-tarfile", "data"), ("--ctrl-tarfile", "control")] {
        let mut archive = super::command("/usr/bin/dpkg-deb")
            .arg(option)
            .arg(path)
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()?;
        let source = archive.stdout.take().ok_or("无法读取安装包内容")?;
        let inspection = super::command("/usr/bin/python3")
            .args(["-I", "-S", "-c", INSPECTOR, kind])
            .stdin(source)
            .output();
        if !inspection
            .as_ref()
            .is_ok_and(|output| output.status.success())
        {
            let _ = archive.kill();
        }
        let extracted = archive.wait()?;
        let inspection = inspection?;
        if !extracted.success() || !inspection.status.success() {
            let detail = String::from_utf8_lossy(&inspection.stderr);
            return Err(format!("更新包超出固定系统安装边界：{}", detail.trim()).into());
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    const POSTINST: &[u8] = include_bytes!("../../../../../tools/appliance/packaging/postinst");

    #[test]
    fn validates_real_debian_data_and_control_archives() {
        if !cfg!(target_os = "linux") {
            return;
        }
        let directory = tempfile::tempdir().unwrap();
        let source = directory.path().join("root");
        std::fs::create_dir_all(source.join("DEBIAN")).unwrap();
        std::fs::create_dir_all(source.join("usr/bin")).unwrap();
        std::fs::write(source.join("DEBIAN/control"), "Package: betterlinuxcnc-qt\nVersion: 1.0\nArchitecture: all\nMaintainer: Test <test@example.invalid>\nDescription: Controlled update boundary fixture\n").unwrap();
        std::fs::write(source.join("usr/bin/betterlinuxcnc"), "fixture").unwrap();
        let package = directory.path().join("test.deb");
        let build = || {
            let output = super::super::command("/usr/bin/dpkg-deb")
                .args(["--build", "--root-owner-group"])
                .arg(&source)
                .arg(&package)
                .output()
                .unwrap();
            assert!(
                output.status.success(),
                "{}",
                String::from_utf8_lossy(&output.stderr)
            );
        };
        build();
        validate(&package).unwrap();
        std::fs::create_dir_all(source.join("etc")).unwrap();
        std::fs::write(source.join("etc/sudoers"), "forbidden").unwrap();
        build();
        assert!(validate(&package).is_err());
        std::fs::remove_file(source.join("etc/sudoers")).unwrap();
        std::fs::write(source.join("DEBIAN/postinst"), POSTINST).unwrap();
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(
            source.join("DEBIAN/postinst"),
            std::fs::Permissions::from_mode(0o755),
        )
        .unwrap();
        build();
        validate(&package).unwrap();
        std::fs::write(source.join("DEBIAN/postinst"), "#!/bin/sh\nexit 0\n").unwrap();
        build();
        assert!(validate(&package).is_err());
        std::fs::write(source.join("DEBIAN/postinst"), POSTINST).unwrap();
        std::fs::copy(
            source.join("DEBIAN/postinst"),
            source.join("DEBIAN/preinst"),
        )
        .unwrap();
        build();
        assert!(validate(&package).is_err());
    }

    #[test]
    fn tar_stream_boundary_rejects_paths_links_scripts_and_privilege_bits() {
        let python = std::env::var_os("SERVICE_TEST_PYTHON").unwrap_or_else(|| "python3".into());
        let driver = r#"
import io, sys, tarfile
scope = {'__name__': 'validator'}
exec(sys.argv[1], scope)
def check(name, kind='data', entry_type=tarfile.REGTYPE, mode=0o644, payload=b'abc', uid=0, gid=0):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w') as archive:
        item=tarfile.TarInfo(name); item.type=entry_type; item.mode=mode; item.uid=uid; item.gid=gid
        if entry_type == tarfile.SYMTYPE: item.linkname='/etc/sudoers'
        if entry_type == tarfile.LNKTYPE: item.linkname='../../etc/sudoers'
        item.size=len(payload) if entry_type == tarfile.REGTYPE else 0
        archive.addfile(item, io.BytesIO(payload) if item.size else None)
    out.seek(0)
    try: scope['inspect'](out, kind); return True
    except ValueError: return False
assert check('./usr/bin/betterlinuxcnc')
assert check('./usr/bin/pa')
assert not check('./usr/bin/pa-helper')
assert check('./usr/lib/betterlinuxcnc/python/bettercnc/__init__.py')
assert check('./usr/sbin/betterlinuxcnc-appliance')
assert check('./usr/lib/systemd/system/betterlinuxcnc-system-update.service')
for name in ['betterlinuxcnc-mesa-update', 'betterlinuxcnc-mesa-flash']:
    assert check('./usr/bin/' + name)
    assert check('./usr/lib/systemd/system/' + name + '.service')
assert check('./usr/lib/systemd/system/betterlinuxcnc-mesa-update.timer')
assert not check('./usr/lib/systemd/system/betterlinuxcnc-mesa-flash.timer')
assert check('./usr/lib/betterlinuxcnc/appliance/betterlinuxcnc-axis-profile@.service')
assert check('./usr/lib/betterlinuxcnc/appliance/00-betterlinuxcnc-axis-settings.rules')
assert not check('./usr/lib/systemd/system/betterlinuxcnc-axis-profile@.service')
assert not check('./usr/lib/systemd/system/betterlinuxcnc-axis-profile@6.service')
assert not check('./usr/lib/systemd/system/betterlinuxcnc-axis-profile.timer')
assert not check('./usr/bin/mesaflash')
assert check('./usr/lib/linuxcnc/modules/zhulong_homing.so')
assert not check('./usr/lib/linuxcnc/modules/homing.so')
assert not check('./usr/lib/linuxcnc/modules/unapproved.so')
assert check('control', kind='control')
assert check('conffiles', kind='control', payload=b'/etc/betterlinuxcnc/updater.json\n')
approved_postinst = scope['APPROVED_POSTINST']
assert approved_postinst == sys.argv[2].encode('utf-8'), 'packaged postinst contract changed'
assert check('./postinst', kind='control', mode=0o755, payload=approved_postinst)
for payload in [approved_postinst+b'\n', approved_postinst[:-1],
                approved_postinst.replace(b'\n', b'\r\n'),
                approved_postinst.replace(b' provision\n', b' activate\n'),
                approved_postinst.replace(b'/usr/sbin/', b'/usr/bin/'),
                approved_postinst.replace(b'        exec ', b'        sudo '),
                b'#!/bin/sh\nexit 0\n']:
    assert not check('postinst', kind='control', mode=0o755, payload=payload), payload
for mode in [0o644, 0o700, 0o775, 0o4755]:
    assert not check('postinst', kind='control', mode=mode, payload=approved_postinst)
assert not check('postinst', kind='control', mode=0o755, payload=approved_postinst, uid=1000)
assert not check('postinst', kind='control', mode=0o755, payload=approved_postinst, gid=1000)
for name in ['/usr/bin/betterlinuxcnc','../etc/sudoers','usr/../etc/sudoers','home/linuxcnc/x','opt/x','usr/bin/bash','etc/sudoers','usr/lib/systemd/system/arbitrary.service']:
    assert not check(name), name
for mode in [0o4755,0o2755,0o666,0o775]: assert not check('usr/bin/betterlinuxcnc', mode=mode)
for type_ in [tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.CHRTYPE,tarfile.FIFOTYPE]:
    assert not check('usr/lib/betterlinuxcnc/link', entry_type=type_)
for name in ['postinst','preinst','prerm','postrm','config','triggers']:
    assert not check(name,kind='control'), name
for name in ['preinst','prerm','postrm','config','triggers']:
    assert not check(name,kind='control',mode=0o755,payload=approved_postinst), name
assert not check('conffiles',kind='control',payload=b'/etc/sudoers\n')
"#;
        let output = std::process::Command::new(python)
            .args([
                "-I",
                "-S",
                "-c",
                driver,
                INSPECTOR,
                std::str::from_utf8(POSTINST).unwrap(),
            ])
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
}
