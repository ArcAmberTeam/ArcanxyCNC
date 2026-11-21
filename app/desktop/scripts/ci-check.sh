#!/bin/bash
# Exercise the installed headless session client only in GitHub-hosted CI.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true ]] || { echo "Source checks run only in GitHub CI." >&2; exit 2; }
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
exec bash .github/ci/python-check.sh desktop
