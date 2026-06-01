# action-deploy-docs

Composite action to deploy documentation artifacts from artifacts.scality.net to the documentation server via SSH and rsync.

## Usage

```yaml
- uses: scality/actions/action-deploy-docs@main
  with:
    artifacts-name: my-product-docs
    version: 9.5.1
    product-path: "RING S3C"
    artifacts-user: ${{ secrets.ARTIFACTS_USER }}
    artifacts-password: ${{ secrets.ARTIFACTS_PASSWORD }}
    documentation-ssh-private-key: ${{ secrets.DOCUMENTATION_SSH_PRIVATE_KEY }}
    documentation-website: ${{ vars.DOCUMENTATION_WEBSITE }}
    documentation-ssh-public-key: ${{ vars.DOCUMENTATION_SSH_PUBLIC_KEY }}
    documentation-ssh-user: ${{ vars.DOCUMENTATION_SSH_USER }}
    site-path: ${{ vars.SITE_PATH }}
    documentation-website-file-owner: ${{ vars.DOCUMENTATION_WEBSITE_FILE_OWNER }}
```

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `artifacts-name` | yes | Name of the artifact to download |
| `version` | yes | Version string (e.g. 9.5.1) |
| `product-path` | yes | Space-separated list of product sub-paths for latest symlinks (e.g. "RING S3C" or "ARTESCA") |
| `artifacts-url` | no | Base URL for artifacts server (default: https://artifacts.scality.net) |
| `artifacts-user` | yes | Username for artifacts server |
| `artifacts-password` | yes | Password for artifacts server |
| `documentation-ssh-private-key` | yes | SSH private key for the documentation server |
| `documentation-website` | yes | Hostname of the documentation server |
| `documentation-ssh-public-key` | yes | SSH public key for the documentation server |
| `documentation-ssh-user` | yes | SSH username |
| `site-path` | yes | Base path on the documentation server |
| `documentation-website-file-owner` | yes | File owner (user:group) for deployed files |

## Prerequisites

The calling workflow must run `actions/checkout@v4` with `fetch-depth: 0` before using this action (required for latest symlink detection).

## What it does

1. Sets up SSH credentials and config for the documentation server
2. Downloads the documentation tarball from artifacts.scality.net
3. Copies and extracts the tarball on the documentation server via rsync/SSH
4. Sets correct ownership and permissions
5. Updates the `latest` symlink for each product path when on the default branch
6. Cleans up SSH credentials (always, even on failure)

## Important

This action is used to deploy to the **internal documentation server only**. Do not use for public-facing deployments.
