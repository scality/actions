# Retry Workflow if Failed

A GitHub Actions composite action that intelligently retries failed workflow runs on a specific branch.

## Overview

This action checks the last workflow run on the latest commit of a specified branch and automatically retries it if it failed. It supports configurable retry limits and retry modes (retry all jobs vs. retry only failed jobs).

## Features

- **Smart Retry Logic**: Only retries workflows that actually failed (failure, timed_out, or cancelled)
- **Configurable Retry Limits**: Set maximum number of retry attempts to prevent infinite loops
- **Flexible Retry Modes**: Choose between retrying all jobs or only failed jobs
- **Job/Step Filtering**: Optionally retry only if a specific job or step failed, ignoring other failures
- **Detailed Outputs**: Returns workflow status, retry count, and whether a retry was triggered
- **Commit-Specific**: Checks workflow runs only on the latest commit of the target branch
- **Step Summary**: Automatically generates a formatted summary in the GitHub Actions UI with workflow information and retry status

## Use Cases

- Automatically retry flaky tests
- Recover from transient infrastructure failures
- Implement retry logic for nightly or scheduled workflows
- Handle temporary service outages gracefully

## Usage

### Basic Example

```yaml
name: Retry Failed Workflow
on:
  workflow_dispatch:
  schedule:
    - cron: '0 8 * * *'  # Run daily at 8am

jobs:
  retry-failed:
    runs-on: ubuntu-latest
    steps:
      - uses: scality/actions/action-retry-workflow@main
        with:
          branch: 'main'
          workflow: 'ci.yaml'
          access_token: ${{ secrets.GITHUB_TOKEN }}
```

### Advanced Example

```yaml
name: Smart Workflow Retry
on:
  workflow_dispatch:
    inputs:
      branch:
        description: 'Branch to check'
        required: true
        default: 'main'
      workflow:
        description: 'Workflow name'
        required: true
      max-retries:
        description: 'Maximum retries'
        required: false
        default: '2'

jobs:
  retry-workflow:
    runs-on: ubuntu-latest
    steps:
      - name: Retry failed workflow
        id: retry
        uses: scality/actions/action-retry-workflow@main
        with:
          branch: ${{ github.event.inputs.branch }}
          workflow: ${{ github.event.inputs.workflow }}
          max-retries: ${{ github.event.inputs.max-retries }}
          retry-mode: 'failed-only'
          access_token: ${{ secrets.GH_PAT }}

      - name: Report results
        run: |
          echo "Workflow status: ${{ steps.retry.outputs.status }}"
          echo "Retry count: ${{ steps.retry.outputs.retry-count }}"
          echo "Was retried: ${{ steps.retry.outputs.was-retried }}"

      - name: Notify on retry
        if: steps.retry.outputs.was-retried == 'true'
        run: |
          echo "Workflow was retried!"
```

### Matrix Strategy Example

```yaml
name: Retry Multiple Workflows
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  retry-workflows:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        workflow:
          - 'ci.yaml'
          - 'integration-tests.yaml'
          - 'e2e-tests.yaml'
    steps:
      - uses: scality/actions/action-retry-workflow@main
        with:
          branch: 'development'
          workflow: ${{ matrix.workflow }}
          max-retries: '1'
          retry-mode: 'failed-only'
          access_token: ${{ secrets.GH_PAT }}
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `branch` | Branch name to check (checks workflow only on the last commit, defaults to repository default branch) | No | Repository default branch |
| `workflow` | Workflow name to check (e.g., "test.yaml" or workflow display name) | Yes | - |
| `max-retries` | Maximum number of retries allowed | No | `1` |
| `retry-mode` | Retry behavior: `all` (retry all jobs) or `failed-only` (retry only failed jobs) | No | `failed-only` |
| `job-name` | Only retry if this specific job failed (optional). Ignores failures in other jobs. | No | `''` |
| `step-name` | Only retry if this specific step failed (optional). If `job-name` also specified, looks for step in that job only. | No | `''` |
| `access_token` | GitHub token with workflow permissions (required for triggering retries) | Yes | - |

### Workflow Name Format

The `workflow` input accepts:
- **Workflow file name**: `ci.yaml`, `test.yaml`
- **Workflow display name**: `CI Pipeline`, `Test Suite`

The action will match against both the workflow's display name and file path.

### Retry Modes

- **`failed-only`** (recommended): Only retries jobs that failed, skipping successful jobs. This is faster and more cost-effective.
- **`all`**: Retries all jobs in the workflow, even those that succeeded.

### Job and Step Filtering

You can optionally filter retries to only trigger when a specific job or step fails. This is useful when you want to ignore certain types of failures.

**Filtering Behavior:**

1. **No filters** (default): Retries on any workflow failure
2. **`job-name` only**: Only retries if the specified job failed, ignores failures in other jobs
3. **`step-name` only**: Only retries if the specified step failed in any job
4. **Both `job-name` and `step-name`**: Only retries if the specified step failed in the specified job

**Example:**

```yaml
# Only retry if the "Integration Tests" job failed
- uses: scality/actions/action-retry-workflow@main
  with:
    branch: 'main'
    workflow: 'ci.yaml'
    job-name: 'Integration Tests'
    access_token: ${{ secrets.GH_PAT }}

