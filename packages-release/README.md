# packages-release

Composite action encapsulating the v2.1 S3 Packages release model (upload,
promotion, visibility flip). Release repos call it from their own workflow
instead of importing ten separate POC workflows.

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `action` | ✅ | — | `upload` \| `promote` \| `publish` |
| `version` | ✅ | — | Release version string (e.g. `9.5.0.3`) |
| `build_id` | | packed digits | Staging prefix locator |
| `artifacts_path` | upload only | — | Local directory with built artifacts |
| `target_stage` | promote only | — | `PW` \| `RC` \| `GA` |
| `publish_action` | publish only | `publish` | `publish` or `unpublish` |
| `publish_reason` | | — | Audited free-text reason |
| `gcp_workload_identity_provider` | ✅ | — | WIF provider URL |
| `gcp_service_account` | ✅ | — | GCS service account email |
| `bucket_staging` | upload + PW promote | — | Staging bucket name |
| `bucket_packages` | ✅ | — | Packages bucket name |
| `retention_pw` | | — | PW retention window (`2d`/`1w`/`6m`). **Unlocked** — clearable, so un-promote keeps working |
| `retention_rc` | | — | RC retention window. Unlocked, like PW |
| `retention_ga` | | — | GA retention window, written **Locked**. Empty falls back to a temporary hold |

## Example — RING release workflow

```yaml
# .github/workflows/release.yaml  (in the RING repo)
on:
  workflow_dispatch:
    inputs:
      version: { required: true, type: string }
      target_stage:
        type: choice
        options: [PW, RC, GA]
        required: true

permissions:
  contents: read
  id-token: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - name: Download artifacts from build system
        # team-specific step — curl from artifacts.scality.net, etc.
        run: |
          mkdir artifacts
          # ... fetch real installers here ...

      - name: Upload to staging
        if: inputs.target_stage == 'PW'
        uses: scality/actions/packages-release@main
        with:
          action: upload
          version: ${{ inputs.version }}
          artifacts_path: artifacts
          gcp_workload_identity_provider: ${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          gcp_service_account: ${{ vars.GCP_SERVICE_ACCOUNT }}
          bucket_staging: ${{ vars.GCS_BUCKET_STAGING }}
          bucket_packages: ${{ vars.GCS_BUCKET_PACKAGES }}

      - name: Promote
        uses: scality/actions/packages-release@main
        with:
          action: promote
          version: ${{ inputs.version }}
          target_stage: ${{ inputs.target_stage }}
          gcp_workload_identity_provider: ${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          gcp_service_account: ${{ vars.GCP_SERVICE_ACCOUNT }}
          bucket_staging: ${{ vars.GCS_BUCKET_STAGING }}
          bucket_packages: ${{ vars.GCS_BUCKET_PACKAGES }}

      - name: Publish (GA only)
        if: inputs.target_stage == 'GA'
        uses: scality/actions/packages-release@main
        with:
          action: publish
          version: ${{ inputs.version }}
          publish_reason: "GA release ${{ inputs.version }}"
          gcp_workload_identity_provider: ${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          gcp_service_account: ${{ vars.GCP_SERVICE_ACCOUNT }}
          bucket_packages: ${{ vars.GCS_BUCKET_PACKAGES }}
```

## Lifecycle recap

```
poc-upload  ──→  action=upload             (bytes land in staging)
poc-release ──→  action=promote PW         (one server-side copy, manifest created)
poc-release ──→  action=promote RC         (metadata flip, zero bytes copied)
poc-release ──→  action=promote GA         (metadata flip + temporary hold)
poc-publish ──→  action=publish            (visibility → external)
```

Operational workflows (verify, housekeeping, lock, index) remain in the
`S3-Packages-POC-IT` repo — they are not release-pipeline concerns.

## Retention (B3)

Per-object retention is what makes a release tamper-resistant rather than merely
hard to delete by accident.

| Stage | Mode | Why |
|---|---|---|
| PW, RC | `Unlocked` | clearable with an explicit override, so un-promote can still remove the copy |
| GA | **`Locked`** | cannot be shortened or cleared by anyone — not the bucket owner, not the project owner, not after it expires |

Two properties worth knowing before choosing a window:

- **A locked retain-until can only ever be increased.** Start short and extend;
  a long window forecloses every correction, and expiry does not relax it — it
  only makes the object deletable.
- **Extending needs no special permission**, so whatever job re-stamps these
  dates can hold that capability alone and be structurally unable to weaken a
  lock. Something has to re-stamp before expiry, or the protection simply lapses.

GA's retention is written **before** the stage flips to GA, not after. A failure
between the two then leaves an object protected but still labelled RC —
under-claimed, and fixed by re-running, which is safe because the retain-until
can only go up. The reverse order leaves an object labelled GA and protected by
nothing, which every listing reports as correct.

With `retention_ga` empty the action falls back to a temporary hold. That guards
against accident, not against a compromised credential: a hold can be lifted by
whoever holds the permission.

## Re-running is safe

`action=upload` compares the `sha256` of each file against what is already in
staging. Identical content is skipped; **different content under the same version
is refused**, not overwritten.

That is deliberate on two counts. Overwriting in GCS is a delete plus a create,
so it needs `storage.objects.delete` — which a least-privilege deployer does not
have and should not. And publishing different bytes under a version that already
exists is not something the release model supports: ship a new version.
