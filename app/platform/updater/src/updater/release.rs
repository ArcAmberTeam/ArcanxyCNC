use super::{
    storage::{self, Staged, Store},
    Event, Result, PACKAGE, REPOSITORY,
};
use reqwest::{blocking::Client, StatusCode, Url};
use serde::Deserialize;
use std::{
    fs::File,
    io::{Read, Seek, SeekFrom, Write},
    time::Duration,
};

const MAX_PACKAGE: u64 = 1024 * 1024 * 1024;

#[derive(Deserialize)]
struct Release {
    tag_name: String,
    draft: bool,
    prerelease: bool,
    assets: Vec<Asset>,
}
#[derive(Deserialize)]
struct Asset {
    name: String,
    size: u64,
    browser_download_url: String,
    digest: Option<String>,
}

fn asset_url(asset: &Asset) -> Result<Url> {
    let url = Url::parse(&asset.browser_download_url)?;
    if url.scheme() != "https"
        || url.host_str() != Some("github.com")
        || !url
            .path()
            .starts_with(&format!("/{REPOSITORY}/releases/download/"))
        || !url.username().is_empty()
        || url.password().is_some()
        || url.port().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err("Release 下载地址不属于当前仓库".into());
    }
    Ok(url)
}

fn select_package<'a>(release: &'a Release, architecture: &str) -> Result<&'a Asset> {
    if release.draft || release.prerelease {
        return Err("只接受正式 Release".into());
    }
    let candidates: Vec<_> = release
        .assets
        .iter()
        .filter(|asset| {
            asset.name.starts_with(&format!("{PACKAGE}_"))
                && asset.name.ends_with(&format!("_{architecture}.deb"))
        })
        .collect();
    if candidates.len() != 1 {
        return Err(format!(
            "最新 Release 需要且只能提供一个 {PACKAGE}_<版本>_{architecture}.deb 安装包"
        )
        .into());
    }
    let asset = candidates[0];
    if asset.size == 0 || asset.size > MAX_PACKAGE {
        return Err("Release 安装包大小无效或超过 1 GiB".into());
    }
    asset_url(asset)?;
    Ok(asset)
}

fn checksum(text: &str, name: &str) -> Result<String> {
    let matches: Vec<_> = text
        .lines()
        .filter_map(|line| {
            let fields: Vec<_> = line.split_whitespace().collect();
            (fields.len() == 2 && fields[1].trim_start_matches('*') == name).then(|| fields[0])
        })
        .collect();
    if matches.len() != 1 {
        return Err("SHA256SUMS 未提供唯一的安装包校验值".into());
    }
    parse_digest(matches[0])
}

fn parse_digest(value: &str) -> Result<String> {
    if value.len() != 64 || !value.bytes().all(|c| c.is_ascii_hexdigit()) {
        return Err("Release 的 SHA-256 校验值无效".into());
    }
    Ok(value.to_ascii_lowercase())
}

fn bounded_body(mut response: reqwest::blocking::Response, limit: u64) -> Result<Vec<u8>> {
    if response.content_length().is_some_and(|size| size > limit) {
        return Err("Release 响应过大".into());
    }
    let mut body = Vec::new();
    (&mut response).take(limit + 1).read_to_end(&mut body)?;
    if body.len() as u64 > limit {
        return Err("Release 响应超过大小限制".into());
    }
    Ok(body)
}