# Only retry if the "Run E2E Tests" step failed (in any job)
- uses: scality/actions/action-retry-workflow@main
  with:
    branch: 'main'
    workflow: 'ci.yaml'
    step-name: 'Run E2E Tests'
    access_token: ${{ secrets.GH_PAT }}

# Only retry if "Deploy to Staging" step failed in "Deploy" job
- uses: scality/actions/action-retry-workflow@main
  with:
    branch: 'main'
    workflow: 'ci.yaml'
    job-name: 'Deploy'
    step-name: 'Deploy to Staging'
    access_token: ${{ secrets.GH_PAT }}
```

## Outputs

| Output | Description | Example Values |
|--------|-------------|----------------|
| `status` | Current status/conclusion of the workflow | `success`, `failure`, `cancelled`, `timed_out`, `not_found` |
| `retry-count` | Number of retries performed | `0`, `1`, `2` |
| `was-retried` | Whether the workflow was retried by this action | `true`, `false` |

## Step Summary

The action automatically generates a formatted summary in the GitHub Actions UI (`GITHUB_STEP_SUMMARY`) that includes:

- **Workflow Information**: Workflow name, branch, status, and run ID (with clickable link)
- **Retry Information**: Visual indicators, retry count, max retries, retry mode, and whether a retry was triggered
- **Action Context**: Helpful messages based on the outcome (e.g., "The workflow has been retried", "Max retries reached", etc.)

### Example Summary Output

#### When Workflow is Retried
```
## 🔄 Workflow Retry Action Summary

### Workflow Information
- Workflow: `ci.yaml`
- Branch: `main`
- Status: ❌ Workflow failure
- Run ID: 12345

### Retry Information
🔄 Retry triggered (mode: `failed-only`, attempt 1/2)

| Setting | Value |
|---------|-------|
| Retry Count | 1 |
| Max Retries | 2 |
| Retry Mode | `failed-only` |
| Was Retried | ✅ Yes |

---
✅ Action taken: The workflow has been retried. Check the workflow run page for progress.
```

#### When Max Retries Reached
```
## ❌ Workflow Retry Action Summary

### Workflow Information
- Workflow: `test.yaml`
- Branch: `develop`
- Status: ❌ Workflow failure
- Run ID: 67890

### Retry Information
🛑 Max retries reached (2/2)

| Setting | Value |
|---------|-------|
| Retry Count | 2 |
| Max Retries | 2 |
| Retry Mode | `all` |
| Was Retried | ❌ No |

---
⚠️ Note: Maximum retries (2) have been reached. Manual intervention may be required.
```

## Authentication

This action requires a GitHub token with workflow permissions. The default `GITHUB_TOKEN` has limitations:

- ✅ **For public repositories**: `GITHUB_TOKEN` usually works
- ❌ **For triggering workflows**: May need a Personal Access Token (PAT) with `workflow` scope

### Using a Personal Access Token

1. Create a PAT with `repo` and `workflow` scopes
2. Add it as a repository secret (e.g., `GH_PAT`)
3. Use it in the action:

```yaml
- uses: scality/actions/action-retry-workflow@main
  with:
    branch: 'main'
    workflow: 'test.yaml'
    access_token: ${{ secrets.GH_PAT }}
