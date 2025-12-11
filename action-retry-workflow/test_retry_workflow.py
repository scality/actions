#!/usr/bin/env python3
"""
Unit tests for retry_workflow.py
"""

import json
import subprocess
import unittest
from unittest.mock import Mock, patch, MagicMock

import retry_workflow


class TestGitHubClient(unittest.TestCase):
    """Test GitHubClient class"""

    @patch('subprocess.run')
    @patch.dict('os.environ', {}, clear=True)
    def test_run_command_success(self, mock_run):
        """Test successful gh command execution"""
        mock_run.return_value = Mock(
            stdout="test output\n",
            returncode=0
        )

        client = retry_workflow.GitHubClient("test-owner/test-repo")
        result = client.run_command(["api", "test"])

        mock_run.assert_called_once_with(
            ["gh", "api", "test"],
            capture_output=True,
            text=True,
            check=True,
            env={'GH_REPO': 'test-owner/test-repo'}
        )
        self.assertEqual(result, "test output")

    @patch('subprocess.run')
    @patch.dict('os.environ', {}, clear=True)
    def test_run_command_failure(self, mock_run):
        """Test gh command failure"""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["gh", "api", "test"], stderr="error"
        )

        client = retry_workflow.GitHubClient("test-owner/test-repo")
        with self.assertRaises(subprocess.CalledProcessError):
            client.run_command(["api", "test"])

    @patch.object(retry_workflow.GitHubClient, 'run_command')
    def test_api_get(self, mock_run_command):
        """Test API GET request"""
        mock_run_command.return_value = "result"

        client = retry_workflow.GitHubClient("test-owner/test-repo")
        result = client.api_get("repos/test-owner/test-repo/commits/main", jq_filter=".sha")

        mock_run_command.assert_called_once_with([
            "api",
            "repos/test-owner/test-repo/commits/main",
            "--jq", ".sha"
        ])
        self.assertEqual(result, "result")

    @patch.object(retry_workflow.GitHubClient, 'run_command')
    def test_api_post_success(self, mock_run_command):
        """Test successful API POST request"""
        mock_run_command.return_value = ""

        client = retry_workflow.GitHubClient("test-owner/test-repo")
        result = client.api_post("repos/test-owner/test-repo/actions/runs/123/rerun")

        self.assertTrue(result)

    @patch.object(retry_workflow.GitHubClient, 'run_command')
    def test_api_post_failure(self, mock_run_command):
        """Test failed API POST request"""
        mock_run_command.side_effect = subprocess.CalledProcessError(
            1, ["gh"], stderr="error"
        )

        client = retry_workflow.GitHubClient("test-owner/test-repo")
        result = client.api_post("repos/test-owner/test-repo/actions/runs/123/rerun")

        self.assertFalse(result)


class TestWorkflowStep(unittest.TestCase):
    """Test WorkflowStep class"""

    def test_is_failed_true(self):
        """Test step that failed"""
        step = retry_workflow.WorkflowStep({
            "name": "Test Step",
            "conclusion": "failure",
            "status": "completed"
        })
        self.assertTrue(step.is_failed())

    def test_is_failed_false(self):
        """Test step that succeeded"""
        step = retry_workflow.WorkflowStep({
            "name": "Test Step",
            "conclusion": "success",
            "status": "completed"
        })
        self.assertFalse(step.is_failed())


class TestWorkflowJob(unittest.TestCase):
    """Test WorkflowJob class"""

    def test_is_failed_true(self):
        """Test job that failed"""
        job = retry_workflow.WorkflowJob({
            "id": 123,
            "name": "Test Job",
            "conclusion": "failure",
            "status": "completed",
            "steps": []
        })
        self.assertTrue(job.is_failed())

    def test_is_failed_false(self):
        """Test job that succeeded"""
        job = retry_workflow.WorkflowJob({
            "id": 123,
            "name": "Test Job",
            "conclusion": "success",
            "status": "completed",
            "steps": []
        })
        self.assertFalse(job.is_failed())

    def test_has_failed_step_found(self):
        """Test finding a failed step"""
        job = retry_workflow.WorkflowJob({
            "id": 123,
            "name": "Test Job",
            "conclusion": "failure",
            "status": "completed",
            "steps": [
                {"name": "Step 1", "conclusion": "success", "status": "completed"},
                {"name": "Step 2", "conclusion": "failure", "status": "completed"}
            ]
        })
        result = job.has_failed_step("Step 2")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Step 2")

    def test_has_failed_step_not_found(self):
        """Test step not found or not failed"""
        job = retry_workflow.WorkflowJob({
            "id": 123,
            "name": "Test Job",
            "conclusion": "success",
            "status": "completed",
            "steps": [
                {"name": "Step 1", "conclusion": "success", "status": "completed"}
            ]
        })
        result = job.has_failed_step("Step 2")
        self.assertIsNone(result)