pub(super) fn fetch(store: &Store, current_version: &str) -> Result<()> {
    if !cfg!(target_os = "linux") {
        return Err("固件更新仅支持 Debian 安装版本".into());
    }
    let installed = storage::installed_version(current_version)?;
    let architecture = super::install::architecture()?;
    store.publish(&Event::new("checking", "正在检查最新 Release…", "", 0))?;
    let client = Client::builder()
        .no_proxy()
        .https_only(true)
        .connect_timeout(Duration::from_secs(15))
        .timeout(Duration::from_secs(1800))
        .redirect(reqwest::redirect::Policy::limited(5))
        .user_agent(concat!(
            "BetterLinuxCNC-Updater/",
            env!("CARGO_PKG_VERSION")
        ))
        .build()?;
    let response = client
        .get(format!(
            "https://api.github.com/repos/{REPOSITORY}/releases/latest"
        ))
        .header("Accept", "application/vnd.github+json")
        .header("X-GitHub-Api-Version", "2022-11-28")
        .timeout(Duration::from_secs(30))
        .send()?;
    if response.status() == StatusCode::NOT_FOUND {
        return store.publish(&Event::new(
            "no_release",
            "当前仓库尚未发布正式 Release",
            "",
            0,
        ));
    }
    if response.status() == StatusCode::FORBIDDEN
        || response.status() == StatusCode::TOO_MANY_REQUESTS
    {
        return Err("GitHub 暂时限制了更新查询，请稍后重试".into());
    }
    let release: Release = serde_json::from_slice(&bounded_body(
        response.error_for_status()?,
        2 * 1024 * 1024,
    )?)?;
    let tag_version = release
        .tag_name
        .strip_prefix('v')
        .unwrap_or(&release.tag_name);
    storage::validate_version(tag_version)?;
    if !betterlinuxcnc_local_update::accepts_official(tag_version, &installed)? {
        return store.publish(&Event::new("current", "已是最新版本", &installed, 100));
    }
    let asset = select_package(&release, &architecture)?;
    let expected = if let Some(value) = &asset.digest {
        parse_digest(
            value
                .strip_prefix("sha256:")
                .ok_or("Release 校验算法不是 SHA-256")?,
        )?
    } else {
        let sums: Vec<_> = release
            .assets
            .iter()
            .filter(|item| item.name == "SHA256SUMS")
            .collect();
        if sums.len() != 1 {
            return Err("Release 缺少 SHA-256 校验，请发布 SHA256SUMS 后重试".into());
        }
        let response = client
            .get(asset_url(sums[0])?)
            .timeout(Duration::from_secs(30))
            .send()?
            .error_for_status()?;
        checksum(
            &String::from_utf8(bounded_body(response, 65536)?)?,
            &asset.name,
        )?
    };
    store.publish(&Event::new(
        "downloading",
        "正在下载更新安装包…",
        &release.tag_name,
        0,
    ))?;
    let mut response = client.get(asset_url(asset)?).send()?.error_for_status()?;
    if response
        .content_length()
        .is_some_and(|size| size != asset.size)
    {
        return Err("Release 下载大小与发布信息不符".into());
    }
    let mut file = tempfile::NamedTempFile::new_in(&store.directory)?;
    let mut bytes = 0_u64;
    let mut last_progress = 0;
    let mut buffer = [0; 65536];
    loop {
        let count = response.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        bytes += count as u64;
        if bytes > asset.size {
            return Err("下载内容超过发布的安装包大小".into());
        }
        file.write_all(&buffer[..count])?;
        let progress = (bytes * 100 / asset.size) as u8;
        if progress != last_progress {
            store.publish(&Event::new(
                "downloading",
                "正在下载更新安装包…",
                &release.tag_name,
                progress,
            ))?;
            last_progress = progress;
        }
    }
    if bytes != asset.size {
        return Err("安装包下载不完整，请重试".into());
    }
    store.publish(&Event::new(
        "verifying",
        "正在校验安装包…",
        &release.tag_name,
        100,
    ))?;
    file.seek(SeekFrom::Start(0))?;
    if storage::hash(file.as_file_mut())? != expected {
        return Err("SHA-256 校验失败，已丢弃安装包".into());
    }
    let (version, package_arch) = storage::package_info(file.path())?;
    if package_arch != architecture || version != tag_version {
        return Err("安装包的版本或架构与 Release 不符".into());
    }
    if !betterlinuxcnc_local_update::accepts_official(&version, &installed)? {
        return Err("拒绝安装相同或更低版本".into());
    }
    file.as_file().sync_all()?;
    file.persist(store.directory.join("package.deb"))?;
    store.save(
        "staged.json",
        &Staged {
            version: version.clone(),
            sha256: expected,
            size: bytes,
            architecture,
        },
    )?;
    // Reopen the final payload, so readiness never refers to an unverified temp file.
    let _verified: File = File::open(store.directory.join("package.deb"))?;
    store.publish(&Event::new(
        "ready",
        format!("{version} 已下载并通过校验"),
        &version,
        100,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn http_transport_limits_response_size() {
        use std::{net::TcpListener, thread};
        let server = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = server.local_addr().unwrap();
        let worker = thread::spawn(move || {
            let (mut stream, _) = server.accept().unwrap();
            let mut request = [0; 2048];
            let _ = stream.read(&mut request);
            stream.write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 20\r\nConnection: close\r\n\r\n01234567890123456789").unwrap();
        });
        let response = Client::builder()
            .no_proxy()
            .build()
            .unwrap()
            .get(format!("http://{address}"))
            .send()
            .unwrap();
        assert!(bounded_body(response, 10).is_err());
        worker.join().unwrap();
    }
    fn asset(name: &str) -> Asset {
        Asset {
            name: name.into(),
            size: 100,
            digest: None,
            browser_download_url: format!(
                "https://github.com/{REPOSITORY}/releases/download/v1.0/{name}"
            ),
        }
    }
    #[test]
    fn selects_exact_arch_and_rejects_ambiguous_or_untrusted_assets() {
        let mut release = Release {
            tag_name: "v1.0".into(),
            draft: false,
            prerelease: false,
            assets: vec![
                asset("betterlinuxcnc-qt_1.0_amd64.deb"),
                asset("betterlinuxcnc-qt_1.0_arm64.deb"),
            ],
        };
        assert!(select_package(&release, "amd64").is_ok());
        assert!(select_package(&release, "i386").is_err());
        release
            .assets
            .push(asset("betterlinuxcnc-qt_2.0_amd64.deb"));
        assert!(select_package(&release, "amd64").is_err());
        for url in [
            "http://github.com/ArcAmberTeam/ArcanxyCNC/releases/download/v1/a.deb",
            "https://github.com/ArcAmberTeam/ArcAmberCNC/releases/download/v1/a.deb",
            "https://example.org/a.deb",
            "https://github.com/other/repo/releases/download/v1/a.deb",
        ] {
            let mut item = asset("a.deb");
            item.browser_download_url = url.into();
            assert!(asset_url(&item).is_err());
        }
        release.prerelease = true;
        assert!(select_package(&release, "arm64").is_err());
    }
    #[test]
    fn accepts_renamed_repository_release_metadata() {
        let release: Release = serde_json::from_str(
            r#"{
                "tag_name": "v26.10.27.1",
                "draft": false,
                "prerelease": false,
                "assets": [{
                    "name": "betterlinuxcnc-qt_26.10.27.1_amd64.deb",
                    "size": 9233490,
                    "browser_download_url": "https://github.com/ArcAmberTeam/ArcanxyCNC/releases/download/v26.10.27.1/betterlinuxcnc-qt_26.10.27.1_amd64.deb"
                }]
            }"#,
        )
        .unwrap();
        assert!(select_package(&release, "amd64").is_ok());
    }
    #[test]
    fn requires_one_well_formed_checksum_for_exact_filename() {
        let digest = "a".repeat(64);
        assert_eq!(
            checksum(&format!("{digest} *a.deb\n"), "a.deb").unwrap(),
            digest
        );
        assert!(checksum(&format!("{digest} a.deb\n{digest} a.deb"), "a.deb").is_err());
        assert!(checksum(&format!("{digest} other.deb"), "a.deb").is_err());
        assert!(checksum("bad a.deb", "a.deb").is_err());
    }
}
