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
| `run-workflow` | Whether to actually run the workflow or only make decision | No | `true` |

## Outputs

| Output | Description |
|--------|-------------|
| `trigger` | Whether the workflow should be triggered (`true`/`false`) |
| `reason` | Reason for the trigger decision |
| `last_commit_time` | Timestamp of the last commit |
| `days_since_last_run` | Days since last workflow run |

## Triggering Logic

1. If last commit in last 24 hours → Trigger
2. If last run was 7, 14, 21... days ago → Trigger (weekly check)
3. Otherwise → Skip

## Testing Mode

You can use `run-workflow: false` to test the decision logic without actually triggering workflows:

```yaml
- name: Test decision logic
  id: decision
  uses: scality/actions/actions-nightly-trigger@main
  with:
    branch: main
    workflow: nightly.yaml
    access_token: ${{ secrets.GITHUB_TOKEN }}
    run-workflow: false

- name: Check decision
  run: |
    echo "Should trigger: ${{ steps.decision.outputs.trigger }}"
    echo "Reason: ${{ steps.decision.outputs.reason }}"
```
