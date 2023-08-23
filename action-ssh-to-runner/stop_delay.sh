#!/bin/bash

set -x -e

while ps -p $(cat /tmp/tmate.pid) > /dev/null ; do
    sleep 5
done

rm ${GITHUB_WORKSPACE}/timeout_date