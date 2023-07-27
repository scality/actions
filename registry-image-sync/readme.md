# Overview

This action helps to sync images between two container registries

# Example

on:
  workflow_dispatch:
```yaml
jobs:
  cleanup:
    runs-on: ubuntu-latest
    container:
      image: quay.io/skopeo/stable
    steps:
      - uses: actions/checkout@v3
      - name: Sync images
        uses: scality/actions/registry-image-sync
        with:
          SOURCE_REPO: <repo-name> # Ex bert-e
          IMAGE_NAME: <image-name> # Ex bert-e
          SRC_USERNAME: ${{ secrets.<src-username> }}
          SRC_PASSWORD:  ${{ secrets.<src-password> }}
          DEST_USERNAME: ${{ github.repository_owner }}
          DEST_PASSWORD: ${{ secrets.GITHUB_TOKEN }}
```
