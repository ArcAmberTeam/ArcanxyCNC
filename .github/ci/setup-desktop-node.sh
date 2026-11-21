#!/bin/bash
# Install the verified Node distribution only inside a disposable hosted CI container.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true ]] || { echo "Desktop toolchains are installed only in GitHub CI." >&2; exit 2; }
node_version=24.21.0
node_archive="node-v${node_version}-linux-x64.tar.xz"
node_download=$(mktemp -d)
trap 'rm -rf "$node_download"' EXIT
curl --fail --silent --show-error --location --retry 3 "https://nodejs.org/dist/v${node_version}/$node_archive" --output "$node_download/$node_archive"
curl --fail --silent --show-error --location --retry 3 "https://nodejs.org/dist/v${node_version}/SHASUMS256.txt" --output "$node_download/SHASUMS256.txt"
(cd "$node_download" && awk -v archive="$node_archive" '$2 == archive' SHASUMS256.txt | sha256sum --check --strict -)
tar -xJf "$node_download/$node_archive" -C /usr/local --strip-components=1
