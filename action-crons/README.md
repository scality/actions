## example

```yaml
name: 'Start cron jobs'

on:
  schedule:
    - cron: '20 1 * * 0-6'
    # Run main
    # test-1.yaml, test-2.yaml -f field_one=true

jobs:
  crons:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        jobs:
          - name: 'main'
            cron: '20 1 * * 0-6'
            branch: 'main'
            workflows: 'test-1.yaml, test-2.yaml -f field_one=true'

  steps:
    - uses: scality/action-releng-utils@v1
      with:
        event_schedule: ${{ matrix.jobs.name }}
        matrix_cron: ${{ matrix.jobs.cron }}
        matrix_branch: ${{ matrix.jobs.branch }}
        matrix_workflow: ${{ matrix.jobs.workflow }}
```