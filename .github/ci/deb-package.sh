#!/bin/bash
# Run only inside a disposable GitHub-hosted Debian 13 container.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true && $(id -u) == 0 ]] || {
  echo "DEB builds and installation checks are restricted to the GitHub CI container." >&2
  exit 2
}
: "${BUILD_SHA:?The checkout commit is required}"
export DEBIAN_FRONTEND=noninteractive
# Dependency maintainer scripts must not start machine, display or SSH services.
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod 755 /usr/sbin/policy-rc.d
apt-get update
mapfile -t native_packages < .github/ci/native/packages.txt
apt-get install -y --no-install-recommends \
  "${native_packages[@]}" cmake curl
curl --fail --silent --show-error --location --retry 3 \
  https://sh.rustup.rs --output /tmp/rustup-init.sh
sh /tmp/rustup-init.sh -y --no-modify-path --default-toolchain none
export PATH="/root/.cargo/bin:$PATH"
for module in app/platform/cam-link app/platform/updater app/platform/mesa-update app/platform/manage-ini app/platform/account-management/cnc-maint; do
  version=$(python3 -c 'import sys,tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["toolchain"]["channel"])' "$module/rust-toolchain.toml")
  rustup toolchain install "$version" --profile minimal --component rustfmt --component clippy
done
cmake -S /workspace -B /tmp/application-build \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
  -DCMAKE_INSTALL_PREFIX:PATH=/usr -DCMAKE_INSTALL_LIBDIR:STRING=lib \
  -DBETTERCNC_PROJECT_DIR=/etc/betterlinuxcnc \
  -DBETTERCNC_BUILD_SYSTEM_SERVICES=ON -DBETTERCNC_BUILD_MESA_HOMING=ON \
  -DPython3_EXECUTABLE=/usr/bin/python3
cmake --build /tmp/application-build --parallel 2
cpack --config /tmp/application-build/CPackConfig.cmake -G DEB -B /tmp/packages
packages=(/tmp/packages/*.deb)
[[ ${#packages[@]} == 1 && -f ${packages[0]} ]]
python3 .github/ci/verify-deb-install.py "${packages[0]}" /workspace
cp "${packages[0]}" /output/
cd /output
sha256sum ./*.deb | sed 's|  \./|  |' > SHA256SUMS
printf '%s\n' "$BUILD_SHA" > SOURCE_COMMIT
