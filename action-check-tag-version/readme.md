# Check tag, artifacts and version match

## Overview

This action takes care of checking that the following informations
match all together:

- tag:
  - matches the repository version
  - does not already exists
  - matches the branch where the release is being run
- version:
  - matches the given tag
- artifacts:
  - the commit used to produce the artifacts matches the current branch HEAD
  - the artifacts are successfull

This action ensures a clean release (no failed artifacts, no attemps to push an existent tag,...)

## Usage

This action is intended to be used in release process.

The action requires the artifacts `username` and `password` in order to check the artifacts status.

### Inputs

| Name                 | Description                   | Required |
|----------------------|-------------------------------|----------|
| tag                  | The tag to be released        | ✅       |
| version              | The version to be released    | ✅       |
| artifacts-to-promote | The artifacts to promote      | ✅       |
| ARTIFACTS_USER       | The artifacts username        | ✅       |
| ARTIFACTS_PASSWORD   | The artifacts password        | ✅       |

## Example

Here is an example of a workflow that uses that action.
The workflow example works as follow:

```yaml
name: release

on:
  workflow_dispatch:
    inputs:
      tag:
        description: 'Tag to be released'
        required: true
      artifacts-to-promote:
        description: 'Artifacts name to promote'
        required: true

jobs:
  create-release:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v3
        with:
          fetch-depth: 0 # fetch all tags
      - name: Get current version
        id: version
        run: |
          source ./VERSION
          echo "VERSION=${VERSION}" >> ${GITHUB_OUTPUT}
      - name: Check version and tag
        uses: scality/actions/action-check-tag-version@1.2.2
        with:
          tag: ${{ inputs.tag }}
          version: ${{ steps.version.outputs.VERSION }}
          artifacts-to-promote: ${{ inputs.artifacts-to-promote }}
          artifacts-user: ${{ secrets.ARTIFACTS_USER }}
          artifacts-password: ${{ secrets.ARTFICATS_PASSWORD }}
      - name: Create Release
        uses: softprops/action-gh-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ inputs.tag }}
          name: Release ${{ inputs.tag }}
          generate_release_notes: true
          target_commitish: ${{ github.sha }}

```
