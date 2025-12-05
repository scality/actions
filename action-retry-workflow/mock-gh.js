#!/usr/bin/env node
/**
 * Mock GitHub CLI for testing retry_workflow.py
 *
 * This script simulates the `gh` CLI tool for integration testing.
 * It responds to common gh api commands used by the retry workflow action.
 *
 * Usage:
 *   Set PATH to include this script before the real gh CLI:
 *   export PATH=/path/to/action-retry-workflow:$PATH
 *   export MOCK_WORKFLOW_NAME="test.yaml"
 *   export MOCK_WORKFLOW_STATUS="failure"
 *   export MOCK_WORKFLOW_ID="12345"
 *
 * Environment Variables:
 *   MOCK_WORKFLOW_NAME   - Name of the workflow to simulate
 *   MOCK_WORKFLOW_STATUS - Status of the workflow (failure, success, etc.)
 *   MOCK_WORKFLOW_ID     - ID of the workflow run
 */

const fs = require('fs');
const path = require('path');

// Mock data storage file - stores workflow states between calls
const MOCK_DATA_FILE = path.join(__dirname, '.mock-gh-data.json');

/**
 * Load mock data from disk
 *
 * Returns:
 *   Object with commits, workflows, runs, and retryCount
 */
function loadMockData() {
    if (fs.existsSync(MOCK_DATA_FILE)) {
        return JSON.parse(fs.readFileSync(MOCK_DATA_FILE, 'utf8'));
    }
    // Initialize with empty data structure
    return {
        commits: {},      // Maps branch names to commit SHAs
        workflows: {},    // Stores workflow definitions
        runs: {},         // Maps run IDs to run objects
        retryCount: {}    // Tracks retry attempts per run ID
    };
}

/**
 * Save mock data to disk
 *
 * Args:
 *   data: Object to save
 */
function saveMockData(data) {
    fs.writeFileSync(MOCK_DATA_FILE, JSON.stringify(data, null, 2));
}

// Parse command line arguments (skip node and script path)
const args = process.argv.slice(2);

/**
 * Main command router - dispatches to appropriate handler
 *
 * Args:
 *   args: Command line arguments
 */
function handleCommand(args) {
    const data = loadMockData();

    // Route based on first argument
    if (args[0] === 'api') {
        return handleApiCommand(args.slice(1), data);
    }

    console.error(`Unknown command: ${args[0]}`);
    process.exit(1);
}

/**
 * Handle 'gh api' commands
 *
 * Parses arguments to extract endpoint, method, jq filter, and query params
 *
 * Args:
 *   args: Command arguments after 'api'
 *   data: Mock data object
 */
function handleApiCommand(args, data) {
    let endpoint = '';
    let method = 'GET';
    let jqFilter = null;
    let queryParams = {};

    // Parse all arguments
    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--method') {
            method = args[++i];
        } else if (args[i] === '--jq') {
            jqFilter = args[++i];
        } else if (args[i] === '-f') {
            // Parse key=value format
            const param = args[++i];
            const [key, value] = param.split('=');
            queryParams[key] = value;
        } else if (args[i] === '--paginate') {
            // Pagination flag - ignored in mock
        } else if (!endpoint) {
            endpoint = args[i];
        }
    }

    // Route to specific endpoint handler based on URL pattern
    if (endpoint.includes('/commits/')) {
        return handleCommitEndpoint(endpoint, data, jqFilter);
    } else if (endpoint.includes('/actions/runs') && !endpoint.match(/\/\d+/)) {
        return handleWorkflowRunsEndpoint(endpoint, data, jqFilter, queryParams);
    } else if (endpoint.match(/\/actions\/runs\/(\d+)$/)) {
        return handleWorkflowRunEndpoint(endpoint, data, jqFilter, method);
    } else if (endpoint.includes('/rerun')) {
        return handleRetryEndpoint(endpoint, data, method);
    }

    console.error(`Unknown API endpoint: ${endpoint}`);
    process.exit(1);
}

/**
 * Handle commit endpoint: GET /repos/{owner}/{repo}/commits/{branch}
 *
 * Returns commit information for a given branch
 *
 * Args:
 *   endpoint: API endpoint URL
 *   data: Mock data object
 *   jqFilter: Optional jq filter to apply to output
 */
