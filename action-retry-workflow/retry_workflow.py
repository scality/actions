#!/usr/bin/env python3
"""
Retry GitHub Actions workflow if failed.

This script checks the last workflow run on the latest commit of a branch
and retries it if it failed, based on the configured retry behavior.
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple, Any


# Constants for workflow statuses
FAILED_STATUSES = {"failure", "timed_out", "cancelled"}
SUCCESS_STATUS = "success"


class GitHubClient:
    """Wrapper for GitHub CLI commands."""

    def __init__(self, repo: str):
        """
        Initialize GitHub CLI client.

        Args:
            repo: Repository in owner/repo format
        """
        self.repo = repo

    def run_command(self, args: List[str]) -> str:
        """
        Run a GitHub CLI command and return the output.

        Args:
            args: List of command arguments for gh CLI

        Returns:
            Command output as string

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        cmd = ["gh"] + args

        # Set up environment with GH_REPO
        env = os.environ.copy()
        env["GH_REPO"] = self.repo

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env=env
        )
        return result.stdout.strip()

    def api_get(self, endpoint: str, jq_filter: Optional[str] = None, paginate: bool = False) -> str:
        """
        Execute a GET API request.

        Args:
            endpoint: API endpoint (e.g., "repos/owner/repo/commits/main")
            jq_filter: Optional jq filter expression
            paginate: Whether to paginate results

        Returns:
            API response as string
        """
        args = ["api", endpoint]
        if paginate:
            args.append("--paginate")
        if jq_filter:
            args.extend(["--jq", jq_filter])
        return self.run_command(args)

    def api_post(self, endpoint: str) -> bool:
        """
        Execute a POST API request.

        Args:
            endpoint: API endpoint

        Returns:
            True if successful, False otherwise
        """
        try:
            self.run_command(["api", "--method", "POST", endpoint])
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error executing POST {endpoint}: {e.stderr}", file=sys.stderr)
            return False


class WorkflowStep:
    """Represents a step within a workflow job."""

    def __init__(self, step_data: Dict):
        """
        Initialize workflow step.

        Args:
            step_data: Step data dictionary from GitHub API
        """
        self.name = step_data.get("name")
        self.conclusion = step_data.get("conclusion")
        self.status = step_data.get("status")

    def is_failed(self) -> bool:
        """
        Check if step failed.

        Returns:
            True if step failed, False otherwise
        """
        return self.conclusion in FAILED_STATUSES


class WorkflowJob:
    """Represents a job within a workflow run."""

    def __init__(self, job_data: Dict):
        """
        Initialize workflow job.

        Args:
            job_data: Job data dictionary from GitHub API

        Raises:
            ValueError: If required 'id' field is missing
        """
        if "id" not in job_data:
            raise ValueError("Job data missing required 'id' field")
        self.id = job_data["id"]
        self.name = job_data.get("name")
        self.conclusion = job_data.get("conclusion")
        self.status = job_data.get("status")
        self._steps_data = job_data.get("steps", [])
        self._steps: Optional[List[WorkflowStep]] = None

    @property
    def steps(self) -> List[WorkflowStep]:
        """
        Get steps in this job (lazy loaded).

        Returns:
            List of WorkflowStep objects
        """
        if self._steps is None:
            self._steps = [WorkflowStep(step) for step in self._steps_data]
        return self._steps

    def is_failed(self) -> bool:
        """
        Check if job failed.

        Returns:
            True if job failed, False otherwise
        """
        return self.conclusion in FAILED_STATUSES

    def has_failed_step(self, step_name: str) -> Optional[WorkflowStep]:
        """
        Check if a specific step failed.

        Args:
            step_name: Name of the step to check

        Returns:
            WorkflowStep if found and failed, None otherwise
        """
        for step in self.steps:
            if step.name == step_name and step.is_failed():
                return step
        return None


