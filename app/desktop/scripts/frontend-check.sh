#!/bin/bash
# Build and verify the manual-control desktop only in a disposable hosted CI container.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true && $(id -u) == 0 ]] || {
  echo "Desktop builds and source tests run only in the GitHub CI container." >&2
  exit 2
}
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl xz-utils python3 make g++ xvfb xauth \
  fonts-noto-cjk fonts-liberation libgtk-3-0t64 libnss3 libasound2t64 libgbm1 \
  libnotify4 libxss1 libxtst6 libdrm2 libxkbcommon0
bash .github/ci/setup-desktop-node.sh
cd app/desktop/web
npm ci --no-audit --no-fund
node scripts/check-boundaries.mjs --self-test
npm run build
npm run test:protocol
npx playwright install --with-deps chromium
xvfb-run -a npm run test:ui
xvfb-run -a ./node_modules/.bin/electron --no-sandbox . --smoke-test --socket /tmp/no-controller-for-startup.sock
npm run package
test -s release/linux-unpacked/resources/app.asar.unpacked/node_modules/node-pty/build/Release/pty.node
# Production uses the namespace sandbox; never ship a setuid sandbox helper.
rm -f release/linux-unpacked/chrome-sandbox
tar -czf /output/manual-control-desktop.tar.gz -C release linux-unpacked
