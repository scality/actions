# Upload final status

## Overview

This action takes care of uploading the appropriate final status to the artifacts.

## Usage

The action is intended to be used at the very end of any workflow.
It si recomended to create a job that depends on all other jobs and
which simply uses the action as it is.

The action requires the artifact `usrename` and `password` in order to upload the final status to the artifacts server.

### Inputs

| Name               | Description                   | Required |
|--------------------|-------------------------------|----------|
| ARTIFACTS_USER     | The artifacts username        | ✅       |
| ARTIFACTS_PASSWORD | The artifacts password        | ✅       |
| JOBS_RESULTS       | Concatenation of jobs results | ✅       |

**Note:** it is important to set the `always()` condition on the step
that calls this action so it's always called at the end.

## Example

Here is a example of a workflow that uses the action.
The workflow example works as follow:

1. the first job does some work
2. the second job will always be triggered at the end and upload the final status

```yaml
name: Pre merge

on:
  push:
    branches:
      - feature/**
      - improvement/**

jobs:
  build-doc:
    runs-on: ubuntu-20.04
    steps:
      - name: build doc
        run: tox -e doc

  final-status:
    runs-on: ubuntu-20.04
    needs:
      - build-doc
    steps:
      - name: upload final status
        if: always()
        uses: scality/actions/upload_final_status@main
        with:
          ARTIFACTS_USER: ${{ secrets.ARTIFACTS_USER }}
          ARTIFACTS_PASSWORD: ${{ secrets.ARTIFACTS_PASSWORD }}
          JOBS_RESULTS: ${{ join(needs.*.result) }}

```