class WorkflowRun:
    """Represents a GitHub Actions workflow run."""

    def __init__(self, client: GitHubClient, run_data: Dict):
        """
        Initialize workflow run.

        Args:
            client: GitHubClient instance
            run_data: Workflow run data dictionary from GitHub API

        Raises:
            ValueError: If required 'id' field is missing
        """
        if "id" not in run_data:
            raise ValueError("Workflow run data missing required 'id' field")
        self.client = client
        self.id = run_data["id"]
        self.name = run_data.get("name")
        self.status = run_data.get("status")
        self.conclusion = run_data.get("conclusion")
        self.created_at = run_data.get("created_at")
        self.path = run_data.get("path", "")
        self._jobs: Optional[List[WorkflowJob]] = None
        self._retry_count: Optional[int] = None

    @property
    def jobs(self) -> List[WorkflowJob]:
        """
        Get jobs for this workflow run (lazy loaded).

        Returns:
            List of WorkflowJob objects
        """
        if self._jobs is None:
            self._jobs = self._fetch_jobs()
        return self._jobs

    @property
    def retry_count(self) -> int:
        """
        Get the number of retry attempts.

        Returns:
            Number of retry attempts (run_attempt - 1)
        """
        if self._retry_count is None:
            self._retry_count = self._fetch_retry_count()
        return self._retry_count

    def _fetch_jobs(self) -> List[WorkflowJob]:
        """
        Fetch jobs from GitHub API.

        Returns:
            List of WorkflowJob objects
        """
        output = self.client.api_get(
            f"repos/{self.client.repo}/actions/runs/{self.id}/jobs",
            jq_filter=".jobs[]",
            paginate=True
        )

        if not output:
            return []

        # Parse JSON lines
        jobs = []
        for line in output.strip().split("\n"):
            if line:
                jobs.append(WorkflowJob(json.loads(line)))

        return jobs

    def _fetch_retry_count(self) -> int:
        """
        Fetch retry count from GitHub API.

        Returns:
            Number of retry attempts
        """
        try:
            output = self.client.api_get(
                f"repos/{self.client.repo}/actions/runs/{self.id}",
                jq_filter=".run_attempt"
            )
            run_attempt = int(output)
            # run_attempt starts at 1, so subtract 1 to get retry count
            return run_attempt - 1
        except (ValueError, TypeError, subprocess.CalledProcessError):
            return 0

    def is_failed(self) -> bool:
        """
        Check if workflow is in a failed state.

        Returns:
            True if workflow failed, False otherwise
        """
        return self.conclusion in FAILED_STATUSES

    def succeeded(self) -> bool:
        """
        Check if workflow succeeded.

        Returns:
            True if workflow succeeded, False otherwise
        """
        return self.conclusion == SUCCESS_STATUS

    def retry(self, mode: str = "failed-only") -> bool:
        """
        Retry this workflow run.

        Args:
            mode: Either "all" or "failed-only"

        Returns:
            True if retry was successful, False otherwise
        """
        endpoint = (
            f"repos/{self.client.repo}/actions/runs/{self.id}/rerun"
            if mode == "all"
            else f"repos/{self.client.repo}/actions/runs/{self.id}/rerun-failed-jobs"
        )

        return self.client.api_post(endpoint)

    def _check_job_and_step_filter(
        self,
        job_name: str,
        step_name: str
    ) -> Tuple[bool, str]:
        """
        Check if specific job/step combination failed.

        Args:
            job_name: Name of the job to check
            step_name: Name of the step to check

        Returns:
            Tuple of (should_retry, reason)
        """
        for job in self.jobs:
            if job.name == job_name:
                failed_step = job.has_failed_step(step_name)
                if failed_step:
                    return True, f"Step '{step_name}' in job '{job_name}' failed"
                return False, (
                    f"Step '{step_name}' in job '{job_name}' did not fail "
                    f"(other failures ignored)"
                )
        return False, f"Job '{job_name}' not found"

    def _check_step_filter(self, step_name: str) -> Tuple[bool, str]:
        """
        Check if specific step failed in any job.

        Args:
            step_name: Name of the step to check

        Returns:
            Tuple of (should_retry, reason)
        """
        for job in self.jobs:
            failed_step = job.has_failed_step(step_name)
            if failed_step:
                return True, f"Step '{step_name}' failed in job '{job.name}'"
        return False, f"Step '{step_name}' did not fail (other failures ignored)"

    def _check_job_filter(self, job_name: str) -> Tuple[bool, str]:
        """
        Check if specific job failed.

        Args:
            job_name: Name of the job to check

        Returns:
            Tuple of (should_retry, reason)
        """
        for job in self.jobs:
            if job.name == job_name:
                if job.is_failed():
                    return True, f"Job '{job_name}' failed"
                return False, f"Job '{job_name}' did not fail (other failures ignored)"
        return False, f"Job '{job_name}' not found"

    def should_retry(
        self,
        job_name: Optional[str] = None,
        step_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Determine if workflow should be retried based on filters.

        Args:
            job_name: Optional job name filter
            step_name: Optional step name filter

        Returns:
            Tuple of (should_retry, reason)
        """
        # If workflow has no conclusion (still in progress), don't retry
        if self.conclusion is None:
            return False, f"Workflow is still in progress (status: {self.status}), not retrying"

        # If workflow succeeded overall, don't retry
        if self.succeeded():
            return False, f"Workflow status is '{self.conclusion}', no retry needed"

        # Check filters based on what was provided
        if job_name and step_name:
            return self._check_job_and_step_filter(job_name, step_name)
        if step_name:
            return self._check_step_filter(step_name)
        if job_name:
            return self._check_job_filter(job_name)

        # No filters, retry on any failure
        return True, "Workflow has failures"


class WorkflowRetryManager:
    """Manages workflow retry operations."""

    def __init__(
        self,
        repo: str,
        branch: str,
        workflow_name: str,
        max_retries: int = 1,
        retry_mode: str = "failed-only"
    ):
        """
        Initialize workflow retry manager.

        Args:
            repo: Repository in owner/repo format
            branch: Branch name
            workflow_name: Workflow name
            max_retries: Maximum number of retries allowed
            retry_mode: Retry behavior ("all" or "failed-only")
        """
        self.client = GitHubClient(repo)
        self.branch = branch
        self.workflow_name = workflow_name
        self.max_retries = max_retries
        self.retry_mode = retry_mode

    def get_latest_commit_sha(self) -> str:
        """
        Get the SHA of the latest commit on the branch.

        Returns:
            Commit SHA
        """
        output = self.client.api_get(
            f"repos/{self.client.repo}/commits/{self.branch}",
            jq_filter=".sha"
        )
        return output

    def get_workflow_runs(self, commit_sha: str) -> List[WorkflowRun]:
        """
        Get workflow runs for a specific commit.

        Args:
            commit_sha: Commit SHA to filter by

        Returns:
            List of WorkflowRun objects
        """
        print(f"Querying workflow runs for: workflow={self.workflow_name}, branch={self.branch}, commit={commit_sha[:8]}")

        try:
            output = self.client.api_get(
                f"repos/{self.client.repo}/actions/runs?branch={self.branch}&head_sha={commit_sha}",
                jq_filter=".workflow_runs[]",
                paginate=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to query workflow runs: {e.stderr}")
            return []

        if not output:
            print("No workflow runs found")
            return []

        # Parse JSON lines
        runs = []
        for line in output.strip().split("\n"):
            if line:
                run_data = json.loads(line)
                # Filter by workflow name
                if run_data.get("name") == self.workflow_name or \
                   run_data.get("path", "").endswith(f"/{self.workflow_name}"):
                    runs.append(WorkflowRun(self.client, run_data))

        print(f"Found {len(runs)} matching workflow runs")
        return runs

    def get_latest_workflow_run(self) -> Optional[WorkflowRun]:
        """
        Get the most recent workflow run.

        Returns:
            Latest WorkflowRun or None if not found
        """
        commit_sha = self.get_latest_commit_sha()
        print(f"Latest commit on {self.branch}: {commit_sha}")

        runs = self.get_workflow_runs(commit_sha)

        if not runs:
            return None

        # Sort by created_at descending to get the latest
        runs.sort(key=lambda x: x.created_at or "", reverse=True)
        return runs[0]

    def execute_retry_logic(
        self,
        job_filter: Optional[str] = None,
        step_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete retry logic and return results.

        Args:
            job_filter: Optional job name filter
            step_filter: Optional step name filter

        Returns:
            Dictionary with status, retry_count, was_retried, and run_id
        """
        print(f"Repository: {self.client.repo}")

        # Get latest workflow run
        workflow_run = self.get_latest_workflow_run()

        if not workflow_run:
            print(
                f"No workflow run found for '{self.workflow_name}' "
                f"on branch '{self.branch}'"
            )
            return {
                "status": "not_found",
                "retry_count": 0, # No retries performed, it does not exists
                "was_retried": False,
                "run_id": None
            }

        print(f"Workflow run ID: {workflow_run.id}")
        print(f"Workflow status: {workflow_run.conclusion}")

        # Early exit if workflow succeeded - no retry needed
        # This avoids unnecessary API calls and filter checks
        if workflow_run.succeeded():
            print("Workflow succeeded, no retry needed")
            return {
                "status": workflow_run.conclusion or "unknown",
                "retry_count": 0,  # No retries performed by this action run
                "was_retried": False,
                "run_id": workflow_run.id
            }

        # Workflow failed - check if it matches retry filters
        should_retry, retry_reason = workflow_run.should_retry(
            job_filter,
            step_filter
        )
        print(f"Retry decision: {retry_reason}")

        # Early exit if filters don't match
        if not should_retry:
            print(f"Not retrying: {retry_reason}")
            return {
                "status": workflow_run.conclusion or workflow_run.status or "unknown",
                "retry_count": 0,  # No retries performed by this action run
                "was_retried": False,
                "run_id": workflow_run.id
            }

        # Only fetch retry count if we actually need to consider retrying
        retry_count = workflow_run.retry_count
        print(f"Current retry count: {retry_count}")

        # Determine if we should retry based on max_retries
        was_retried = False
        if retry_count < self.max_retries:
            print(
                f"Retrying workflow (mode: {self.retry_mode}, "
                f"attempt {retry_count + 1}/{self.max_retries})..."
            )
            was_retried = workflow_run.retry(mode=self.retry_mode)
            if was_retried:
                print("Workflow retry initiated successfully")
                retry_count += 1
            else:
                print("Failed to retry workflow", file=sys.stderr)
        else:
            print(
                f"Max retries ({self.max_retries}) already reached, "
                f"not retrying"
            )

        return {
            "status": workflow_run.conclusion or "unknown",
            "retry_count": retry_count,
            "was_retried": was_retried,
            "run_id": workflow_run.id
        }


class RetryOutputWriter:
    """Handles writing outputs and summaries."""

    @staticmethod
    def write_github_output(
        output_file: Optional[str],
        status: str,
        retry_count: int,
        was_retried: bool
    ) -> None:
        """
        Write output variables for GitHub Actions.

        Args:
            output_file: Path to output file (GITHUB_OUTPUT)
            status: Workflow status
            retry_count: Number of retries performed
            was_retried: Whether retry was triggered
        """
        variables = {
            "status": status,
            "retry_count": str(retry_count),
            "was_retried": "true" if was_retried else "false"
        }

        if output_file:
            with open(output_file, "a") as f:
                for key, value in variables.items():
                    f.write(f"{key}={value}\n")

        # Also print to stdout
        print("\nOutput variables:")
        for key, value in variables.items():
            print(f"  {key}={value}")

    @staticmethod
    def write_step_summary(
        workflow_name: str,
        branch: str,
        status: str,
        retry_count: int,
        was_retried: bool,
        max_retries: int,
        retry_mode: str,
        run_id: Optional[int] = None
    ) -> None:
        """
        Write a summary to GitHub Actions step summary.

        Args:
            workflow_name: Name of the workflow
            branch: Branch name
            status: Workflow status/conclusion
            retry_count: Number of retries performed
            was_retried: Whether retry was triggered
            max_retries: Maximum retries allowed
            retry_mode: Retry mode (all/failed-only)
            run_id: Workflow run ID (optional)
        """
        summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary_file:
            return

        # Determine status emoji and message
        if status == "not_found":
            emoji = "🔍"
            status_msg = "Workflow run not found"
        elif status == SUCCESS_STATUS:
            emoji = "✅"
            status_msg = "Workflow succeeded"
        elif status in FAILED_STATUSES:
            emoji = "❌" if status == "failure" else "⏱️" if status == "timed_out" else "🚫"
            status_msg = f"Workflow {status}"
        elif status == "in_progress":
            emoji = "🔄"
            status_msg = "Workflow is still in progress"
        else:
            emoji = "ℹ️"
            status_msg = f"Workflow {status}"

        # Determine retry message
        if was_retried:
            retry_emoji = "🔄"
            retry_msg = f"**Retry triggered** (mode: `{retry_mode}`, attempt {retry_count}/{max_retries})"
        elif retry_count >= max_retries and status in FAILED_STATUSES:
            retry_emoji = "🛑"
            retry_msg = f"**Max retries reached** ({retry_count}/{max_retries})"
        elif status in FAILED_STATUSES:
            retry_emoji = "⏭️"
            retry_msg = "**No retry** (max retries already reached)"
        else:
            retry_emoji = "ℹ️"
            retry_msg = "**No retry needed**"

        # Build markdown summary
        summary = f"""## {emoji} Workflow Retry Action Summary

### Workflow Information
- **Workflow:** `{workflow_name}`
- **Branch:** `{branch}`
- **Status:** {emoji} {status_msg}
"""

        if run_id:
            repo = os.environ.get("GITHUB_REPOSITORY", "owner/repo")
            server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
            run_url = f"{server_url}/{repo}/actions/runs/{run_id}"
            summary += f"- **Run ID:** [{run_id}]({run_url})\n"

        summary += f"""
### Retry Information
{retry_emoji} {retry_msg}

| Setting | Value |
|---------|-------|
| Retry Count | {retry_count} |
| Max Retries | {max_retries} |
| Retry Mode | `{retry_mode}` |
| Was Retried | {'✅ Yes' if was_retried else 'No'} |
"""

        # Add context-specific message
        if was_retried:
            summary += f"""
---
✅ **Action taken:** The workflow has been retried. Check the workflow run page for progress.
"""
        elif status == "not_found":
            summary += f"""
---
ℹ️ **Note:** No workflow run found for `{workflow_name}` on the latest commit of branch `{branch}`.
"""
        elif status == "in_progress":
            summary += f"""
---
🔄 **In Progress:** The workflow is still running. Will check again on next retry schedule.
"""
        elif retry_count >= max_retries and status in FAILED_STATUSES:
            summary += f"""
---
⚠️ **Note:** Maximum retries ({max_retries}) have been reached. Manual intervention may be required.
"""
        elif status == SUCCESS_STATUS:
            summary += f"""
---
✅ **Success:** The workflow completed successfully. No retry needed.
"""

        # Write to summary file
        try:
            with open(summary_file, "a") as f:
                f.write(summary)
        except Exception as e:
            print(f"Warning: Could not write to step summary: {e}", file=sys.stderr)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Retry GitHub Actions workflow if failed"
    )
    parser.add_argument(
        "--branch",
        required=True,
        help="Branch name to check"
    )
    parser.add_argument(
        "--workflow",
        required=True,
        help="Workflow name to check"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Maximum number of retries allowed (default: 1)"
    )
    parser.add_argument(
        "--retry-mode",
        choices=["all", "failed-only"],
        default="failed-only",
        help="Retry behavior: 'all' or 'failed-only' (default: failed-only)"
    )
    parser.add_argument(
        "--job-name",
        default="",
        help="Only retry if this specific job failed (optional)"
    )
    parser.add_argument(
        "--step-name",
        default="",
        help="Only retry if this specific step failed (optional)"
    )
    parser.add_argument(
        "--output-file",
        help="File to write output variables (for GitHub Actions)"
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    args = parse_arguments()

    try:
        # Get repository from environment
        repo = os.environ.get("GITHUB_REPOSITORY")
        if not repo:
            print(
                "Error: GITHUB_REPOSITORY environment variable not set",
                file=sys.stderr
            )
            return 1

        # Create manager
        manager = WorkflowRetryManager(
            repo=repo,
            branch=args.branch,
            workflow_name=args.workflow,
            max_retries=args.max_retries,
            retry_mode=args.retry_mode
        )

        # Execute retry logic
        result = manager.execute_retry_logic(
            job_filter=args.job_name or None,
            step_filter=args.step_name or None
        )

        # Write outputs
        RetryOutputWriter.write_github_output(
            args.output_file,
            result["status"],
            result["retry_count"],
            result["was_retried"]
        )

        RetryOutputWriter.write_step_summary(
            args.workflow,
            args.branch,
            result["status"],
            result["retry_count"],
            result["was_retried"],
            args.max_retries,
            args.retry_mode,
            result.get("run_id")
        )

        return 0

    except subprocess.CalledProcessError as e:
        print(f"GitHub CLI error: {e.stderr}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
