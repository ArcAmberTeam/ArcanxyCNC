use crate::contract::{self, Manifest, MAX_BIT_BYTES};
use crate::Result;
use reqwest::blocking::Client;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::io::Read;
use std::time::Duration;

const API: &str = "https://api.github.com/repos/ArcAmberTeam";
const APP: &str = "ArcanxyCNC";
const MAX_METADATA: u64 = 1024 * 1024;

pub(crate) trait Fetch {
    fn get(&self, url: &str, limit: u64) -> Result<Vec<u8>>;
}

pub(crate) struct OfficialHttp(Client);

impl OfficialHttp {
    pub(crate) fn new() -> Result<Self> {
        Ok(Self(
            Client::builder()
                .no_proxy()
                .https_only(true)
                .connect_timeout(Duration::from_secs(15))
                .timeout(Duration::from_secs(120))
                .user_agent("BetterLinuxCNC-Mesa-Update/1")
                .redirect(reqwest::redirect::Policy::custom(|attempt| {
                    let url = attempt.url();
                    if attempt.previous().len() >= 5
                        || url.scheme() != "https"
                        || !matches!(
                            url.host_str(),
                            Some(
                                "github.com"
                                    | "release-assets.githubusercontent.com"
                                    | "objects.githubusercontent.com"
                            )
                        )
                        || !url.username().is_empty()
                        || url.password().is_some()
                        || url.port_or_known_default() != Some(443)
                    {
                        attempt.error("Untrusted release redirect")
                    } else {
                        attempt.follow()
                    }
                }))
                .build()?,
        ))
    }
}

impl Fetch for OfficialHttp {
    fn get(&self, url: &str, limit: u64) -> Result<Vec<u8>> {
        let response = self
            .0
            .get(url)
            .send()
            .map_err(|_| "Official release request failed")?;
        if !response.status().is_success() {
            return Err(format!(
                "Official release request returned HTTP {}",
                response.status()
            )
            .into());
        }
        if response.content_length().is_some_and(|size| size > limit) {
            return Err("Official release response exceeds limit".into());
        }
        let mut bytes = Vec::new();
        response
            .take(limit + 1)
            .read_to_end(&mut bytes)
            .map_err(|_| "Official release response could not be read")?;
        if bytes.len() as u64 > limit {
            return Err("Official release response exceeds limit".into());
        }
        Ok(bytes)
    }
}

#[derive(Deserialize)]
struct Release {
    tag_name: String,
    draft: bool,
    prerelease: bool,
    assets: Vec<Asset>,
}

#[derive(Clone, Deserialize)]
struct Asset {
    name: String,
    size: u64,
    browser_download_url: String,
}

#[derive(Deserialize)]
struct GitObject {
    sha: String,
    #[serde(rename = "type")]
    kind: String,
}

#[derive(Deserialize)]
struct GitReference {
    object: GitObject,
}

pub(crate) struct MesaRelease {
    pub(crate) manifest: Manifest,
    firmware: Option<Asset>,
}

pub(crate) fn latest_pair(fetch: &impl Fetch) -> Result<(String, MesaRelease)> {
    let application = fetch_release(fetch, "latest")?;
    let application_version = version(&application)?.to_owned();
    Ok((application_version, verify_manifest(fetch, application)?))
}

pub(crate) fn installed_release(fetch: &impl Fetch, installed: &str) -> Result<MesaRelease> {
    if !contract::valid_version(installed) {
        return Err("Installed application version is not a supported release version".into());
    }
    let release = fetch_release(fetch, &format!("tags/v{installed}"))?;
    if version(&release)? != installed {
        return Err("Official Mesa release does not match the installed application".into());
    }
    verify_manifest(fetch, release)
}

fn fetch_release(fetch: &impl Fetch, selector: &str) -> Result<Release> {
    let bytes = fetch.get(&format!("{API}/{APP}/releases/{selector}"), MAX_METADATA)?;
    let release: Release = serde_json::from_slice(&bytes)?;
    version(&release)?;
    Ok(release)
}

fn version(release: &Release) -> Result<&str> {
    let version = release.tag_name.strip_prefix('v').unwrap_or("");
    if release.draft || release.prerelease || !contract::valid_version(version) {
        return Err("Only official stable version-tagged releases are accepted".into());
    }
    Ok(version)
}

