# arti-compute

Composite action that runs `arti_compute.py` to resolve RING / S3 / ADI installer
URLs and versions for installer-test workflows.

Snapshot of the RING script from [RING-54589](https://scality.atlassian.net/browse/RING-54589).
RING still owns the canonical copy until workflows cut over to this action.

## Usage

```yaml
- uses: scality/actions/arti-compute@main
  with:
    os: rocky9
    ring-artifact: ${{ needs.get-artifacts-name.outputs.artifacts-name }}
    auth: ${{ secrets.ARTIFACTS_USER }}:${{ secrets.ARTIFACTS_PASSWORD }}
    job-type: install upgrade
    normalize: 'true'
    debug: 'true'
    output-file: /tmp/installer-tests-vars
    github-token: ${{ secrets.GIT_ACCESS_TOKEN }}
    version-file: VERSION
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

Then `source` the output file as today:

```yaml
- run: source /tmp/installer-tests-vars
```

### Tech-train check only

```yaml
- uses: scality/actions/arti-compute@main
  with:
    check-tech-train: '10.1.0.0'
    version-file: VERSION
```

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `os` | yes\* | OS name (`rhel8`, `rocky9`, `scalityos`, …) |
| `ring-artifact` | yes\* | RING artifact build id |
| `auth` | yes\* | `user:password` for artifacts.scality.net |
| `job-type` | no | Space-separated: `install`, `upgrade`, `upgradeprev`, `sbom` |
| `s3-artifact` | no | S3 / Federation artifact override |
| `adi-artifact` | no | ADI artifact (scalityos) |
| `adi-branch` | no | ADI git ref for manifests |
| `adi-upgrade-from` | no | ADI upgrade-from version |
| `upgrade-from` | no | RING upgrade-from version |
| `ring-architecture` | no | Architecture string (must match script `ARCHITECTURE`) |
| `ring-explicit` | no | `true` if RING artifact was explicit |
| `normalize` | no | Normalize upgradeprev → upgrade vars |
| `no-snapshots` | no | Disable snapshot lookup |
| `debug` / `quiet` / `online` | no | Logging / offline mode flags |
| `suffix` / `region` | no | Snapshot suffix / AWS region |
| `check-tech-train` | no | Validate `TECH_TRAIN` only (skips artifact inputs) |
| `output-file` | no | Write bash vars here (else stdout) |
| `github-token` | no | For ADI GitHub API |
| `version-file` | no | Path to RING `VERSION` |
| `python-version` | no | Default `3.12` |

\* Required unless `check-tech-train` is set.

## Environment

| Variable | Role |
|----------|------|
| `GITHUB_TOKEN` | Set from `github-token` for ADI manifests |
| `RING_VERSION_FILE` | Set from `version-file` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Snapshot AMI lookup (job env) |
| `GITHUB_WORKSPACE` | Fallback for `VERSION` when `version-file` is omitted |

## Caller requirements

1. Check out the RING repository (or pass `version-file`).
2. For upgrade path resolution that uses `_is_released_GA`, git tags must be available in the RING checkout (`fetch-depth: 0` if needed).
3. AWS credentials on the job when snapshots are enabled.

## Maintenance

Until RING cutover, refresh `arti_compute.py` from
`ring/.github/scripts/installer-tests/arti_compute.py` before adopting this
action in RING workflows. Keep `TECH_TRAIN` updates in this copy once it becomes
the source of truth.
