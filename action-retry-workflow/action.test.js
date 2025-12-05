/**
 * Integration tests for action-retry-workflow using @kie/mock-github
 *
 * These tests verify that the GitHub Action works correctly by:
 * 1. Mocking GitHub API responses
 * 2. Running the action in a simulated environment
 * 3. Verifying outputs and behavior
 */

const { MockGithub } = require('@kie/mock-github');
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

describe('action-retry-workflow', () => {
    let mockGithub;
    let testRepo;

    beforeEach(async () => {
        // Create mock GitHub instance
        mockGithub = new MockGithub({
            repo: {
                'test-owner/test-repo': {
                    files: [
                        {
                            src: path.join(__dirname, 'action.yaml'),
                            dest: '.github/actions/retry-workflow/action.yaml'
                        },
                        {
                            src: path.join(__dirname, 'retry_workflow.py'),
                            dest: '.github/actions/retry-workflow/retry_workflow.py'
                        }
                    ]
                }
            }
        });

        testRepo = await mockGithub.setup();
    });

    afterEach(async () => {
        await mockGithub.teardown();
    });

    /**
     * Test that action handles workflow not found scenario
     */
    test('should handle workflow not found', async () => {
        // Mock GitHub API to return no workflows
        mockGithub.mockApi('/repos/test-owner/test-repo/commits/main', {
            sha: 'abc123def456'
        });

        mockGithub.mockApi('/repos/test-owner/test-repo/actions/runs', {
            workflow_runs: []
        });

        // Run the action
        const result = await testRepo.runAction('.github/actions/retry-workflow/action.yaml', {
            inputs: {
                branch: 'main',
                workflow: 'nonexistent.yaml',
                'max-retries': '1',
                'retry-mode': 'failed-only',
                'access_token': 'mock-token'
            }
        });

        // Verify outputs
        expect(result.outputs.status).toBe('not_found');
        expect(result.outputs['retry-count']).toBe('0');
        expect(result.outputs['was-retried']).toBe('false');
    });

    /**
     * Test that action retries a failed workflow
     */
    test('should retry a failed workflow', async () => {
        const runId = 12345;

        // Mock GitHub API responses
        mockGithub.mockApi('/repos/test-owner/test-repo/commits/main', {
            sha: 'abc123'
        });

        mockGithub.mockApi('/repos/test-owner/test-repo/actions/runs', {
            workflow_runs: [
                {
                    id: runId,
                    name: 'Test Workflow',
                    path: '.github/workflows/test.yaml',
                    head_sha: 'abc123',
                    conclusion: 'failure',
                    created_at: new Date().toISOString(),
                    run_attempt: 1
                }
            ]
        });

        mockGithub.mockApi(`/repos/test-owner/test-repo/actions/runs/${runId}`, {
            id: runId,
            run_attempt: 1
        });

        // Mock the retry endpoint
        let retryWasCalled = false;
        mockGithub.mockApi(
            `/repos/test-owner/test-repo/actions/runs/${runId}/rerun-failed-jobs`,
            (req) => {
                retryWasCalled = true;
                return {};
            },
            { method: 'POST' }
        );

        // Run the action
        const result = await testRepo.runAction('.github/actions/retry-workflow/action.yaml', {
            inputs: {
                branch: 'main',
                workflow: 'Test Workflow',
                'max-retries': '2',
                'retry-mode': 'failed-only',
                'access_token': 'mock-token'
            }
        });

        // Verify outputs
        expect(result.outputs.status).toBe('failure');
        expect(result.outputs['was-retried']).toBe('true');
        expect(retryWasCalled).toBe(true);
    });

    /**
     * Test that action does not retry a successful workflow
     */
    test('should not retry a successful workflow', async () => {
        const runId = 12346;

        // Mock GitHub API responses
        mockGithub.mockApi('/repos/test-owner/test-repo/commits/main', {
            sha: 'abc123'
        });

        mockGithub.mockApi('/repos/test-owner/test-repo/actions/runs', {
            workflow_runs: [
                {
                    id: runId,
                    name: 'Test Workflow',
                    path: '.github/workflows/test.yaml',
                    head_sha: 'abc123',
                    conclusion: 'success',
                    created_at: new Date().toISOString(),
                    run_attempt: 1
                }
            ]
        });

        mockGithub.mockApi(`/repos/test-owner/test-repo/actions/runs/${runId}`, {
            id: runId,
            run_attempt: 1
        });

        // Track if retry was called (it shouldn't be)
        let retryWasCalled = false;
        mockGithub.mockApi(
            `/repos/test-owner/test-repo/actions/runs/${runId}/rerun-failed-jobs`,
            () => {
                retryWasCalled = true;
                return {};
            },
            { method: 'POST' }
        );

        // Run the action
        const result = await testRepo.runAction('.github/actions/retry-workflow/action.yaml', {
            inputs: {
                branch: 'main',
                workflow: 'Test Workflow',
                'max-retries': '1',
                'retry-mode': 'failed-only',
                'access_token': 'mock-token'
            }
        });

        // Verify outputs
        expect(result.outputs.status).toBe('success');
        expect(result.outputs['retry-count']).toBe('0');
        expect(result.outputs['was-retried']).toBe('false');
        expect(retryWasCalled).toBe(false);
    });

    /**
     * Test that action respects max-retries limit
     */
    test('should respect max-retries limit', async () => {
        const runId = 12347;

        // Mock GitHub API responses
        mockGithub.mockApi('/repos/test-owner/test-repo/commits/main', {
            sha: 'abc123'
        });

        mockGithub.mockApi('/repos/test-owner/test-repo/actions/runs', {
            workflow_runs: [
                {
                    id: runId,
                    name: 'Test Workflow',
                    path: '.github/workflows/test.yaml',
                    head_sha: 'abc123',
                    conclusion: 'failure',
                    created_at: new Date().toISOString(),
                    run_attempt: 3  // Already retried twice
                }
            ]
        });

        mockGithub.mockApi(`/repos/test-owner/test-repo/actions/runs/${runId}`, {
            id: runId,
            run_attempt: 3
        });

        // Track if retry was called (it shouldn't be)
        let retryWasCalled = false;
        mockGithub.mockApi(
            `/repos/test-owner/test-repo/actions/runs/${runId}/rerun-failed-jobs`,
            () => {
                retryWasCalled = true;
                return {};
            },
            { method: 'POST' }
        );

        // Run the action with max-retries of 2
        const result = await testRepo.runAction('.github/actions/retry-workflow/action.yaml', {
            inputs: {
                branch: 'main',
                workflow: 'Test Workflow',
                'max-retries': '2',
                'retry-mode': 'failed-only',
                'access_token': 'mock-token'
            }
        });

        // Verify outputs - should not retry because already at max
        expect(result.outputs.status).toBe('failure');
        expect(result.outputs['retry-count']).toBe('2');
        expect(result.outputs['was-retried']).toBe('false');
        expect(retryWasCalled).toBe(false);
    });

    /**
     * Test retry mode "all" vs "failed-only"
     */
    test('should use correct retry endpoint for "all" mode', async () => {
        const runId = 12348;

        // Mock GitHub API responses
        mockGithub.mockApi('/repos/test-owner/test-repo/commits/main', {
            sha: 'abc123'
        });

        mockGithub.mockApi('/repos/test-owner/test-repo/actions/runs', {
            workflow_runs: [
                {
                    id: runId,
                    name: 'Test Workflow',
                    path: '.github/workflows/test.yaml',
                    head_sha: 'abc123',
                    conclusion: 'failure',
                    created_at: new Date().toISOString(),
                    run_attempt: 1
                }
            ]
        });

        mockGithub.mockApi(`/repos/test-owner/test-repo/actions/runs/${runId}`, {
            id: runId,
            run_attempt: 1
        });

        // Mock the "all" retry endpoint
        let correctEndpointCalled = false;
        mockGithub.mockApi(
            `/repos/test-owner/test-repo/actions/runs/${runId}/rerun`,
            () => {
                correctEndpointCalled = true;
                return {};
            },
            { method: 'POST' }
        );

        // Run the action with retry-mode "all"
        const result = await testRepo.runAction('.github/actions/retry-workflow/action.yaml', {
            inputs: {
                branch: 'main',
                workflow: 'Test Workflow',
                'max-retries': '1',
                'retry-mode': 'all',
                'access_token': 'mock-token'
            }
        });

        // Verify correct endpoint was called
        expect(result.outputs['was-retried']).toBe('true');
        expect(correctEndpointCalled).toBe(true);
    });

    /**
     * Test handling of timed_out status
     */
    test('should retry timed_out workflows', async () => {
        const runId = 12349;

        // Mock GitHub API responses
        mockGithub.mockApi('/repos/test-owner/test-repo/commits/main', {
            sha: 'abc123'
        });

        mockGithub.mockApi('/repos/test-owner/test-repo/actions/runs', {
            workflow_runs: [
                {
                    id: runId,
                    name: 'Test Workflow',
                    path: '.github/workflows/test.yaml',
                    head_sha: 'abc123',
                    conclusion: 'timed_out',
                    created_at: new Date().toISOString(),
                    run_attempt: 1
                }
            ]
        });

        mockGithub.mockApi(`/repos/test-owner/test-repo/actions/runs/${runId}`, {
            id: runId,
            run_attempt: 1
        });

        let retryWasCalled = false;
        mockGithub.mockApi(
            `/repos/test-owner/test-repo/actions/runs/${runId}/rerun-failed-jobs`,
            () => {
                retryWasCalled = true;
                return {};
            },
            { method: 'POST' }
        );

        // Run the action
        const result = await testRepo.runAction('.github/actions/retry-workflow/action.yaml', {
            inputs: {
                branch: 'main',
                workflow: 'Test Workflow',
                'max-retries': '1',
                'retry-mode': 'failed-only',
                'access_token': 'mock-token'
            }
        });

        // Verify outputs
        expect(result.outputs.status).toBe('timed_out');
        expect(result.outputs['was-retried']).toBe('true');
        expect(retryWasCalled).toBe(true);
    });
});