```

## How It Works

1. **Fetch Latest Commit**: Gets the SHA of the latest commit on the specified branch
2. **Find Workflow Run**: Searches for workflow runs matching the workflow name on that commit
3. **Check Status**: Examines the workflow's conclusion (success, failure, etc.)
4. **Count Retries**: Determines how many times the workflow has already been retried
5. **Retry Logic**: If the workflow failed and hasn't exceeded max retries, triggers a retry
6. **Return Results**: Outputs the status, retry count, and whether a retry was performed

## Retry Behavior

The action will retry a workflow if:
- ✅ Workflow conclusion is `failure`, `timed_out`, or `cancelled`
- ✅ Current retry count is less than `max-retries`

The action will NOT retry if:
- ❌ Workflow succeeded or is still running
- ❌ Max retries already reached
- ❌ Workflow run not found

## Development

### Running Tests

This action includes both Python unit tests and JavaScript integration tests using mock-github.

#### Install Dependencies

```bash
cd action-retry-workflow

# Install Python dependencies (if not already installed)
pip3 install pytest pytest-cov

# Install Node.js dependencies
npm install
```

#### Python Unit Tests

Tests the core Python logic with comprehensive mocking:

```bash
# Run unit tests
python3 -m pytest test_retry_workflow.py -v

# Run with coverage
python3 -m pytest test_retry_workflow.py --cov=retry_workflow --cov-report=term-missing

# Or using npm
npm run test:unit
```

#### JavaScript Integration Tests

Tests the actual GitHub Action using @kie/mock-github framework:

```bash
# Run integration tests
npm run test:integration

# Or directly with jest
npx jest action.test.js -v
```

#### Run All Tests

```bash
# Run both Python and JavaScript tests
npm run test:all
```

### Testing Locally with Real GitHub API

```bash
# Set environment variables
export GITHUB_TOKEN="your-token"

# Test the script against a real repository
python3 retry_workflow.py \
  --branch "main" \
  --workflow "ci.yaml" \
  --max-retries 2 \
  --retry-mode "failed-only"
```

### Mock Testing with Custom GitHub CLI

For manual integration testing, you can use the included mock gh CLI:

```bash
# Add mock gh to PATH
export PATH="$(pwd):$PATH"

# Set mock environment variables
export MOCK_WORKFLOW_NAME="test.yaml"
export MOCK_WORKFLOW_STATUS="failure"
export MOCK_WORKFLOW_ID="12345"

# Run with mock
python3 retry_workflow.py \
  --branch "main" \
  --workflow "test.yaml"
```

### Validating Action Syntax

```bash
# Install actionlint
brew install actionlint

# Validate the action
actionlint action.yaml
```

## Limitations

- Only checks the latest commit on the specified branch
- Requires the workflow to have run at least once
- Cannot retry workflows that are currently running
- Requires appropriate GitHub token permissions

## Examples

### Retry Nightly Tests

```yaml
name: Retry Nightly Tests
on:
  schedule:
    - cron: '0 2 * * *'  # 2am daily

jobs:
  retry:
    runs-on: ubuntu-latest
    steps:
      - uses: scality/actions/action-retry-workflow@main
        with:
          branch: 'main'
          workflow: 'nightly-tests.yaml'
          max-retries: '2'
          retry-mode: 'failed-only'
          access_token: ${{ secrets.GH_PAT }}
```

### Conditional Retry Based on Status

```yaml
jobs:
  check-and-retry:
    runs-on: ubuntu-latest
    steps:
      - name: Check workflow status
        id: check
        uses: scality/actions/action-retry-workflow@main
        with:
          branch: 'develop'
          workflow: 'integration-tests.yaml'
          max-retries: '3'
          access_token: ${{ secrets.GH_PAT }}

      - name: Send notification if still failing
        if: |
          steps.check.outputs.status == 'failure' &&
          steps.check.outputs.retry-count >= '3'
        run: |
          echo "Workflow failed after 3 retries!"
          # Send notification to Slack, email, etc.
```

## Contributing

When making changes:

1. Update the Python script (`retry_workflow.py`)
2. Add/update unit tests (`test_retry_workflow.py`)
3. Run tests: `python3 -m pytest test_retry_workflow.py -v`
4. Update documentation in this README
5. Validate action syntax: `actionlint action.yaml`

## License

See the repository's main LICENSE file.

## Related Actions

- [action-crons](../action-crons/) - Trigger workflows on cron schedules
- [xcore/bump_version_pull_request](../xcore/bump_version_pull_request/) - Automate version bumping

## Support

For issues or questions, please open an issue in the repository.
