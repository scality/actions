#!/usr/bin/env bash
#
# Spawn a miniring cluster and wait until it reports readiness.

set -eu -o pipefail

READY='All processes started'

# Split the extra options on lines, so a value holding a space stays one
# argument
mapfile -t EXTRA < <(printf '%s\n' "${EXTRA_ARGS}" | sed -e 's/[[:space:]]*$//' -e '/^$/d')

# Start miniring $NODES nodes $DISKS disks and record its pid
sudo prlimit --memlock=unlimited \
    "${MINIRING_BIN}" spawn -n "${NODES}" -d "${DISKS}" \
    --node-bin-path "${NODE_BIN_PATH}" \
    --disk-bin-path "${DISK_BIN_PATH}" \
    "${EXTRA[@]}" > "${LOG}" 2>&1 &
echo $! > "${PID_FILE}"

# Wait for readiness
for _ in $(seq 1 "${TIMEOUT}"); do
    if grep -q "${READY}" "${LOG}" 2> /dev/null; then
        exit 0
    fi
    sleep 1
done

# Report the log on timeout
cat "${LOG}" >&2
echo "ERROR: miniring did not start within ${TIMEOUT}s" >&2
exit 1
