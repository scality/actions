#!/bin/bash

set -ex

if [[ $# != 4 ]]; then
    echo "usage: $0 <github actor> <github_ref> <version> <version_bumped>"
    exit 1
fi

GITHUB_ACTOR=$1
REF=$2
VERSION=$3
NEW_VERSION=$4
git checkout -b feature/bump_version_${NEW_VERSION} ${REF}

# update version patch level
sed -i "s/VERSION=.*/VERSION=${NEW_VERSION}/" ./VERSION

git add ./VERSION

# config git to commit
git config --local user.name ${GITHUB_ACTOR}
git config --local user.email ${GITHUB_ACTOR}@scality.com

# commit changes
git commit -m "Bump version to ${NEW_VERSION}"

# fetch all branches
git fetch --all
all_dev_branches=$(git branch --all | grep -E 'origin/development/' | grep -v HEAD | sed 's_remotes/origin/development/__' | sort -u)
short_version=$(./semver get major ${VERSION}).$(./semver get minor  ${VERSION})

echo "Find upper branches in: ${all_dev_branches}"
echo "based on current branch: ${short_version}"

# Identify the upper version branches
upper_branches=""
for branch in ${all_dev_branches}; do
    is_upper=$(./semver compare "${branch}.0" "${short_version}.0")
    if [[ "${is_upper}" -gt 0 ]]; then
    upper_branches="${upper_branches}${branch} "
    fi
done
echo "Prepare waterfall branches for: ${upper_branches}"

for branch in ${upper_branches}; do
    echo "Create and push waterfall branch for origin/development/${branch}"
    git checkout -B w/${branch}/feature/bump_version_${NEW_VERSION} origin/development/${branch}

    # We now we can always use 'ours' as this sould only update the version file for the current branch only
    git merge --strategy=ours --no-edit feature/bump_version_${NEW_VERSION}

    git push -u origin w/${branch}/feature/bump_version_${NEW_VERSION}
done