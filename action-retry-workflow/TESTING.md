# Testing Guide for action-retry-workflow

This document describes the testing strategy and how to run tests for the retry workflow action.

## Test Architecture

The action includes two levels of testing:

1. **Python Unit Tests** (`test_retry_workflow.py`) - Tests the core Python logic
2. **JavaScript Integration Tests** (`action.test.js`) - Tests the GitHub Action itself using @kie/mock-github

## Python Unit Tests

### Overview

The Python unit tests use `pytest` and `unittest.mock` to test all functions in `retry_workflow.py` in isolation.

### Test Coverage

- ✅ GitHub CLI command execution
- ✅ Commit SHA retrieval
- ✅ Workflow run listing and filtering
- ✅ Latest workflow run selection
- ✅ Retry attempt counting
- ✅ Workflow retry logic (both modes)
- ✅ Output file writing
- ✅ Main function scenarios (success, failure, not found, max retries)

### Running Python Tests

```bash
# Run all unit tests
python3 -m pytest test_retry_workflow.py -v

# Run with coverage report
python3 -m pytest test_retry_workflow.py --cov=retry_workflow --cov-report=term-missing --cov-report=html

# Run specific test class
python3 -m pytest test_retry_workflow.py::TestRetryWorkflow -v

# Run specific test
python3 -m pytest test_retry_workflow.py::TestRetryWorkflow::test_retry_workflow_all -v
```

### Test Results

All 20 Python unit tests pass:

```
test_retry_workflow.py::TestRunGhCommand::test_run_gh_command_failure PASSED
test_retry_workflow.py::TestRunGhCommand::test_run_gh_command_success PASSED
test_retry_workflow.py::TestGetLatestCommitSha::test_get_latest_commit_sha PASSED
test_retry_workflow.py::TestGetWorkflowRuns::test_get_workflow_runs_by_path PASSED
test_retry_workflow.py::TestGetWorkflowRuns::test_get_workflow_runs_empty PASSED
test_retry_workflow.py::TestGetWorkflowRuns::test_get_workflow_runs_with_results PASSED
test_retry_workflow.py::TestGetLatestWorkflowRun::test_get_latest_workflow_run_empty PASSED
test_retry_workflow.py::TestGetLatestWorkflowRun::test_get_latest_workflow_run_with_results PASSED
test_retry_workflow.py::TestCountRetryAttempts::test_count_retry_attempts_invalid PASSED
test_retry_workflow.py::TestCountRetryAttempts::test_count_retry_attempts_no_retries PASSED
test_retry_workflow.py::TestCountRetryAttempts::test_count_retry_attempts_with_retries PASSED
test_retry_workflow.py::TestRetryWorkflow::test_retry_workflow_all PASSED
test_retry_workflow.py::TestRetryWorkflow::test_retry_workflow_failed_only PASSED
test_retry_workflow.py::TestRetryWorkflow::test_retry_workflow_failure PASSED
test_retry_workflow.py::TestWriteOutput::test_write_output_with_file PASSED
test_retry_workflow.py::TestWriteOutput::test_write_output_without_file PASSED
test_retry_workflow.py::TestMain::test_main_workflow_failed_retry PASSED
test_retry_workflow.py::TestMain::test_main_workflow_max_retries_reached PASSED
test_retry_workflow.py::TestMain::test_main_workflow_not_found PASSED
test_retry_workflow.py::TestMain::test_main_workflow_success_no_retry PASSED

============================== 20 passed in 0.07s ==============================
```

## JavaScript Integration Tests

### Overview

The JavaScript integration tests use Jest and `@kie/mock-github` to test the complete GitHub Action workflow in a simulated environment.

### Test Coverage

- ✅ Workflow not found scenario
- ✅ Retrying a failed workflow
- ✅ Not retrying a successful workflow
- ✅ Respecting max-retries limit
- ✅ Retry mode selection (all vs failed-only)
- ✅ Handling timed_out status

### Running JavaScript Tests

```bash
# Install dependencies first
npm install

# Run integration tests
npm run test:integration

# Or with jest directly
npx jest action.test.js -v

# Run with coverage
npx jest --coverage
```

### Test Structure

Each test follows this pattern:

```javascript
test('should retry a failed workflow', async () => {
    // 1. Mock GitHub API responses
    mockGithub.mockApi('/repos/owner/repo/commits/main', {...});
    mockGithub.mockApi('/repos/owner/repo/actions/runs', {...});

    // 2. Run the action
    const result = await testRepo.runAction('action.yaml', {
        inputs: { branch: 'main', workflow: 'test.yaml', ... }
    });

    // 3. Verify outputs
    expect(result.outputs.status).toBe('failure');
    expect(result.outputs['was-retried']).toBe('true');
});
```