fn asset(release: &Release, name: &str, size: Option<u64>) -> Result<Asset> {
    if !contract::valid_asset(name) {
        return Err("Unsafe Mesa asset name".into());
    }
    let matches: Vec<_> = release
        .assets
        .iter()
        .filter(|item| item.name == name)
        .collect();
    if matches.len() != 1 {
        return Err("Required official Mesa release asset is missing or duplicated".into());
    }
    let selected = matches[0];
    let expected = format!(
        "https://github.com/ArcAmberTeam/{APP}/releases/download/{}/{name}",
        release.tag_name
    );
    if selected.browser_download_url != expected
        || selected.size == 0
        || size.is_some_and(|size| selected.size != size)
    {
        return Err("Mesa asset URL or size differs from official release metadata".into());
    }
    Ok(selected.clone())
}

fn verify_manifest(fetch: &impl Fetch, release: Release) -> Result<MesaRelease> {
    let manifest_asset = asset(&release, "mesa-release.json", None)?;
    if manifest_asset.size > MAX_METADATA {
        return Err("Mesa manifest exceeds size limit".into());
    }
    let bytes = fetch.get(&manifest_asset.browser_download_url, MAX_METADATA)?;
    if bytes.len() as u64 != manifest_asset.size {
        return Err("Mesa manifest size differs from official release metadata".into());
    }
    let manifest: Manifest = serde_json::from_slice(&bytes)?;
    manifest.validate(version(&release)?)?;
    verify_tag(fetch, &manifest)?;
    for item in [&manifest.artifacts.source, &manifest.artifacts.integration] {
        asset(&release, &item.asset, Some(item.size_bytes))?;
    }
    let firmware = if manifest.firmware.available {
        Some(asset(
            &release,
            manifest
                .firmware
                .asset
                .as_deref()
                .ok_or("Missing firmware asset")?,
            manifest.firmware.size,
        )?)
    } else {
        None
    };
    Ok(MesaRelease { manifest, firmware })
}

fn verify_tag(fetch: &impl Fetch, manifest: &Manifest) -> Result<()> {
    let bytes = fetch.get(
        &format!("{API}/{APP}/git/ref/tags/{}", manifest.tag_name),
        MAX_METADATA,
    )?;
    let mut object: GitReference = serde_json::from_slice(&bytes)?;
    for _ in 0..4 {
        if object.object.kind == "commit" {
            if object.object.sha == manifest.source_commit {
                return Ok(());
            }
            return Err("Mesa manifest source commit differs from its official version tag".into());
        }
        if object.object.kind != "tag"
            || object.object.sha.len() != 40
            || !object
                .object
                .sha
                .bytes()
                .all(|byte| byte.is_ascii_hexdigit())
        {
            break;
        }
        object = serde_json::from_slice(&fetch.get(
            &format!("{API}/{APP}/git/tags/{}", object.object.sha),
            MAX_METADATA,
        )?)?;
    }
    Err("Mesa official version tag does not resolve to an approved source commit".into())
}