class TestWorkflowRun(unittest.TestCase):
    """Test WorkflowRun class"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = retry_workflow.GitHubClient("test-owner/test-repo")
        self.run_data = {
            "id": 123,
            "name": "Test Workflow",
            "status": "completed",
            "conclusion": "failure",
            "created_at": "2025-12-05T10:00:00Z",
            "path": ".github/workflows/test.yaml"
        }

    def test_is_failed_true(self):
        """Test workflow run that failed"""
        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)
        self.assertTrue(workflow_run.is_failed())

    def test_is_failed_false(self):
        """Test workflow run that succeeded"""
        self.run_data["conclusion"] = "success"
        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)
        self.assertFalse(workflow_run.is_failed())

    def test_succeeded_true(self):
        """Test workflow run that succeeded"""
        self.run_data["conclusion"] = "success"
        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)
        self.assertTrue(workflow_run.succeeded())

    def test_succeeded_false(self):
        """Test workflow run that failed"""
        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)
        self.assertFalse(workflow_run.succeeded())

    @patch.object(retry_workflow.GitHubClient, 'api_get')
    def test_fetch_retry_count(self, mock_api_get):
        """Test fetching retry count"""
        mock_api_get.return_value = "3"

        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)
        retry_count = workflow_run.retry_count

        self.assertEqual(retry_count, 2)  # run_attempt 3 - 1 = 2 retries

    @patch.object(retry_workflow.GitHubClient, 'api_get')
    def test_fetch_jobs(self, mock_api_get):
        """Test fetching jobs"""
        job1 = {"id": 1, "name": "Job 1", "conclusion": "success", "status": "completed", "steps": []}
        job2 = {"id": 2, "name": "Job 2", "conclusion": "failure", "status": "completed", "steps": []}
        mock_api_get.return_value = f"{json.dumps(job1)}\n{json.dumps(job2)}"

        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)
        jobs = workflow_run.jobs

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].name, "Job 1")
        self.assertEqual(jobs[1].name, "Job 2")

    @patch.object(retry_workflow.GitHubClient, 'api_post')
    def test_retry_all(self, mock_api_post):
        """Test retrying workflow with all mode"""
        mock_api_post.return_value = True

        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)
        result = workflow_run.retry(mode="all")

        self.assertTrue(result)
        mock_api_post.assert_called_once_with(
            "repos/test-owner/test-repo/actions/runs/123/rerun"
        )

    @patch.object(retry_workflow.GitHubClient, 'api_post')
    def test_retry_failed_only(self, mock_api_post):
        """Test retrying workflow with failed-only mode"""
        mock_api_post.return_value = True

        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)
        result = workflow_run.retry(mode="failed-only")

        self.assertTrue(result)
        mock_api_post.assert_called_once_with(
            "repos/test-owner/test-repo/actions/runs/123/rerun-failed-jobs"
        )

    def test_should_retry_success(self):
        """Test should not retry successful workflow"""
        self.run_data["conclusion"] = "success"
        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)

        should_retry, reason = workflow_run.should_retry()

        self.assertFalse(should_retry)
        self.assertIn("no retry needed", reason)

    def test_should_retry_in_progress(self):
        """Test should not retry in-progress workflow"""
        self.run_data["conclusion"] = None
        self.run_data["status"] = "in_progress"
        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)

        should_retry, reason = workflow_run.should_retry()

        self.assertFalse(should_retry)
        self.assertIn("still in progress", reason)

    @patch.object(retry_workflow.WorkflowRun, 'jobs', new_callable=lambda: property(lambda self: []))
    def test_should_retry_no_filters(self, mock_jobs):
        """Test should retry with no filters"""
        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)

        should_retry, reason = workflow_run.should_retry()

        self.assertTrue(should_retry)
        self.assertEqual(reason, "Workflow has failures")

    @patch.object(retry_workflow.WorkflowRun, 'jobs')
    def test_should_retry_with_job_filter_match(self, mock_jobs):
        """Test should retry with matching job filter"""
        job = Mock()
        job.name = "Build"
        job.is_failed.return_value = True
        mock_jobs.__get__ = Mock(return_value=[job])

        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)

        should_retry, reason = workflow_run.should_retry(job_name="Build")

        self.assertTrue(should_retry)
        self.assertIn("Job 'Build' failed", reason)

    @patch.object(retry_workflow.WorkflowRun, 'jobs')
    def test_should_retry_with_job_filter_no_match(self, mock_jobs):
        """Test should not retry with non-matching job filter"""
        job = Mock()
        job.name = "Build"
        job.is_failed.return_value = False
        mock_jobs.__get__ = Mock(return_value=[job])

        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)

        should_retry, reason = workflow_run.should_retry(job_name="Build")

        self.assertFalse(should_retry)
        self.assertIn("did not fail", reason)

    @patch.object(retry_workflow.WorkflowRun, 'jobs')
    def test_should_retry_with_step_filter_match(self, mock_jobs):
        """Test should retry with matching step filter"""
        step = Mock()
        step.name = "Test"

        job = Mock()
        job.name = "Build"
        job.has_failed_step.return_value = step
        mock_jobs.__get__ = Mock(return_value=[job])

        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)

        should_retry, reason = workflow_run.should_retry(step_name="Test")

        self.assertTrue(should_retry)
        self.assertIn("Step 'Test' failed", reason)

    @patch.object(retry_workflow.WorkflowRun, 'jobs')
    def test_should_retry_with_both_filters(self, mock_jobs):
        """Test should retry with both job and step filters"""
        step = Mock()
        step.name = "Test"

        job = Mock()
        job.name = "Build"
        job.has_failed_step.return_value = step
        mock_jobs.__get__ = Mock(return_value=[job])

        workflow_run = retry_workflow.WorkflowRun(self.client, self.run_data)

        should_retry, reason = workflow_run.should_retry(job_name="Build", step_name="Test")

        self.assertTrue(should_retry)
        self.assertIn("Step 'Test' in job 'Build' failed", reason)


class TestWorkflowRetryManager(unittest.TestCase):
    """Test WorkflowRetryManager class"""

    def setUp(self):
        """Set up test fixtures"""
        self.manager = retry_workflow.WorkflowRetryManager(
            repo="test-owner/test-repo",
            branch="main",
            workflow_name="Test Workflow",
            max_retries=2,
            retry_mode="failed-only"
        )

    @patch.object(retry_workflow.GitHubClient, 'api_get')
    def test_get_latest_commit_sha(self, mock_api_get):
        """Test getting latest commit SHA"""
        mock_api_get.return_value = "abc123def456"

        result = self.manager.get_latest_commit_sha()

        self.assertEqual(result, "abc123def456")

    @patch.object(retry_workflow.GitHubClient, 'api_get')
    def test_get_workflow_runs_with_results(self, mock_api_get):
        """Test getting workflow runs with results"""
        run1 = {
            "id": 123,
            "name": "Test Workflow",
            "path": ".github/workflows/test.yaml",
            "created_at": "2025-12-05T10:00:00Z",
            "conclusion": "failure",
            "status": "completed"
        }
        run2 = {
            "id": 124,
            "name": "Other Workflow",
            "path": ".github/workflows/other.yaml",
            "created_at": "2025-12-05T11:00:00Z",
            "conclusion": "success",
            "status": "completed"
        }

        mock_api_get.return_value = f"{json.dumps(run1)}\n{json.dumps(run2)}"

        result = self.manager.get_workflow_runs("abc123")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 123)
        self.assertEqual(result[0].name, "Test Workflow")

    @patch.object(retry_workflow.GitHubClient, 'api_get')
    def test_get_workflow_runs_by_path(self, mock_api_get):
        """Test filtering workflow runs by path"""
        run1 = {
            "id": 123,
            "name": "Test",
            "path": ".github/workflows/Test Workflow",
            "created_at": "2025-12-05T10:00:00Z",
            "conclusion": "failure",
            "status": "completed"
        }

        mock_api_get.return_value = json.dumps(run1)

        result = self.manager.get_workflow_runs("abc123")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 123)

    @patch.object(retry_workflow.GitHubClient, 'api_get')
    def test_get_workflow_runs_empty(self, mock_api_get):
        """Test getting workflow runs with no results"""
        mock_api_get.return_value = ""

        result = self.manager.get_workflow_runs("abc123")

        self.assertEqual(result, [])

    @patch.object(retry_workflow.WorkflowRetryManager, 'get_workflow_runs')
    @patch.object(retry_workflow.WorkflowRetryManager, 'get_latest_commit_sha')
    def test_get_latest_workflow_run_with_results(self, mock_get_commit, mock_get_runs):
        """Test getting latest workflow run with results"""
        mock_get_commit.return_value = "abc123"

        run1 = Mock()
        run1.id = 124
        run1.created_at = "2025-12-05T12:00:00Z"

        run2 = Mock()
        run2.id = 125
        run2.created_at = "2025-12-05T09:00:00Z"

        mock_get_runs.return_value = [run1, run2]

        result = self.manager.get_latest_workflow_run()

        # Should return the one with latest created_at
        self.assertEqual(result.id, 124)

    @patch.object(retry_workflow.WorkflowRetryManager, 'get_workflow_runs')
    @patch.object(retry_workflow.WorkflowRetryManager, 'get_latest_commit_sha')
    def test_get_latest_workflow_run_empty(self, mock_get_commit, mock_get_runs):
        """Test getting latest workflow run with no results"""
        mock_get_commit.return_value = "abc123"
        mock_get_runs.return_value = []

        result = self.manager.get_latest_workflow_run()

        self.assertIsNone(result)

    @patch.object(retry_workflow.WorkflowRetryManager, 'get_latest_workflow_run')
    def test_execute_retry_logic_workflow_not_found(self, mock_get_run):
        """Test execute retry logic when workflow not found"""
        mock_get_run.return_value = None

        result = self.manager.execute_retry_logic()

        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["retry_count"], 0)
        self.assertFalse(result["was_retried"])

    @patch.object(retry_workflow.WorkflowRetryManager, 'get_latest_workflow_run')
    def test_execute_retry_logic_workflow_success_no_retry(self, mock_get_run):
        """Test execute retry logic when workflow succeeded"""
        workflow_run = Mock()
        workflow_run.id = 123
        workflow_run.conclusion = "success"
        workflow_run.retry_count = 0
        workflow_run.succeeded.return_value = True
        workflow_run.should_retry.return_value = (False, "Workflow succeeded")

        mock_get_run.return_value = workflow_run

        result = self.manager.execute_retry_logic()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["retry_count"], 0)
        self.assertFalse(result["was_retried"])

    @patch.object(retry_workflow.WorkflowRetryManager, 'get_latest_workflow_run')
    def test_execute_retry_logic_workflow_failed_retry(self, mock_get_run):
        """Test execute retry logic when workflow failed and retry"""
        workflow_run = Mock()
        workflow_run.id = 123
        workflow_run.conclusion = "failure"
        workflow_run.retry_count = 0
        workflow_run.succeeded.return_value = False
        workflow_run.should_retry.return_value = (True, "Workflow has failures")
        workflow_run.retry.return_value = True

        mock_get_run.return_value = workflow_run

        result = self.manager.execute_retry_logic()

        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["retry_count"], 1)
        self.assertTrue(result["was_retried"])
        workflow_run.retry.assert_called_once_with(mode="failed-only")

    @patch.object(retry_workflow.WorkflowRetryManager, 'get_latest_workflow_run')
    def test_execute_retry_logic_workflow_max_retries_reached(self, mock_get_run):
        """Test execute retry logic when max retries reached"""
        workflow_run = Mock()
        workflow_run.id = 123
        workflow_run.conclusion = "failure"
        workflow_run.retry_count = 2  # Already at max
        workflow_run.succeeded.return_value = False
        workflow_run.should_retry.return_value = (True, "Workflow has failures")

        mock_get_run.return_value = workflow_run

        result = self.manager.execute_retry_logic()

        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["retry_count"], 2)
        self.assertFalse(result["was_retried"])
        workflow_run.retry.assert_not_called()


class TestRetryOutputWriter(unittest.TestCase):
    """Test RetryOutputWriter class"""

    @patch('builtins.open', new_callable=MagicMock)
    def test_write_github_output_with_file(self, mock_open_func):
        """Test writing output to file"""
        mock_file = MagicMock()
        mock_open_func.return_value.__enter__.return_value = mock_file

        retry_workflow.RetryOutputWriter.write_github_output(
            "/tmp/output.txt",
            "success",
            1,
            True
        )

        mock_open_func.assert_called_once_with("/tmp/output.txt", "a")
        mock_file.write.assert_any_call("status=success\n")
        mock_file.write.assert_any_call("retry_count=1\n")
        mock_file.write.assert_any_call("was_retried=true\n")

    def test_write_github_output_without_file(self):
        """Test writing output without file"""
        # Should not raise any exceptions
        retry_workflow.RetryOutputWriter.write_github_output(
            None,
            "success",
            0,
            False
        )


class TestMain(unittest.TestCase):
    """Test main function"""

    @patch('sys.argv', ['retry_workflow.py', '--branch', 'main', '--workflow', 'test.yaml'])
    @patch.dict('os.environ', {'GITHUB_REPOSITORY': 'test-owner/test-repo'})
    @patch.object(retry_workflow.WorkflowRetryManager, 'execute_retry_logic')
    @patch.object(retry_workflow.RetryOutputWriter, 'write_github_output')
    @patch.object(retry_workflow.RetryOutputWriter, 'write_step_summary')
    def test_main_workflow_success(self, mock_summary, mock_output, mock_execute):
        """Test main function with successful workflow"""
        mock_execute.return_value = {
            "status": "success",
            "retry_count": 0,
            "was_retried": False,
            "run_id": 123
        }

        result = retry_workflow.main()

        self.assertEqual(result, 0)
        mock_execute.assert_called_once()
        mock_output.assert_called_once()
        mock_summary.assert_called_once()


if __name__ == '__main__':
    unittest.main()
