#!/bin/bash

set -e

source /etc/os-release

# Check if tmate is installed
if ! command -v tmate &> /dev/null; then
  echo "tmate is not installed"
else
  echo "tmate is already installed"
  exit 0
fi

# If os is ubuntu or debian
if [[ $ID == "ubuntu" || $ID == "debian" ]]; then
    sudo apt-get update
    sudo apt-get install -y tmate
# if os is rocky, centos or redhat
elif [[ $ID == "rocky" || $ID == "centos" || $ID == "rhel" ]]; then
    if [[ ${VERSION_ID:0:1} -ge 8 ]]; then
        sudo dnf install -y "https://dl.fedoraproject.org/pub/epel/epel-release-latest-${VERSION_ID:0:1}.noarch.rpm"
        sudo dnf install -y tmate
    else
        sudo yum install -y epel-release
        sudo yum install -y tmate
    fi
else
  echo "Unsupported OS"
  exit 1
fi