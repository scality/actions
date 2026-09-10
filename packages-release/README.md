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
