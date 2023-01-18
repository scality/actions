# Bump version and open Pull Request

This action will bump the version of the calling component
and open a pull requests to integrate the changes.

## Description

This is intended to be used after a release of a component.
It enforces the component to have a file named `VERSION` located
at the root of the repository and to have the following format:

```sh
VERSION=X.Y.Z
```

## Inputs

This action requires no inputs.

**But:** it requires to run on a system that has the following commands available:

- git: in order to commit and push the new version
- gh: in order to open the new pull request
- curl: in order to install `semver` tool

**Important:** the action uses the tool `gh` in order to open a new PR.
This tool requires the following environemnt variable to be set:

- GH_TOKEN: gh environement variable to interract with Github

## Outputs

This action has the following outputs:

- pull-request-url: the URL of the newly openned pull request

## Example

This repository includes a workflow that uses this action, you can use it as a very basic example.

Otherwise here is a simple example during a release workflow

```yaml
name: Release

on:
  workflow_dispatch:
    inputs:
      tag:
        description: 'Tag to be released'
        required: true

jobs:
  create-release:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v3
        with:
          fetch-depth: 0 # fetch all tags
      - name: Create Release
        uses: softprops/action-gh-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          name: Release ${{ inputs.tag }}
          tag_name: ${{ inputs.tag }}
          generate_release_notes: true
          target_commitish: ${{ github.sha }}

  Bump-version:
    runs-on: ubuntu-latest
    needs:
      - create-release
    env:
      BRANCH: feature/bump_version_to_${{ inputs.tag }}
      GH_TOKEN: ${{ github.token }}
    steps:
      - name: Checkout
        uses: actions/checkout@v3
        with:
          # we must use the custom token in order to trigger the pre-merge on push
          # using default token will not trigger any CI run:
          # https://docs.github.com/en/actions/using-workflows/triggering-a-workflow#triggering-a-workflow-from-a-workflow
          token: ${{ secrets.GIT_ACCESS_TOKEN }}

      - name: Bump version
        uses: scality/actions/xcore/bump_version_pull_request@main
```
