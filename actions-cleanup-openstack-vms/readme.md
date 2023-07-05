# Overview

This action is made to clean up VMs that are older than a certain period of time in an OpenStack cluster.

# Example

```yaml
name: "clean up idle VMs in OVH OpenStack"

on:
  workflow_dispatch:
  schedule:
    - cron: '0 0 * * *'

jobs:
  cleanup:
    runs-on: [self-hosted, centos7, large]
    steps:
      - name: Clean up orphan VMs in ${{ env.CLOUD }}
        uses: scality/actions/actions-cleanup-openstack-vms
        with:
          CLOUD: ${{ env.CLOUD }}
          AUTH_URL: ${{ secrets.AUTH_URL }}
          REGION: ${{ secrets.REGION }}
          USERNAME: ${{ secrets.USERNAME }}
          PASSWORD: ${{ secrets.PASSWORD }}
          TENANT_NAME: ${{ secrets.TENANT_NAME }}
```