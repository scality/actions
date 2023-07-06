# Overview

This action is made to delete VMs that are older than a certain period of time in an OpenStack cluster.

# Example

```yaml
name: "delete old VMs in OpenStack"

on:
  workflow_dispatch:
  schedule:
    - cron: '0 0 * * *'

jobs:
  cleanup:
    runs-on: [self-hosted, centos7, large] # only centos7 runners is supported
    steps:
      - name: Clean up old VMs in OpenStack
        uses: scality/actions/actions-cleanup-openstack-vms
        with:
          # these secrets should be added to the repository secrets
          AUTH_URL: ${{ secrets.<AUTH_URL> }}
          AGE: 6 # deletes VMs older than 6 hours
          REGION: ${{ secrets.<REGION> }}
          USERNAME: ${{ secrets.<USERNAME> }}
          PASSWORD: ${{ secrets.<PASSWORD> }}
          PROJECT_NAME: ${{ secrets.<PROJECT_NAME> }}
          PROJECT_ID: ${{ secrets.<PROJECT_ID> }}
          ARTIFACTS_PASSWORD: ${{ secrets.ARTIFACTS_PASSWORD }}
          ARTIFACTS_USER: ${{ secrets.ARTIFACTS_USER }}
```