pub(crate) fn firmware(fetch: &impl Fetch, release: &MesaRelease) -> Result<Option<Vec<u8>>> {
    let Some(asset) = &release.firmware else {
        return Ok(None);
    };
    let bytes = fetch.get(&asset.browser_download_url, MAX_BIT_BYTES)?;
    if bytes.len() as u64 != asset.size
        || Some(format!("{:x}", Sha256::digest(&bytes))) != release.manifest.firmware.sha256
    {
        return Err("Mesa firmware size or SHA-256 verification failed".into());
    }
    Ok(Some(bytes))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use std::collections::BTreeMap;

    struct Fixture {
        responses: BTreeMap<String, Vec<u8>>,
        calls: RefCell<Vec<String>>,
    }

    impl Fetch for Fixture {
        fn get(&self, url: &str, limit: u64) -> Result<Vec<u8>> {
            self.calls.borrow_mut().push(url.into());
            let bytes = self.responses.get(url).ok_or("Unexpected request")?;
            assert!(bytes.len() as u64 <= limit);
            Ok(bytes.clone())
        }
    }

    fn fixture(manifest: &Manifest) -> Fixture {
        let bytes = serde_json::to_vec(manifest).unwrap();
        let mut assets = vec![serde_json::json!({
            "name": "mesa-release.json", "size": bytes.len(),
            "browser_download_url": format!("https://github.com/ArcAmberTeam/ArcanxyCNC/releases/download/{}/mesa-release.json", manifest.tag_name),
        })];
        for artifact in [&manifest.artifacts.source, &manifest.artifacts.integration] {
            assets.push(serde_json::json!({
                "name": artifact.asset, "size": artifact.size_bytes,
                "browser_download_url": format!("https://github.com/ArcAmberTeam/ArcanxyCNC/releases/download/{}/{}", manifest.tag_name, artifact.asset),
            }));
        }
        if let Some(name) = &manifest.firmware.asset {
            assets.push(serde_json::json!({
                "name": name, "size": manifest.firmware.size,
                "browser_download_url": format!("https://github.com/ArcAmberTeam/ArcanxyCNC/releases/download/{}/{name}", manifest.tag_name),
            }));
        }
        let release = serde_json::to_vec(&serde_json::json!({
            "tag_name": manifest.tag_name, "draft": false, "prerelease": false, "assets": assets,
        }))
        .unwrap();
        Fixture {
            calls: RefCell::new(Vec::new()),
            responses: BTreeMap::from([
                (format!("{API}/{APP}/releases/tags/{}", manifest.tag_name), release.clone()),
                (format!("{API}/{APP}/releases/latest"), release),
                (format!("https://github.com/ArcAmberTeam/ArcanxyCNC/releases/download/{}/mesa-release.json", manifest.tag_name), bytes),
                (format!("{API}/{APP}/git/ref/tags/{}", manifest.tag_name), serde_json::to_vec(&serde_json::json!({"object":{"type":"commit", "sha":manifest.source_commit}})).unwrap()),
            ]),
        }
    }

    #[test]
    fn source_only_download_never_requests_a_bitstream() {
        let fetch = fixture(&contract::fixture());
        let release = installed_release(&fetch, "26.10.26.1").unwrap();
        assert!(firmware(&fetch, &release).unwrap().is_none());
        assert!(fetch
            .calls
            .borrow()
            .iter()
            .all(|url| !url.ends_with(".bit")));
        let (app, mesa) = latest_pair(&fetch).unwrap();
        assert_eq!(app, mesa.manifest.version);
    }

    #[test]
    fn official_source_commit_and_stable_release_are_required() {
        let manifest = contract::fixture();
        let mut fetch = fixture(&manifest);
        let ref_url = format!("{API}/{APP}/git/ref/tags/{}", manifest.tag_name);
        fetch.responses.insert(
            ref_url,
            br#"{"object":{"type":"commit","sha":"bad"}}"#.to_vec(),
        );
        assert!(installed_release(&fetch, "26.10.26.1").is_err());
        let mut fetch = fixture(&manifest);
        let url = format!("{API}/{APP}/releases/tags/{}", manifest.tag_name);
        let mut value: serde_json::Value = serde_json::from_slice(&fetch.responses[&url]).unwrap();
        value["prerelease"] = true.into();
        fetch
            .responses
            .insert(url, serde_json::to_vec(&value).unwrap());
        assert!(installed_release(&fetch, "26.10.26.1").is_err());
    }

    #[test]
    fn verified_download_rejects_substituted_bytes_and_foreign_urls() {
        let mut manifest = contract::fixture();
        manifest.physical_constraints_verified = true;
        manifest.firmware.available = true;
        manifest.firmware.origin = "ci-build".into();
        manifest.firmware.asset = Some("new.bit".into());
        manifest.firmware.size = Some(3);
        manifest.firmware.sha256 = Some(format!("{:x}", Sha256::digest(b"bit")));
        manifest.firmware.verification = contract::Verification {
            implementation: true,
            timing: true,
            board_approved: true,
        };
        let mut fetch = fixture(&manifest);
        let url = format!(
            "https://github.com/ArcAmberTeam/ArcanxyCNC/releases/download/{}/new.bit",
            manifest.tag_name
        );
        fetch.responses.insert(url.clone(), b"bit".to_vec());
        let release = installed_release(&fetch, "26.10.26.1").unwrap();
        assert_eq!(firmware(&fetch, &release).unwrap(), Some(b"bit".to_vec()));
        fetch.responses.insert(url, b"old".to_vec());
        assert!(firmware(&fetch, &release).is_err());
        let url = format!("{API}/{APP}/releases/tags/{}", manifest.tag_name);
        let mut value: serde_json::Value = serde_json::from_slice(&fetch.responses[&url]).unwrap();
        value["assets"][0]["browser_download_url"] = "https://example.com/mesa-release.json".into();
        fetch
            .responses
            .insert(url, serde_json::to_vec(&value).unwrap());
        assert!(installed_release(&fetch, "26.10.26.1").is_err());
    }
}