function handleCommitEndpoint(endpoint, data, jqFilter) {
    // Extract branch from endpoint like repos/{owner}/{repo}/commits/main
    const match = endpoint.match(/\/commits\/(.+)$/);
    if (!match) {
        console.error('Invalid commit endpoint');
        process.exit(1);
    }

    const branch = match[1];
    // Return stored SHA or default test SHA
    const commitSha = data.commits[branch] || 'abc123def456';

    // Apply jq filter if specified
    if (jqFilter === '.sha') {
        console.log(commitSha);
        return;
    }

    // Return full commit object
    console.log(JSON.stringify({
        sha: commitSha,
        commit: {
            message: 'Test commit'
        }
    }));
}

/**
 * Handle workflow runs list endpoint: GET /repos/{owner}/{repo}/actions/runs
 *
 * Returns list of workflow runs filtered by branch and commit SHA
 *
 * Args:
 *   endpoint: API endpoint URL
 *   data: Mock data object
 *   jqFilter: Optional jq filter to apply to output
 *   queryParams: Query parameters (branch, head_sha, etc.)
 */
function handleWorkflowRunsEndpoint(endpoint, data, jqFilter, queryParams) {
    const branch = queryParams.branch || 'main';
    const headSha = queryParams.head_sha;

    // Get workflow configuration from environment or use defaults
    const workflowName = process.env.MOCK_WORKFLOW_NAME || 'test.yaml';
    const workflowStatus = process.env.MOCK_WORKFLOW_STATUS || 'failure';
    const workflowId = parseInt(process.env.MOCK_WORKFLOW_ID || '12345');

    // Create workflow run if it doesn't exist
    if (!data.runs[workflowId]) {
        data.runs[workflowId] = {
            id: workflowId,
            name: workflowName.replace('.yaml', '').replace('.yml', ''),
            path: `.github/workflows/${workflowName}`,
            head_sha: headSha,
            conclusion: workflowStatus,
            created_at: new Date().toISOString(),
            run_attempt: 1
        };
        saveMockData(data);
    }

    const run = data.runs[workflowId];

    // Apply jq filter - returns raw JSON object per line
    if (jqFilter === '.workflow_runs[]') {
        console.log(JSON.stringify(run));
        return;
    }

    // Return full response with array wrapper
    console.log(JSON.stringify({
        workflow_runs: [run]
    }));
}

/**
 * Handle single workflow run endpoint: GET /repos/{owner}/{repo}/actions/runs/{run_id}
 *
 * Returns details about a specific workflow run
 *
 * Args:
 *   endpoint: API endpoint URL
 *   data: Mock data object
 *   jqFilter: Optional jq filter to apply to output
 *   method: HTTP method (GET, POST, etc.)
 */
function handleWorkflowRunEndpoint(endpoint, data, jqFilter, method) {
    // Extract run ID from endpoint
    const match = endpoint.match(/\/actions\/runs\/(\d+)$/);
    if (!match) {
        console.error('Invalid workflow run endpoint');
        process.exit(1);
    }

    const runId = parseInt(match[1]);

    // Get or create run object
    const run = data.runs[runId] || {
        id: runId,
        run_attempt: data.retryCount[runId] ? data.retryCount[runId] + 1 : 1
    };

    // Apply jq filter - extract run_attempt field
    if (jqFilter === '.run_attempt') {
        console.log(run.run_attempt);
        return;
    }

    // Return full run object
    console.log(JSON.stringify(run));
}

/**
 * Handle retry endpoint: POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun[-failed-jobs]
 *
 * Simulates retrying a workflow run by incrementing retry counter
 *
 * Args:
 *   endpoint: API endpoint URL
 *   data: Mock data object
 *   method: HTTP method (must be POST)
 */
function handleRetryEndpoint(endpoint, data, method) {
    // Verify POST method
    if (method !== 'POST') {
        console.error('Retry endpoint requires POST method');
        process.exit(1);
    }

    // Extract run ID from endpoint (works for both /rerun and /rerun-failed-jobs)
    const match = endpoint.match(/\/actions\/runs\/(\d+)\/rerun/);
    if (!match) {
        console.error('Invalid retry endpoint');
        process.exit(1);
    }

    const runId = parseInt(match[1]);

    // Increment retry count for this run
    if (!data.retryCount[runId]) {
        data.retryCount[runId] = 1;
    } else {
        data.retryCount[runId]++;
    }

    // Update the run_attempt in the run object
    if (data.runs[runId]) {
        data.runs[runId].run_attempt = data.retryCount[runId] + 1;
    }

    // Persist changes
    saveMockData(data);

    // Return empty success response (matching real GitHub API)
    console.log('{}');
}

// Execute main command handler
try {
    handleCommand(args);
} catch (error) {
    console.error(`Mock gh error: ${error.message}`);
    process.exit(1);
}