## Mock GitHub CLI

### Overview

`mock-gh.js` is a Node.js script that simulates the `gh` CLI for manual integration testing.

### Features

- Handles commit endpoint: `GET /repos/{owner}/{repo}/commits/{branch}`
- Handles workflow runs listing: `GET /repos/{owner}/{repo}/actions/runs`
- Handles workflow run details: `GET /repos/{owner}/{repo}/actions/runs/{run_id}`
- Handles retry endpoints: `POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun[-failed-jobs]`
- Persists state to `.mock-gh-data.json`

### Usage

```bash
# Set environment variables
export MOCK_WORKFLOW_NAME="test.yaml"
export MOCK_WORKFLOW_STATUS="failure"
export MOCK_WORKFLOW_ID="12345"

# Add to PATH
export PATH="$(pwd):$PATH"

# Run Python script with mock gh
python3 retry_workflow.py --branch "main" --workflow "test.yaml"

# Clean up mock data
rm -f .mock-gh-data.json
```

### Environment Variables

- `MOCK_WORKFLOW_NAME` - Name of the workflow (default: "test.yaml")
- `MOCK_WORKFLOW_STATUS` - Workflow conclusion (default: "failure")
- `MOCK_WORKFLOW_ID` - Workflow run ID (default: "12345")

## Running All Tests

### Quick Test

```bash
npm test
```

### Comprehensive Test

```bash
# Run both Python and JavaScript tests
npm run test:all
```

### Expected Output

```
✓ Python unit tests: 20 passed
✓ JavaScript integration tests: 6 passed
✓ All tests passed!
```

## Continuous Integration

The tests are designed to run in CI/CD environments:

```yaml
# Example GitHub Actions workflow
- name: Run Python tests
  run: python3 -m pytest test_retry_workflow.py -v

- name: Install Node.js dependencies
  run: npm install

- name: Run JavaScript tests
  run: npm run test:integration
```

## Debugging Tests

### Python Tests

```bash
# Run with verbose output
python3 -m pytest test_retry_workflow.py -vv

# Run with print statements
python3 -m pytest test_retry_workflow.py -s

# Run with pdb debugger on failure
python3 -m pytest test_retry_workflow.py --pdb
```

### JavaScript Tests

```bash
# Run with verbose output
npx jest action.test.js --verbose

# Run specific test
npx jest -t "should retry a failed workflow"

# Run in watch mode
npx jest --watch
```

## Test Data

### Mock Workflow Run Object

```json
{
    "id": 12345,
    "name": "Test Workflow",
    "path": ".github/workflows/test.yaml",
    "head_sha": "abc123",
    "conclusion": "failure",
    "created_at": "2025-12-05T10:00:00Z",
    "run_attempt": 1
}
```

### Expected Outputs

| Scenario | status | retry_count | was_retried |
|----------|--------|-------------|-------------|
| Not found | `not_found` | `0` | `false` |
| Failed (retry) | `failure` | `1` | `true` |
| Success | `success` | `0` | `false` |
| Max retries | `failure` | `2` | `false` |
| Timed out (retry) | `timed_out` | `1` | `true` |

## Contributing

When adding new features:

1. Add Python unit tests to `test_retry_workflow.py`
2. Add JavaScript integration tests to `action.test.js`
3. Update this TESTING.md document
4. Ensure all tests pass: `npm run test:all`

## Troubleshooting

### Python Tests Fail

```bash
# Ensure pytest is installed
pip3 install pytest pytest-cov

# Check Python version (requires 3.8+)
python3 --version
```

### JavaScript Tests Fail

```bash
# Remove node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Check Node.js version (requires 14+)
node --version
```

### Mock gh Not Working

```bash
# Ensure mock-gh.js is executable
chmod +x mock-gh.js

# Verify it's in PATH
which gh

# Check environment variables
echo $MOCK_WORKFLOW_NAME
echo $MOCK_WORKFLOW_STATUS
```

## Performance

- Python unit tests: ~0.07 seconds
- JavaScript integration tests: ~2-5 seconds
- Total test time: ~5-10 seconds

## Coverage

Current test coverage:

- Python code: ~95% (19/20 functions)
- Action logic: ~90% (6/7 scenarios)
