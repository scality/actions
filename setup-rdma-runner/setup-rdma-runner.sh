#!/usr/bin/env bash
#
# Set up SoftRoCE on the runner and report the address to bind RDMA to.

set -eu -o pipefail

# Install RDMA and io_uring libraries
sudo dnf -y install libibverbs-utils librdmacm liburing

# Allow io_uring, which biziod refuses to start without
if [ -e /proc/sys/kernel/io_uring_disabled ]; then
    sudo sysctl -w kernel.io_uring_disabled=0
    test "$(sysctl -n kernel.io_uring_disabled)" = 0
fi

# Load SoftRoCE kernel module
sudo modprobe rdma_rxe

# Attach SoftRoCE device to $NETDEV
sudo rdma link delete "${LINK}" 2> /dev/null || true
sudo rdma link add "${LINK}" type rxe netdev "${NETDEV}"

# Verify RDMA device
ibv_devinfo -d "${LINK}"

# Report the address to bind RDMA endpoints to
IP=$(ip -4 addr show "${NETDEV}" | awk '/inet / {print $2}' | cut -d/ -f1)
if [ -z "${IP}" ]; then
    echo "ERROR: ${NETDEV} has no IPv4 address" >&2
    exit 1
fi

# Check the link carries RC traffic: a ping-pong between client and server.
# The client retries until the server listens, and a server left without a
# client must not outlive the script.
ibv_rc_pingpong -d "${LINK}" -g 1 &
SERVER_PID=$!
trap 'kill "${SERVER_PID}" 2> /dev/null || true' EXIT
for attempt in 1 2 3 4 5; do
    sleep 1
    ibv_rc_pingpong -d "${LINK}" -g 1 "${IP}" && break
    if [ "${attempt}" -eq 5 ]; then
        echo "ERROR: no RC ping-pong over ${LINK}" >&2
        exit 1
    fi
done
wait "${SERVER_PID}"

echo "ip=${IP}" >> "${GITHUB_OUTPUT}"
