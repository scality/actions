#!/usr/bin/env bash
#
# Set up SoftRoCE on the runner and report the address to bind RDMA to.

set -eu -o pipefail

# Install RDMA libraries
sudo dnf -y install libibverbs-utils librdmacm

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
echo "ip=${IP}" >> "${GITHUB_OUTPUT}"
