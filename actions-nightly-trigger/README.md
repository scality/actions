# Smart Nightly Trigger Action

Intelligently decides whether to trigger nightly workflows based on commits and schedule to reduce CI/CD costs.

## Usage

### Basic Example

```yaml
steps:
  - uses: scality/actions/actions-nightly-trigger@main
    with:
      branch: "development/4"
      workflow: "nightly.yaml"
      access_token: ${{ secrets.GIT_ACCESS_TOKEN }}
```

### Federation Repository Example

```yaml
name: 'Start cron jobs'

on:
  schedule:
    - cron: '24 1 * * *'  # Daily at 01:24

jobs:
  crons:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        jobs:
          - name: 'development 7.10.x SupSetup'
            cron: '24 1 * * *'
            branch: 'development/7.10'
            workflows: 'build-tests.yaml'

    steps:
      - name: 'Smart trigger for ${{ matrix.jobs.name }}'
        uses: scality/actions/actions-nightly-trigger@<commit-hash>
        with:
          branch: ${{ matrix.jobs.branch }}
          workflow: ${{ matrix.jobs.workflows }}
          access_token: ${{ secrets.GIT_ACCESS_TOKEN }}
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `branch` | Branch to check and trigger workflow for | No | Repository default branch |
| `workflow` | Workflow file to trigger | Yes | `nightly.yaml` |
| `access_token` | GitHub token with workflow permissions | Yes | - |

## Triggering Logic

1. If last commit in last 24 hours → Trigger
2. If last run was 7, 14, 21... days ago → Trigger (weekly check)
3. Otherwise → Skip
