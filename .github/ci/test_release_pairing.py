"""Exercise the source-only Mesa publication gate against the CI bundle."""

import json
from pathlib import Path
import subprocess
import textwrap
import unittest


class ReleasePairingTests(unittest.TestCase):
    def test_only_matching_artifacts_from_the_application_commit_can_publish(self):
        workflow = (Path(__file__).parents[1] / "workflows/release.yml").read_text()
        start = workflow.index("            const digest =")
        end = workflow.index("            try {", start)
        verifier = textwrap.dedent(workflow[start:end])
        fixture = r"""
const crypto = require('node:crypto');
const sha = 'a'.repeat(40), version = '26.11.21.1', tag = 'v' + version;
const repo = {owner: 'ArcAmberTeam', repo: 'ArcanxyCNC'};
const root = 'release-artifact';
const mode = process.argv[1];
const files = new Map();
const fs = {readFileSync: path => {
  if (!files.has(path)) throw Error('Missing asset');
  return files.get(path);
}};
const manifest = {
  schema_version: 1, version, tag_name: tag, source_commit: sha, compatible_app_version: version,
  board: 'zhulong-v2', variant: 'PIN_ZHULONG_V2_34', fpga: 'xc6slx9', package: 'tqg144',
  physical_constraints_verified: false, artifacts: {},
  firmware: {available: false, asset: null, size: null, sha256: null, origin: 'unavailable',
    verification: {implementation: false, timing: false, board_approved: false}}
};
for (const kind of ['source', 'integration']) {
  const asset = `cnc-mesa-${kind}-${version}.tar.gz`;
  const bytes = Buffer.from(kind);
  manifest.artifacts[kind] = {asset, size_bytes: bytes.length, sha256: digest(bytes)};
  files.set(root + '/' + asset, bytes);
}
if (mode === 'wrong-source') manifest.source_commit = 'b'.repeat(40);
if (mode === 'wrong-version') manifest.compatible_app_version = '26.11.05.1';
if (mode === 'wrong-board') manifest.board = 'other';
if (mode === 'available') manifest.firmware.available = true;
if (mode === 'hardware-claim') manifest.firmware.verification.timing = true;
if (mode === 'hidden-payload') manifest.firmware.asset = 'original.bit';
if (mode === 'bad-hash') manifest.artifacts.source.sha256 = '0'.repeat(64);
if (mode === 'bad-size') manifest.artifacts.integration.size_bytes++;
if (mode === 'swapped') manifest.artifacts.source.asset = manifest.artifacts.integration.asset;
if (mode === 'missing') files.delete(root + '/' + manifest.artifacts.source.asset);
files.set(root + '/mesa-release.json', Buffer.from(JSON.stringify(manifest)));
try {
  const assets = verifyMesaRelease();
  const receipt = JSON.parse(assets.get('CNC_MESA_PAIR.json'));
  if (receipt.app.source_commit !== sha || receipt.mesa.source_commit !== sha ||
      receipt.mesa.repository !== repo.owner + '/' + repo.repo ||
      receipt.mesa.manifest_sha256 !== digest(assets.get('mesa-release.json')) || assets.size !== 4)
    throw Error('Unexpected release provenance');
  console.log('true');
} catch (error) { console.log('false'); }
"""
        for mode in ("valid", "wrong-source", "wrong-version", "wrong-board", "available",
                     "hardware-claim", "hidden-payload", "bad-hash", "bad-size", "swapped", "missing"):
            with self.subTest(mode=mode):
                result = subprocess.run(["node", "-e", verifier + fixture, mode],
                                        capture_output=True, text=True, check=True, timeout=10)
                self.assertEqual(json.loads(result.stdout), mode == "valid")


if __name__ == "__main__":
    unittest.main()
