# Upload final status

## Overview

This action takes care of uploading the appropriate final status to the artifacts.

## Usage

The action is intended to be used at the very end of any workflow.
It si recomended to create a job that depends on all other jobs and
which simply uses the action as it is.

It does not require any inputs, the action will take care of uploading
the appropriate status by using Github context conditions.

**Note:** it is important to set the `always()` condition on the step
that calls this action so it's always called at the end.

### Example

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

```
