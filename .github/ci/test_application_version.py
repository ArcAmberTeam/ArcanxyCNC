"""Verify application version consistency and automatic release eligibility."""

import json
from pathlib import Path
import re
import subprocess
import textwrap
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ApplicationVersionTests(unittest.TestCase):
    def test_display_version_matches_packaged_application(self):
        manifest = json.loads((ROOT / "versions/version.json").read_text())
        self.assertEqual(manifest["schema_version"], 1)
        match = re.fullmatch(r"(\d+\.\d+\.\d+\.\d+)-(dev|release)", manifest["version"])
        self.assertIsNotNone(match)
        version = match[1]
        metadata = tomllib.loads((ROOT / "app/desktop/pyproject.toml").read_text())
        self.assertEqual(version, metadata["project"]["version"])
        for name in ("CMakeLists.txt", "app/desktop/CMakeLists.txt"):
            cmake = (ROOT / name).read_text()
            self.assertRegex(cmake, rf"project\([^\n]* VERSION {re.escape(version)}\s")
        python = (ROOT / "app/desktop/python/bettercnc/__init__.py").read_text()
        self.assertIn(f'__version__ = "{version}"', python)

    def test_release_resolver_requires_marker_and_matching_successful_ci(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text()
        script = textwrap.dedent(workflow.split("          script: |\n", 1)[1].split("\n  publish:", 1)[0])
        fixture = r"""
const mode = process.argv[1];
const sha = 'a'.repeat(40), parent = 'b'.repeat(40);
const repo = {owner: 'owner', repo: 'app'};
const outputs = {};
const core = {setOutput: (key, value) => outputs[key] = value, info: () => {}};
const context = {repo, ref: 'refs/heads/main', eventName: 'workflow_run', payload: {
  workflow_run: {event: 'push', head_branch: 'main', conclusion: 'success', head_sha: sha}
}};
if (mode === 'failed-event') context.payload.workflow_run.conclusion = 'failure';
if (mode === 'pr-ci') context.payload.workflow_run.event = 'pull_request';
if (mode === 'branch-ci') context.payload.workflow_run.head_branch = 'kihon';
if (mode === 'retry' || mode === 'retry-other-branch') {
  context.eventName = 'workflow_dispatch'; context.payload.inputs = {pr_number: '7'};
  if (mode === 'retry-other-branch') context.ref = 'refs/heads/kihon';
}
if (mode === 'merged-event') {
  context.eventName = 'pull_request_target'; context.payload.pull_request = {number: 7};
}
const pr = {number: 7, merged: mode !== 'unmerged', merge_commit_sha: sha,
  base: {ref: 'main', repo: {full_name: 'owner/app'}}, labels: []};
const content = value => ({data: {content: Buffer.from(value).toString('base64')}});
const github = {rest: {
  pulls: {get: async () => ({data: pr})},
  git: {getRef: async () => {
    if (mode === 'unchanged') return {data: {object: {type: 'commit', sha: parent}}};
    if (mode === 'same-tag') return {data: {object: {type: 'commit', sha}}};
    throw Object.assign(new Error('Missing tag'), {status: 404});
  }},
  repos: {
    listPullRequestsAssociatedWithCommit: 'prs',
    compareCommitsWithBasehead: async () => ({data: {status: mode === 'off-main' ? 'diverged' : 'identical'}}),
    getContent: async ({path}) => {
      if (path === 'app/desktop/pyproject.toml') return content(`version = "${mode === 'package-mismatch' ? '26.11.05.2' : '26.11.05.1'}"`);
      if (mode === 'missing-manifest') throw Object.assign(new Error('Missing'), {status: 404});
      if (mode === 'read-error') throw Object.assign(new Error('Unavailable'), {status: 503});
      let version = '26.11.05.1-release';
      if (mode === 'dev') version = '26.11.05.1-dev';
      if (mode === 'invalid') version = '26.11.05.1-release-extra';
      if (mode === 'invalid-type') version = 42;
      return content(JSON.stringify({schema_version: mode === 'bad-schema' ? 2 : 1, version}));
    }
  },
  actions: {
    getWorkflow: async () => ({data: {id: 1}}),
    listWorkflowRuns: async () => ({data: {workflow_runs: [{id: 2, head_sha: mode === 'wrong-sha' ? parent : sha,
      head_branch: 'main', event: 'push', status: 'completed', conclusion: mode === 'ci-failed' ? 'failure' : 'success'}]}}),
    listJobsForWorkflowRun: 'jobs', listWorkflowRunArtifacts: 'artifacts'
  }
}, paginate: async kind => {
  if (kind === 'prs') return mode === 'no-pr' ? [] : [pr];
  if (kind === 'jobs') return [{name: 'CI Gate', conclusion: mode === 'gate-failed' ? 'failure' : 'success'}];
  if (kind === 'artifacts') return mode === 'missing-artifact' ? [] : [{id: 3,
    expired: mode === 'expired-artifact', name: `betterlinuxcnc-deb-${sha}`}];
  throw new Error('Unexpected API');
}};
"""
        accepted = {"release", "retry", "merged-event", "same-tag"}
        skipped = {"dev", "unchanged", "unmerged", "failed-event", "pr-ci", "branch-ci",
                   "no-pr", "ci-failed", "wrong-sha", "missing-manifest"}
        rejected = {"invalid", "invalid-type", "bad-schema", "read-error", "off-main",
                    "package-mismatch", "gate-failed", "missing-artifact", "expired-artifact",
                    "retry-other-branch"}
        finish = "\n})().then(() => console.log(JSON.stringify({outputs}))).catch(error => console.log(JSON.stringify({error: error.message, outputs})));"
        for mode in sorted(accepted | skipped | rejected):
            with self.subTest(mode=mode):
                result = subprocess.run(
                    ["node", "-e", fixture + "\n(async () => {\n" + script + finish, mode],
                    capture_output=True, text=True, timeout=10, check=True,
                )
                response = json.loads(result.stdout)
                self.assertEqual("error" in response, mode in rejected, response)
                self.assertEqual(response["outputs"].get("ready") == "true", mode in accepted, response)
                if mode in accepted:
                    self.assertEqual(response["outputs"]["version"], "26.11.05.1")


if __name__ == "__main__":
    unittest.main()
