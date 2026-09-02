#!/usr/bin/env python3
"""Compute artifact input data for installer tests workflow"""

import argparse
import logging
import os
import re
import subprocess
import sys

try:
    from natsort import natsorted
    import requests
    import yaml

    from botocore.exceptions import ClientError
    import boto3
except ImportError:
    pass    # It's ok if we just check tech-train data


logger = logging.getLogger(__name__)


def _peek_argv_version_file():
    """Read --version-file from argv before argparse (needed at import time)."""
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == '--version-file' and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith('--version-file='):
            return arg.split('=', 1)[1]
    return None


def _resolve_version_file():
    """Locate RING VERSION file for major-version detection.

    Order:
      1. --version-file on the command line
      2. RING_VERSION_FILE or VERSION_FILE environment variable
      3. $GITHUB_WORKSPACE/VERSION
      4. Walk up from the current working directory
      5. Legacy walk from this script (RING .github/scripts/installer-tests/)
    """
    candidates = []

    peeked = _peek_argv_version_file()
    if peeked:
        candidates.append(peeked)

    for env_name in ('RING_VERSION_FILE', 'VERSION_FILE'):
        env_val = os.environ.get(env_name)
        if env_val:
            candidates.append(env_val)

    github_workspace = os.environ.get('GITHUB_WORKSPACE')
    if github_workspace:
        candidates.append(os.path.join(github_workspace, 'VERSION'))

    cwd = os.getcwd()
    probe = cwd
    for _ in range(6):
        candidates.append(os.path.join(probe, 'VERSION'))
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent

    # Legacy layout: .../ring/.github/scripts/installer-tests/arti_compute.py
    ring_dir = os.path.dirname(__file__)
    for _ in range(3):
        ring_dir = os.path.dirname(ring_dir)
    candidates.append(os.path.join(ring_dir, 'VERSION'))

    seen = set()
    for version_file in candidates:
        version_file = os.path.abspath(version_file)
        if version_file in seen:
            continue
        seen.add(version_file)
        if os.path.isfile(version_file):
            return version_file

    raise RuntimeError(
        "Cannot find RING VERSION file. Pass --version-file, set "
        "RING_VERSION_FILE, or run with GITHUB_WORKSPACE / RING checkout as cwd."
    )


def _get_ring_major():
    """Get current RING major version from VERSION file"""
    version_file = _resolve_version_file()
    with open(version_file, 'r', encoding='utf-8') as fd:
        for line in fd:
            m = re.match(r'^VERSION\s*=\s*[\'"]?(\d+)([.]\d+){3}', line)
            if m:
                return int(m.group(1))
    raise RuntimeError(f"Cannot find ring VERSION in '{version_file}'")


# Add a fake "sbom" job type, as sbom workflow is using us to get installer url
# In this case, we don't care about upgrade/upgradeprev or s3 stuff
JOB_TYPE = ("install", "upgrade", "upgradeprev", "sbom")
# RING previous version types
VERSION_TYPE = ("stable", "current", "previous")

_ring_major = _get_ring_major()

# NOTE: ADD_NEW_OS (do not remove)
OS = ()
if _ring_major > 8:
    # RHEL9 and Rocky9 only for RING9+
    OS += ("rhel9", "rocky9")
if _ring_major > 9:
    # scalityos only for RING10+
    OS += ("scalityos",)
if _ring_major < 10:
    OS += ("rhel8", "rocky8")

# scalityos or scalityos-X.Y or scalityos-X.Y-N or scalityos-X.Y-N.build_id
SCALITYOS_VERSION_REGEX = re.compile(
  r'^(?P<name>scalityos)(-(?P<ver>\d+[.]\d+(-\d+([.][a-f0-9]{8})?)?))?$'
)

# adi-X.Y.Z or adi-X.Y.Z.SHA or adi-X.Y.Z_pwN or adi-X.Y.Z_rcN
ADI_OS_REGEX = re.compile(
  r'^(?P<name>adi)-(?P<ver>\d+\.\d+\.\d+([.][a-f0-9]+|_(rc|pw)\d+)?)$'
)


def is_valid_os(os_name):
    """
    Check if os_name is a valid OS.
    Handles scalityos variants: scalityos, scalityos-X.Y, scalityos-X.Y-N, scalityos-X.Y-N.build_id
    Handles ADI variants: adi-X.Y.Z, adi-X.Y.Z-N.build_id
    """
    if os_name in OS:
        return True
    if SCALITYOS_VERSION_REGEX.match(os_name):
        return True
    if ADI_OS_REGEX.match(os_name):
        return True
    logger.warning(f"Unknown OS name '{os_name}'")
    return False


def is_scality_managed_os(os_name):
    """Check if OS is a Scality-managed image (scalityos or adi)"""
    return bool(SCALITYOS_VERSION_REGEX.match(os_name) or ADI_OS_REGEX.match(os_name))


def _split_os_minor(os_name):
    """Split an OS name into its major-only form and optional minor version.

    Examples:
        rhel9.6 -> ('rhel9', '9.6')
        rhel9   -> ('rhel9', None)
        rocky9  -> ('rocky9', None)
    scalityos/adi names are returned unchanged, with no minor.
    """
    if is_scality_managed_os(os_name):
        return os_name, None
    m = re.match(r'^(?P<base>[a-zA-Z]+\d+)\.(?P<minor>\d+)$', os_name)
    if not m:
        return os_name, None
    major = re.search(r'\d+$', m.group('base')).group(0)
    return m.group('base'), f"{major}.{m.group('minor')}"


# Architecture (1st one is the default)
ARCHITECTURE = (
    '1site_3nodes_s3_sofs',
    '1site_3nodes_s3',
    '1site_3nodes_1connector_sofs',
    '1site_6nodes_s3_sofs',
    '2sites_6nodes_s3_sofs',
    '3sites_6nodes_s3_sofs',
    '3sites_18nodes_s3_sofs',
)

# Tests from last GA on the previous techtrain already delivered
# Notes:
#       1) this should be updated every time VERSION file is changed (any branch)
#       2) it should be updated on the lowest RING branch (aka. RING8 branch)
#          so that the table is the same everywhere
TECH_TRAIN = {
    # Note: need only 3 digits in RING versions, we'll find the last one...
    'previous-8.5.8': '7.4.10',
    'previous-8.5.9': '7.4.10',
    'previous-8.5.10': '7.4.10',
    'previous-8.5.11': '7.4.10',
    'previous-8.5.12': '7.4.10',
    'previous-8.5.13': '7.4.10',

    'previous-9.2.0': '8.5.7',
    'previous-9.3.0': '8.5.8',
    'previous-9.4.0': '8.5.9',
    'previous-9.4.1': '8.5.9',
    'previous-9.4.2': '8.5.10',
    'previous-9.4.3': '8.5.11',
    'previous-9.5.0': '8.5.11',
    'previous-9.5.1': '8.5.12',
    'previous-9.5.2': '8.5.12',
    'previous-9.5.3': '8.5.12',
    'previous-9.5.4': '8.5.12',

    'previous-10.0.0': '9.5.2',
    'previous-10.1.0': '9.5.3',
}

DEFAULT_ARTIFACT_URL = 'https://artifacts.scality.net/builds'
DEFAULT_SEARCH_URL = 'https://artifacts.scality.net/search'
RING_BUILD = 'github:scality:ring'
PROMOTED_BUILD = f'{RING_BUILD}:promoted-'

ADI_BUILD = 'github:scality:adi'
ADI_PROMOTED_BUILD = f'{ADI_BUILD}:promoted-'
ADI_MANIFEST_HISTORY_API_URL = 'https://api.github.com/repos/scality/adi/contents/manifest-history.yaml'
ADI_MANIFEST_API_URL = 'https://api.github.com/repos/scality/adi/contents/manifest.yaml'

DEFAULT_REGION = 'eu-north-1'
DEFAULT_SUFFIX = 'GA'

# Replaces installers and snapshots when upgrade
# or OS+version combination is not supported
UNSUPPORTED = "__UNSUPPORTED__"


class ArtifactError(Exception):
    """Artifact related error"""
    def __init__(self, message, version=None):
        super().__init__(message)
        self.version = version


class VersionError(Exception):
    """Version related error"""
    def __init__(self, message, version=None):
        super().__init__(message)
        self.version = version


class SnapshotError(Exception):
    """Snapshot related error"""


class Unsupported(Exception):
    """Requested upgrade is not supported"""


# AWS related code, inspired from installci get_aws_images_list() function
def get_snapshots(region=None, custom_filters=None, filter_supervisor=True):
    """
    Get a list of AWS snaspshoted RING images

    :param custom_filters: list of (key, value)

    :raises: RuntimeError

    :return: list of available snapshot names matching filters
    :rtype: list
    """
    snapshot_list = []

    ec2 = boto3.client('ec2', region_name=region or DEFAULT_REGION)

    # Get list of all supervisor AMIs
    filters = []
    filters.append({'Name': 'tag:Addedby', 'Values': ['InstallCI']})
    filters.append({'Name': 'state', 'Values': ['available']})

    # useful_tags = set(SNAPSHOT_TAGS)
    # useful_tags.add('Addedby')

    # Filtering using --filter-snapshots inputs
    if custom_filters:
        for tag, value in custom_filters:
            filters.append({'Name': 'tag:' + tag, 'Values': [value]})

    # Set filter on supervisor
    if filter_supervisor:
        filters.append({'Name': 'tag:type', 'Values': ['supervisor']})

    try:
        images_list = ec2.describe_images(Owners=['self'], Filters=filters)
    except ClientError as err:
        error_code = err.response['Error']['Code']
        error_message = err.response['Error']['Message']
        raise RuntimeError('Error listing AMI in AWS: {0} - {1}'.format(error_code, error_message))
    except Exception as err:
        raise RuntimeError('Error listing AMI in AWS: {0}'.format(err))

    for image in images_list.get('Images', []):
        for tag in image.get('Tags', []):
            if tag['Key'] == 'platform_name':
                snapshot_list.append(tag['Value'])
                break
    return snapshot_list


class ArtiCompute:
    """Compute artifact data form installer tests"""
    def __init__(self, jobs, os_name, ring_artifact, s3_artifact, offline, auth,
                 upgrade_from_version=None, architecture=ARCHITECTURE[0], suffix=None, region=None,
                 adi_artifact=None, github_token=None, ring_explicit=False,
                 adi_upgrade_from_version=None, adi_branch=None):
        # Accept an optional OS minor (e.g. rhel9.6): keep os_name major-only
        # for installer/S3/validity logic, and remember the minor so snapshot
        # selection can pick the closest matching minor (see _select_snapshot).
        os_name, self.os_minor = _split_os_minor(os_name)
        if not is_valid_os(os_name):
            raise ValueError(f"Unknown OS name '{os_name}'")

        self.jobs = jobs
        self.os_name = os_name
        self.ring_artifact = ring_artifact
        self.s3_artifact = s3_artifact
        self.offline = offline
        if isinstance(auth, str):
            self.auth = tuple(auth.split(':', 1))
        else:
            self.auth = auth
        self.suffix = suffix
        self.region = region
        self.architecture = architecture

        self._ring_installer = None
        self._s3_installer = None
        self._ring_upgrade_from = None
        self._s3_upgrade_from = None
        self._upgrade_snapshot = None
        self._ring_upgradeprev_from = None
        self._s3_upgradeprev_from = None
        self._upgrade_snapshotprev = None

        self._adi_iso = None
        self._adi_version = None
        self._scos_version = None
        self._upgrade_adi_iso = None
        self._upgrade_scos_version = None
        self._upgradeprev_adi_iso = None
        self._upgradeprev_scos_version = None
        # Target versions resolved from the current ADI manifest entry
        self._adi_ring_version = None
        self._adi_s3_version = None
        self._upgrade_ring_version_display = None
        self._upgrade_s3_version_display = None
        self._is_scalityos = is_scality_managed_os(self.os_name)
        self._is_explicit_adi = bool(ADI_OS_REGEX.match(self.os_name))
        self._adi_manifest = None
        self._adi_branch = adi_branch

        self.upgrade_error_msg = ""
        self.upgradeprev_error_msg = ""

        try:
            self.nb_nodes = int(re.search(r'_(\d+)nodes_', architecture).group(1))
        except Exception:
            raise ValueError(f"Cannot extract number of nodes from architecture '{architecture}'")

        # Explicit ADI AMI (e.g. adi-0.0.2.f8dd7ff4): the AMI is
        # self-contained for install — installci uses the AMI directly
        # with no separate RING/S3/ADI ISO resolution needed.
        if self._is_explicit_adi:
            m = ADI_OS_REGEX.match(self.os_name)
            self._adi_version = m.group('ver')
            if 'upgrade' not in self.jobs and 'upgradeprev' not in self.jobs:
                return

        # Cache the ADI manifest entry when an explicit ADI artifact is used.
        # Keep the artifact choice self-contained so explicit ADI installs do
        # not trigger external RING/S3 resolution unless the workflow also
        # passes explicit overloads.
        self._adi_entry_cache = None
        if self._is_scalityos and adi_artifact and not ring_explicit:
            self._adi_manifest = self._fetch_adi_manifest_history(
                github_token=github_token, adi_ref=self._adi_branch)
            _adi_version = self._extract_adi_version(adi_artifact)
            if _adi_version is None:
                adi_url = os.path.join(DEFAULT_ARTIFACT_URL, adi_artifact)
                self._adi_iso = self._find_adi_iso(adi_url, self.auth)
                _adi_version = self._extract_version_from_iso(self._adi_iso)
            self._adi_entry_cache = self._find_adi_entry_by_version(
                self._adi_manifest, _adi_version)
            if self._adi_entry_cache is None:
                try:
                    self._adi_entry_cache = self._fetch_adi_current_entry(
                        github_token=github_token,
                        adi_ref=self._adi_branch,
                        adi_version=_adi_version)
                    logger.info(
                        f"Using target versions from ADI manifest.yaml "
                        f"(ref: {self._adi_branch or 'default'})")
                except ArtifactError:
                    logger.warning(
                        f"ADI version {_adi_version} not found in manifest "
                        f"(unreleased?), target versions will stay unresolved")

        # On scalityos with an explicit ADI artifact, S3 is bundled in
        # the ADI ISO — skip the S3 lookup unless an explicit S3
        # artifact override was provided.  Without an explicit ADI
        # artifact, RING and S3 are looked up normally; the ADI ISO
        # (resolved later from the branch manifest) only provides the
        # ADI repo and extra packages.
        _s3_from_adi = (self._is_scalityos and not self.s3_artifact
                        and bool(adi_artifact))

        # When an ADI artifact is provided on scalityos with no RING
        # artifact, skip the RING/S3 installer lookup entirely —
        # _resolve_adi will handle everything from the ADI ISO.
        _skip_ring_lookup = (self._is_scalityos and bool(adi_artifact)
                             and not self.ring_artifact)

        if not _skip_ring_lookup:
            self._ring_url = os.path.join(DEFAULT_ARTIFACT_URL, self.ring_artifact)
            self._ring_installer, guessed_version = self._find_ring_installer(
                self._ring_url, self.os_name, self.auth)
            if self._ring_installer is None:
                try:
                    self.is_valid(self.os_name, guessed_version)
                except Unsupported:
                    self._ring_installer = UNSUPPORTED
                    self._s3_installer = UNSUPPORTED
                    self._ring_upgrade_from = UNSUPPORTED
                    self._s3_upgrade_from = UNSUPPORTED
                    self._upgrade_snapshot = UNSUPPORTED
                    self._ring_upgradeprev_from = UNSUPPORTED
                    self._s3_upgradeprev_from = UNSUPPORTED
                    self._upgrade_snapshotprev = UNSUPPORTED
                    return
                raise ArtifactError(f"No RING installer found for '{self.ring_artifact}'")
        else:
            self._ring_url = ""
            logger.info(
                "Skipping RING/S3 installer lookup — "
                "versions will be resolved from ADI artifact")

        if "sbom" in self.jobs:
            # If sbom, we just want installer, skip everything else
            return

        if self._ring_installer == UNSUPPORTED:
            self._s3_installer = UNSUPPORTED
        elif _s3_from_adi or (_skip_ring_lookup and not self.s3_artifact):
            logger.info("S3 installer for scalityos will be resolved from ADI manifest")
        else:
            self._s3_installer = self._find_latest_s3_installer(
                self._ring_installer or self.ring_artifact or "",
                DEFAULT_ARTIFACT_URL, self.os_name, self.offline,
                buildid=self.s3_artifact, auth=self.auth)

        try:
            if self._is_scalityos:
                # scalityos/adi: upgrade-from resolved in _resolve_adi
                # via --adi-upgrade-from or manifest history
                pass
            elif upgrade_from_version:
                try:
                    self.is_valid_upgrade(upgrade_from=upgrade_from_version)
                    self._ring_upgrade_from = self._find_latest_stable(
                        self._ring_url, self.os_name, upgrade_from_version, auth=self.auth)
                    self._s3_upgrade_from = self._find_latest_s3_installer(
                        self._ring_upgrade_from, DEFAULT_ARTIFACT_URL,
                        self.os_name, self.offline, auth=self.auth)
                    self._upgrade_snapshot = self._find_snapshot(
                        self._ring_upgrade_from, self.os_name,
                        self.nb_nodes, self.suffix, os_minor=self.os_minor)
                except (ArtifactError, VersionError):
                    if 'upgrade' in self.jobs:
                        raise
                    self._ring_upgrade_from = None
                    self._s3_upgrade_from = None
                    self._upgrade_snapshot = None
            else:
                try:
                    # Installers for upgrade
                    upgrade_installer = self._ring_installer
                    while True:     # Not endless, loop will eventually fail
                        upgrade_from = self._get_precedent_major(
                            upgrade_installer, version_type='stable')
                        try:
                            self.is_valid_upgrade(upgrade_from=upgrade_from)
                            self._ring_upgrade_from = self._find_latest_stable(
                                self._ring_url, self.os_name, upgrade_from, auth=self.auth)
                            if not _s3_from_adi:
                                self._s3_upgrade_from = self._find_latest_s3_installer(
                                    self._ring_upgrade_from, DEFAULT_ARTIFACT_URL,
                                    self.os_name, self.offline, auth=self.auth)
                            self._upgrade_snapshot = self._find_snapshot(
                                ring_installer=self._ring_upgrade_from,
                                os_name=self.os_name,
                                nb_nodes=self.nb_nodes,
                                snapshot_suffix=self.suffix,
                                os_minor=self.os_minor)
                            break
                        except (ArtifactError, VersionError) as err:
                            if self._is_released_GA(err.version or upgrade_from):
                                raise   # We should have an installer for that version...
                            # Try with lower version (using fake name to fool _get_ring_version)...
                            upgrade_installer = f"fake-name-{upgrade_from}.r12345"
                except (ArtifactError, VersionError):
                    if 'upgrade' in self.jobs:
                        raise   # Problem only if upgrade job is requested
                    self._ring_upgrade_from = None
                    self._s3_upgrade_from = None
                    self._upgrade_snapshot = None
        except Unsupported as err:
            self._ring_upgrade_from = UNSUPPORTED
            self._s3_upgrade_from = UNSUPPORTED
            self._upgrade_snapshot = UNSUPPORTED
            self.upgrade_error_msg = f"({err})"

        try:
            if self._is_scalityos:
                if _ring_major > 10:
                    # RING 11+: upgradeprev is from RING 10, which has
                    # ScalityOS — resolved in _resolve_adi
                    pass
                else:
                    # RING 10: upgradeprev means upgrading from the previous
                    # major (RING 9), but ScalityOS does not exist before
                    # RING 10 — never supported.
                    raise Unsupported("scalityos upgradeprev not supported")
            else:
                upgradeprev_from = self._get_precedent_major(
                    self._ring_installer, version_type='previous')
                self.is_valid_upgrade(upgrade_from=upgradeprev_from, is_previous=True)
                self._ring_upgradeprev_from = self._find_latest_stable(
                    self._ring_url, self.os_name, upgradeprev_from, auth=self.auth)
                if not _s3_from_adi:
                    self._s3_upgradeprev_from = self._find_latest_s3_installer(
                        self._ring_upgradeprev_from, DEFAULT_ARTIFACT_URL,
                        self.os_name, self.offline, auth=self.auth)
                self._upgrade_snapshotprev = self._find_snapshot(
                    self._ring_upgradeprev_from, self.os_name,
                    self.nb_nodes, self.suffix, os_minor=self.os_minor)
        except (ArtifactError, VersionError):
            if 'upgradeprev' in self.jobs:
                raise   # Problem only if upgradeprev job is requested
            self._ring_upgradeprev_from = None
            self._s3_upgradeprev_from = None
            self._upgrade_snapshotprev = None
        except Unsupported as err:
            self._ring_upgradeprev_from = UNSUPPORTED
            self._s3_upgradeprev_from = UNSUPPORTED
            self._upgrade_snapshotprev = UNSUPPORTED
            self.upgradeprev_error_msg = f"({err})"

        # Resolve ADI ISO for scalityos
        if self._is_scalityos and self._ring_installer != UNSUPPORTED:
            self._resolve_adi(adi_artifact=adi_artifact,
                              adi_upgrade_from=adi_upgrade_from_version,
                              github_token=github_token)

    @property
    def ring_installer(self):
        """Get ring installer URL"""
        return self._ring_installer or ""

    @property
    def s3_installer(self):
        """Get S3 installer URL"""
        return self._s3_installer or ""

    @property
    def ring_upgrade_from(self):
        """Get ring upgrade-from installer URL"""
        return self._ring_upgrade_from or ""

    @property
    def s3_upgrade_from(self):
        """Get S3 upgrade-from installer URL"""
        return self._s3_upgrade_from or ""

    @property
    def ring_upgradeprev_from(self):
        """Get ring upgradeprev-from installer URL"""
        return self._ring_upgradeprev_from or ""

    @property
    def s3_upgradeprev_from(self):
        """Get S3 upgradeprev-from installer URL"""
        return self._s3_upgradeprev_from or ""

    @property
    def upgrade_snapshot(self):
        """Get upgrade snapshot name"""
        return self._upgrade_snapshot or ""

    @property
    def upgrade_snapshotprev(self):
        """Get upgradeprev snapshot name"""
        return self._upgrade_snapshotprev or ""

    @property
    def adi_iso(self):
        """Get ADI ISO URL (scalityos only)"""
        return self._adi_iso or ""

    @property
    def adi_version(self):
        """Get ADI version (scalityos only)"""
        return self._adi_version or ""

    @property
    def scos_version(self):
        """Get SCOS version from ADI manifest (scalityos only)"""
        return self._scos_version or ""

    @property
    def upgrade_adi_iso(self):
        """Get upgrade ADI ISO URL (scalityos only)"""
        return self._upgrade_adi_iso or ""

    @property
    def upgrade_scos_version(self):
        """Get upgrade SCOS version from ADI manifest (scalityos only)"""
        return self._upgrade_scos_version or ""

    @property
    def upgradeprev_adi_iso(self):
        """Get upgradeprev ADI ISO URL (scalityos only)"""
        return self._upgradeprev_adi_iso or ""

    @property
    def upgradeprev_scos_version(self):
        """Get upgradeprev SCOS version from ADI manifest (scalityos only)"""
        return self._upgradeprev_scos_version or ""

    @property
    def ring_version(self):
        """Get current ring version"""
        if self._adi_ring_version:
            return self._get_ring_version(self._adi_ring_version)
        if self._ring_installer == UNSUPPORTED:
            return UNSUPPORTED
        ring = self._ring_installer
        return self._get_ring_version(ring) if ring else ""

    @property
    def ring_upgrade_from_version(self):
        """Get ring upgrade-from version"""
        if self._upgrade_ring_version_display:
            return self._get_ring_version(self._upgrade_ring_version_display)
        if self._ring_upgrade_from == UNSUPPORTED:
            return UNSUPPORTED
        ring = self._ring_upgrade_from
        return self._get_ring_version(ring) if ring else ""

    @property
    def ring_upgradeprev_from_version(self):
        """Get ring upgradeprev-from version"""
        if self._ring_upgradeprev_from == UNSUPPORTED:
            return UNSUPPORTED
        ring = self._ring_upgradeprev_from
        return self._get_ring_version(ring) if ring else ""

    @property
    def s3_version(self):
        """Get current S3 version"""
        if self._adi_s3_version:
            return self._get_s3_version(self._adi_s3_version)
        if self._s3_installer == UNSUPPORTED:
            return UNSUPPORTED
        s3 = self._s3_installer
        return self._get_s3_version(s3) if s3 else ""

    @property
    def s3_upgrade_from_version(self):
        """Get S3 upgrade-from version"""
        if self._upgrade_s3_version_display:
            return self._get_s3_version(self._upgrade_s3_version_display)
        if self._s3_upgrade_from == UNSUPPORTED:
            return UNSUPPORTED
        s3 = self._s3_upgrade_from
        return self._get_s3_version(s3) if s3 else ""

    @property
    def s3_upgradeprev_from_version(self):
        """Get S3 upgradeprev-from version"""
        if self._s3_upgradeprev_from == UNSUPPORTED:
            return UNSUPPORTED
        s3 = self._s3_upgradeprev_from
        return self._get_s3_version(s3) if s3 else ""

    def is_valid(self, os_name=None, ring_version=None):
        """Check if OS+version combination is valid"""
        if os_name is None:
            os_name = self.os_name
        if ring_version is None:
            ring_version = self.ring_version

        version = [int(x) for x in ring_version.split('.')]
        while len(version) < 4:
            version.append(0)

        if os_name == 'rhel8':
            if version < [8, 5, 2, 0]:
                raise Unsupported("RHEL8 only supported from 8.5.2.0")
        elif os_name == 'rocky8':
            if version < [8, 5, 4, 0]:
                raise Unsupported("Rocky8 only supported from 8.5.4.0")
        elif os_name == 'rhel9':
            if version < [9, 3, 0, 0]:
                raise Unsupported("RHEL9 only supported from 9.3.0.0")
        elif os_name == 'rocky9':
            if version < [9, 4, 0, 0]:
                raise Unsupported("Rocky9 only supported from 9.4.0.0")
        elif is_scality_managed_os(os_name):
            # scalityos/adi is supported from RING 10.0.0+
            if version < [10, 0, 0, 0]:
                raise Unsupported("scalityos only supported from RING 10+")

    def is_valid_upgrade(self, upgrade_from, is_previous=False):
        """Check if requested upgrade is valid

        upgrade_from: version to upgrade from
        is_previous: check for upgradeprev instead of upgrade
        """
        version = [int(x) for x in self.ring_version.split('.')]
        from_version = [int(x) for x in upgrade_from.split('.')]
        # _get_precedent_major can return short versions (e.g. "9", "10.0")
        # after stripping trailing zeros; pad to 4 digits so list comparisons
        # like [10,0,0] < [10,0,0,0] don't produce false positives.
        while len(from_version) < 4:
            from_version.append(0)

        # Can only upgrade from as low as RING8
        if version[0] < 8:
            raise Unsupported("Upgrade only supported from RING8")

        if self.os_name == 'rhel8':
            # RedHat8 can upgrade only after 8.5.3.0 and upgrade-prev after 9.0.0.0
            if version < [8, 5, 3, 0]:
                raise Unsupported("RHEL8 upgrade only supported from 8.5.3.0")
            if is_previous and from_version < [8, 0, 0, 0]:
                raise Unsupported("RHEL8 upgradeprev only supported from 9.0.0.0")
        elif self.os_name == 'rocky8':
            # Rocky8 can upgrade only after 8.5.4.0 and upgrade-prev after 9.0.0.0
            if version < [8, 5, 4, 0]:
                raise Unsupported("Rocky8 upgrade only supported from 8.5.4.0")
            if is_previous and from_version < [8, 0, 0, 0]:
                raise Unsupported("Rocky8 upgradeprev only supported from 9.0.0.0")
        elif self.os_name == 'rhel9':
            # RedHat9 can upgrade only after 9.3.0.0
            if version < [9, 3, 0, 0]:
                raise Unsupported("RHEL9 upgrade only supported from 9.3.0.0")
            # upgradeprev on RING 9 targets RING 8, which has no RHEL9 image;
            # from RING 10 the previous tech-train is a 9.5.x (RHEL9-capable),
            # so upgradeprev is valid there.
            if is_previous and version[0] < 10:
                raise Unsupported("RHEL9 upgradeprev not supported")
        elif self.os_name == 'rocky9':
            # Rocky9 can upgrade only after 9.4.0.0
            if version < [9, 4, 0, 0]:
                raise Unsupported("Rocky9 upgrade only supported from 9.4.0.0")
            # upgradeprev on RING 9 targets RING 8, which has no Rocky9 image;
            # from RING 10 the previous tech-train is a 9.5.x (Rocky9-capable),
            # so upgradeprev is valid there.
            if is_previous and version[0] < 10:
                raise Unsupported("Rocky9 upgradeprev not supported")
        elif is_scality_managed_os(self.os_name):
            if from_version < [10, 0, 0, 0]:
                raise Unsupported("scalityos upgrade from pre-10.0.0 is not supported")
            if is_previous:
                raise Unsupported("scalityos upgradeprev not supported")

    @classmethod
    def _find_snapshot(cls, ring_installer, os_name, nb_nodes=3,
                       architecture=None, snapshot_suffix=None, region=None,
                       os_minor=None):
        """Find snapshot name from given RING installer URL.

        Snapshot selection is OS-minor aware (see _select_snapshot):
          - os_minor set (e.g. '9.6'): pick the highest available minor that
            is <= the requested minor, or None if none qualifies;
          - os_minor None (major-only request): pick the highest available
            minor.
        """
        if not is_valid_os(os_name):
            raise ValueError(f"Unknown OS name '{os_name}'")

        # Handle scalityos specially - it's passed directly to installci
        m = SCALITYOS_VERSION_REGEX.match(os_name)
        if m:
            name = m.group('name')
            version = m.group('ver')
            if not version:
                logger.warning("Snapshot not supported when a specific scalityos version is not provided")
                return None
        else:
            m = re.match(r'(?P<name>.+?)(?P<ver>\d+)', os_name)
            name = m.group('name').replace('rhel', 'redhat')
            version = m.group('ver')
        ring_version = cls._get_ring_version(ring_installer)

        msg = [f"Searching {os_name} RING {ring_version} {nb_nodes} nodes snapshot"]
        if architecture:
            msg.append(f"architecture={architecture}")
        if snapshot_suffix:
            msg.append(f"suffix={snapshot_suffix}")
        if region:
            msg.append(f"in region {region}")
        logger.info(" ".join(msg))

        if not architecture:
            architecture = ARCHITECTURE[0]

        # Do NOT filter on os_version here: snapshots are tagged with their
        # full OS version, which may be a bare major (e.g. "9") or a
        # major.minor (e.g. "9.7"). We want every available minor so that
        # _select_snapshot can pick the closest one <= the requested minor.
        # First try with architecture, if not found, try with nb_nodes
        for extra_filters in (('ring_architecture', architecture), ('nb_storage_server', str(nb_nodes))):
            snapshots = get_snapshots(
                custom_filters=[
                    ('ring_version', ring_version),
                    ('os_name', name),
                    ('owner', 'ci'),
                    extra_filters,
                ],
                region=region,
            )
            if snapshots:
                break

        if not snapshot_suffix:
            snapshot_suffix = DEFAULT_SUFFIX

        snapshot = cls._select_snapshot(
            snapshots, ring_version, name, version, os_minor, snapshot_suffix)
        if snapshot:
            logger.debug(f"Found {os_name} snapshot {snapshot} for RING {ring_version}")
        else:
            logger.debug(f"No {os_name} snapshot found for RING {ring_version}")
        return snapshot

    @classmethod
    def _select_snapshot(cls, snapshots, ring_version, os_family, os_major,
                         os_minor, snapshot_suffix):
        """Pick the best snapshot for the requested OS minor version.

        Snapshot names look like:
            RING-<ring_version>-<os_family><os_version>-<n>nodes[<suffix>]
        where <os_version> is a major ("9") or major.minor ("9.7").

        Selection rules for the requested OS (os_major[.os_minor]):
          - os_minor given: choose the highest available minor that is
            <= the requested minor; return None if none qualifies (never
            pick a higher minor, i.e. never "downgrade" the request);
          - os_minor None (major-only request): choose the highest
            available minor.
        A snapshot tagged with a bare major (no minor) is treated as
        minor 0, so it stays eligible as a last-resort fallback.
        """
        reSnapshot = re.compile(
            rf'^RING-{re.escape(ring_version)}-{re.escape(os_family)}'
            rf'(?P<osver>\d+(?:\.\d+)?)-.+?\[{re.escape(snapshot_suffix)}]$')

        target_major = int(os_major)
        target_minor = int(os_minor.split('.')[1]) if os_minor else None

        best = None     # (minor, name)
        for snapshot in snapshots:
            m = reSnapshot.match(snapshot)
            if not m:
                continue
            osver = m.group('osver').split('.')
            if int(osver[0]) != target_major:
                continue
            minor = int(osver[1]) if len(osver) > 1 else 0
            if target_minor is not None and minor > target_minor:
                continue    # never pick a higher minor than requested
            if best is None or minor > best[0]:
                best = (minor, snapshot)
        return best[1] if best else None

    @classmethod
    def _find_adi_snapshot(cls, adi_version, nb_nodes=3,
                           architecture=None, snapshot_suffix=None, region=None):
        """Find snapshot name from given ADI version"""
        msg = [f"Searching ADI {adi_version} {nb_nodes} nodes snapshot"]
        if architecture:
            msg.append(f"architecture={architecture}")
        if snapshot_suffix:
            msg.append(f"suffix={snapshot_suffix}")
        if region:
            msg.append(f"in region {region}")
        logger.info(" ".join(msg))

        if not architecture:
            architecture = ARCHITECTURE[0]

        for extra_filters in (('ring_architecture', architecture), ('nb_storage_server', str(nb_nodes))):
            snapshots = get_snapshots(
                custom_filters=[
                    ('adi_version', adi_version),
                    ('owner', 'ci'),
                    extra_filters,
                ],
                region=region,
            )
            if snapshots:
                break

        if not snapshot_suffix:
            snapshot_suffix = DEFAULT_SUFFIX
        reSnapshot = re.compile(rf'^ADI-{re.escape(adi_version)}-.+?\[{re.escape(snapshot_suffix)}]$')

        for snapshot in snapshots:
            if reSnapshot.match(snapshot):
                logger.debug(f"Found ADI snapshot {snapshot} for ADI {adi_version}")
                return snapshot

        logger.debug(f"No ADI snapshot found for ADI {adi_version}")
        return None

    @classmethod
    def _find_ring_installer(cls, base_url, os_name, auth=None):
        """Find ring installer URL"""
        if not is_valid_os(os_name):
            raise ValueError(f"Unknown OS name '{os_name}'")

        logger.info(f"Searching {os_name} RING installer for {os.path.basename(base_url)}")

        # Get RING version from any installer found, to sort the case
        # where we do not find the one we want, this could be because:
        #   1. the combination OS + RING version is not supported
        #   2. there is effectively a missing installer
        guessed_ring_version = None

        if base_url:
            # scalityos/adi use Rocky 9 installers
            if is_scality_managed_os(os_name):
                ring_os_name = "rocky_9"
            else:
                m = re.match(r'(?P<name>.+?)(?P<ver>\d+)', os_name)
                ring_os_name = f"{m.group('name')}_{m.group('ver')}"
            installer_suffix = f"{ring_os_name}.run"
            reRingInstaller = re.compile(rf'^scality-ring-.+?{installer_suffix}$')
            reAnyInstaller = re.compile(r'^scality-ring-.+?\.run$')

            response = requests.get(
                os.path.join(base_url, 'installer', '?format=txt'),
                auth=auth,
            )
            if not response.ok:
                raise ArtifactError(f"_find_ring_installer(): {response.reason} ({response.status_code})")
            if len(response.text) == 0:
                # Nothing returned; as the '?format=txt' hides HTTP 404 errors,
                # check if the URL is still valid...
                check = requests.head(os.path.join(base_url, 'installer', ''), auth=auth)
                if not check.ok:
                    raise ArtifactError(f"_find_ring_installer(): {check.reason} ({check.status_code})")
            for line in response.text.splitlines():
                if guessed_ring_version is None and reAnyInstaller.match(line):
                    guessed_ring_version = cls._get_ring_version(line)
                if reRingInstaller.match(line):
                    logger.debug(f"Found {os_name} RING installer {line} for RING {guessed_ring_version}")
                    return os.path.join(base_url, 'installer', line), guessed_ring_version
        logger.warning(f"Found no {os_name} RING installer for RING {guessed_ring_version}")
        return None, guessed_ring_version

    @classmethod
    def _find_s3_installer(cls, base_url, os_name, offline, auth=None):
        """Find S3 installer URL"""
        if not is_valid_os(os_name):
            raise ValueError(f"Unknown OS name '{os_name}'")

        logger.info(f"Searching {os_name} S3 installer for {os.path.basename(base_url)}")

        if base_url:
            # scalityos/adi use Rocky 9 installers
            if is_scality_managed_os(os_name):
                s3_os_name = 'rocky9'
                installer_type = ''
            else:
                # S3C installer has no minor version
                s3_os_name = re.sub(r'\.\d+$', '', os_name)  # e.g. rhel9.7 -> rhel9
                s3_os_name = s3_os_name.replace('rhel', 'redhat')
                installer_type = 'light-' if offline else ''

            # S3C archive formats:
            # - Versions < 7.10.0: s3-offline-light-{version}.tar.gz (no os-specific suffix)
            # - Versions < 10.0: s3-offline-light-{os}-{version}.tar.gz (respects offline flag)
            # - Versions >= 10.0: s3-offline-{os}-{version}.tar.gz (light doesn't exist)
            response = requests.get(
                os.path.join(base_url, '?format=txt'),
                auth=auth,
            )
            if not response.ok:
                raise ArtifactError(f"_find_s3_installer(): {response.reason} ({response.status_code})")

            # Try with installer_type first (respects offline flag for < 10.0)
            reS3Installer = re.compile(
                rf'^s3-offline-{installer_type}({s3_os_name}-)?\d+([.]\d+){{3}}[.]tar[.]gz$')
            for line in response.text.splitlines():
                if reS3Installer.match(line):
                    logger.debug(f"Found {os_name} S3 installer {line}")
                    return os.path.join(base_url, line)

            # Fall back to non-light if not found (for >= 10.0 when offline=True)
            if installer_type:
                reS3InstallerFallback = re.compile(
                    rf'^s3-offline-({s3_os_name}-)?\d+([.]\d+){{3}}[.]tar[.]gz$')
                for line in response.text.splitlines():
                    if reS3InstallerFallback.match(line):
                        logger.debug(f"Found {os_name} S3 installer {line} via fallback")
                        return os.path.join(base_url, line)

        logger.warning(f"Found no {os_name} S3 installer")
        return None

    @classmethod
    def _get_ring_version(cls, from_string):
        """Extract version number from a RING filename, URL, or bare version

        Return: string "a.b.c[.d]" or raise VersionError
        """
        reVersion = re.compile(r'^(?:.+-)?(\d+(\.\d+){2,3})(?:((\.r\d+)?.+))?$')
        basename = os.path.basename(from_string)
        m = reVersion.match(basename)
        if not m:
            raise VersionError(f"Cannot extract RING version from '{basename}'")
        return m.group(1)

    @classmethod
    def _get_s3_version(cls, from_string):
        """Extract version number from given S3 filename, URL, or bare version

        Return: string "a.b.c.d" or raise VersionError
            s3-offline-light-7.4.10.0.tar.gz -> 7.4.10.0
            s3-offline-light-7.4.10.0_rc1.tar.gz -> 7.4.10.0
            10.0.0.0_pw3 -> 10.0.0.0
        """
        reVersion = re.compile(r'^(?:.+-)?(\d+(\.\d+){2,3})(?:_(rc|pw)\d+)?(?:[.]tar[.]gz)?$')
        basename = os.path.basename(from_string)
        m = reVersion.match(basename)
        if not m:
            raise VersionError(f"Cannot extract S3 version from '{basename}'")
        return m.group(1)

    @classmethod
    def _get_precedent_major(cls, from_string, version_type='stable'):
        """Compute precedent stable major version for the installer

        from_string: current version string "a.b.c[.d]"
        version_type: one of "stable", "current", "previous", or "A[.B[.C[.D]]]"
            stable|previous for latest major version selection, or A[.B[.C[.D]]]
                - stable: get precedent stable version in the same techtrain
                - previous: get precedent stable in previous techtrain
        """
        if version_type in VERSION_TYPE:
            # stable and latest will make the same result, latest in techtrain
            if version_type == 'stable':
                version_type = 'latest'

            from_version = cls._get_ring_version(from_string)

            parts = from_version.split('.')
            if len(parts) < 3:
                raise VersionError(f"Cannot compute previous version from '{from_version}'")
            try:
                if version_type == 'latest':
                    # Drop last digit while it's zero
                    while parts and int(parts[-1]) == 0:
                        parts.pop()
                    if not parts:   # Nothing left....
                        raise VersionError(f"Invalid version '{from_version}'")
                    parts[-1] = str(int(parts[-1]) - 1)     # Use version before, whatever it is
                    _prev_version = ".".join(parts)
                else:   # previous
                    _prev_version = TECH_TRAIN[f"{version_type}-{'.'.join(parts[0:3])}"]
                logger.info(f"Previous version for {from_version} computed as {_prev_version}")
                return _prev_version
            except KeyError as err:
                # The table is outdated, better crash than guessing wrong...
                raise RuntimeError(
                    f"{sys.argv[0]}: missing key {err} in TECH_TRAIN table") from err
        else:
            # Version provided
            logger.info(f"Previous version for {from_version} provided as {version_type}")
            return version_type

    @classmethod
    def _find_latest_stable(cls, base_url, os_name, version, auth=None):
        """Retrieve latest stable RING installer URL

        base_url: URL to RING artifact installer directory
        os_name: OS name (rhelN, rockyN)
        version: Latest RING major/partial version (A[.B[.C[.D]]] or build-id)
        """
        if not is_valid_os(os_name):
            raise ValueError(f"Unknown OS name '{os_name}'")

        last_stable = None
        build_url = os.path.dirname(base_url)
        if version.startswith(f'{RING_BUILD}:'):
            # We were given a build; don't ask and use it...
            logger.info(f"Using provided {version} as last stable RING")
            last_stable = version
        else:
            logger.info(f"Searching {os_name} last stable for RING {version}")
            # Get the promoted builds, extract only version numbers, sort them
            # in increasing order, and pick the last one that matches our search.
            response = requests.get(
                os.path.join(build_url, '?format=txt'),
                auth=auth,
            )
            if not response.ok:
                raise ArtifactError(f"_find_latest_stable(): {response.reason} ({response.status_code})")

            reVersion = re.compile(rf'^{PROMOTED_BUILD}{version}([.]\d+){{0,3}}/$')
            version_list = []
            for line in response.text.splitlines():
                if reVersion.match(line):
                    version_list.append(line.rstrip('/'))
            if version_list:
                last_stable = natsorted(version_list)[-1]
        if last_stable is None:
            raise VersionError(f"No matching stable RING version found for '{version}'", version=version)
        last_installer, _ = cls._find_ring_installer(
            os.path.join(build_url, last_stable), os_name, auth=auth)
        if last_installer is None:
            raise ArtifactError(f"No RING installer found for '{last_stable}'",
                                version=cls._get_ring_version(last_stable))
        logger.debug(f"Found {os_name} last stable RING {last_stable} installer: {last_installer}")
        return last_installer

    @staticmethod
    def _is_released_GA(version):
        """Check if given version has been released as GA

        Notes:
            1. version can be a "short" one (eg. "9.4" will match any 9.4.x.y)
            2. this is done by retrieving git tags and looking for GA ones

        Returns list of tags matching given GA versions
        """
        reVersionGA = re.compile(r'^\d+([.]\d+){3}$')   # Only GA versions
        response = subprocess.run(
            ['git', 'tag', '--list', f'{version}*'],
            capture_output=True, text=True, check=False)
        tag_list = [v for v in response.stdout.splitlines() if reVersionGA.match(v)]
        return tag_list

    @classmethod
    def _find_latest_s3_installer(cls, base_ring_url, base_s3_url, os_name, offline, buildid=None, auth=None):
        """Retrieve latest stable S3 installer URL

        Notes:  1) If RING8, then get latest 7.5 S3 installer (could be RC one)
                   else, get S3 installer with same version as ring (no RC)
                2) if PREMERGE_S3_ARTIFACT is set, then it is overriden
                   from outside and we blindly return that version

        base_ring_url: RING URL (base or installer)
        base_s3_url: S3 base URL
        os_name: OS name (rhelN, rockyN)
        offline: Offline mode flag
        buildid: S3 build-id
        """
        if not is_valid_os(os_name):
            raise ValueError(f"Unknown OS name '{os_name}'")

        logger.info(f"Searching {os_name} latest S3 installer")

        last_installer = None
        if buildid:
            # S3 installer is forced from a build...
            last_installer = cls._find_s3_installer(
                os.path.join(base_s3_url, buildid), os_name, offline, auth=auth)
            try:    # For error message...
                s3_version = cls._get_s3_version(buildid)
                logger.debug(f"Using {os_name} latest S3 {s3_version} installer "
                             f"{last_installer} (provided by {buildid})")
            except VersionError:
                s3_version = ""
        else:
            ring_version = cls._get_ring_version(base_ring_url)
            s3_int_version = [int(x) for x in ring_version.split('.')]
            # Maintenance (3rd) and hotfix (4th) version numbers are the same
            # between RING 8 and Federation.
            # Only Major (1st) and minor (2nd) numbers are different
            # For RING 7- and 9+, S3 version is the same as RING version
            if s3_int_version[0] == 8:
                s3_int_version[0] -= 1
                s3_int_version[1] += 5
            s3_version = ".".join(str(x) for x in s3_int_version)

            # Get last version from API
            response = requests.get(
                os.path.join(
                    DEFAULT_SEARCH_URL,
                    'last_success/version/github/scality/federation/build-tests',
                    s3_version),
                auth=auth,
            )
            if not response.ok:
                raise ArtifactError(f"_find_latest_s3_installer(): {response.reason} ({response.status_code})")
            if response.text:
                buildid = response.text.splitlines()[0]
                last_installer = cls._find_s3_installer(
                            os.path.join(base_s3_url, buildid),
                            os_name, offline, auth=auth)
                logger.debug(f"Found {os_name} latest S3 {s3_version} installer {last_installer}")
            else:
                # Found nothing, search artifacts
                latest_version = {
                    'LAST': None,
                    'LAST_PW': None,
                    'LAST_RC': None,
                    'LAST_GA': None,
                }
                response = requests.get(
                    os.path.join(DEFAULT_ARTIFACT_URL, '?format=txt'),
                    auth=auth,
                )
                if not response.ok:
                    raise ArtifactError(f"_find_latest_s3_installer(): {response.reason} ({response.status_code})")
                reS3Version = re.compile(
                    rf'github:scality:[fF]ederation:staging-{s3_version}([.](\d+[.]?){{0,3}})?.+[.]build[.].+$')
                reS3VersionGA = re.compile(
                    rf'github:scality:[fF]ederation:promoted-{s3_version}([.](\d+[.]?){{0,3}})?/$')
                reS3VersionRC = re.compile(
                    rf'github:scality:[fF]ederation:promoted-{s3_version}([.](\d+[.]?){{0,3}})?_rc.+$')
                reS3VersionPW = re.compile(
                    rf'github:scality:[fF]ederation:promoted-{s3_version}([.](\d+[.]?){{0,3}})?_pw.+$')
                for line in response.text.splitlines():
                    if reS3Version.match(line):
                        latest_version['LAST'] = line
                    if reS3VersionGA.match(line):
                        latest_version['LAST_GA'] = line
                    if reS3VersionRC.match(line):
                        latest_version['LAST_RC'] = line
                    if reS3VersionPW.match(line):
                        latest_version['LAST_PW'] = line
                # Selection order: LAST_GA > LAST > LAST_RC > LAST_PW
                for key in ('LAST_GA', 'LAST', 'LAST_RC', 'LAST_PW'):
                    if latest_version[key]:
                        buildid = latest_version[key].rstrip('/')
                        last_installer = cls._find_s3_installer(
                            os.path.join(base_s3_url, buildid),
                            os_name, offline, auth=auth)
                        logger.debug(f"Found {os_name} latest S3 {s3_version} installer {last_installer}")
                        break
        if last_installer is None:
            raise VersionError(f"No S3 installer {s3_version} found")
        return last_installer

    @classmethod
    def _fetch_adi_manifest_history(cls, github_token=None, adi_ref=None):
        """Fetch manifest-history.yaml from the ADI repository on GitHub"""
        if adi_ref:
            logger.info(
                f"Fetching ADI manifest-history.yaml from GitHub "
                f"(ref: {adi_ref})")
        else:
            logger.info("Fetching ADI manifest-history.yaml from GitHub")
        headers = {
            'Accept': 'application/vnd.github.raw+json',
            'X-GitHub-Api-Version': '2026-03-10',
        }
        if github_token:
            headers['Authorization'] = f'Bearer {github_token}'
        params = {'ref': adi_ref} if adi_ref else None
        response = requests.get(ADI_MANIFEST_HISTORY_API_URL, headers=headers, params=params)
        if not response.ok:
            raise ArtifactError(
                f"Cannot fetch ADI manifest: {response.reason} ({response.status_code})")
        manifest = yaml.safe_load(response.text)
        if not manifest or 'history' not in manifest:
            raise ArtifactError("Invalid ADI manifest: missing 'history' key")
        logger.debug(f"Fetched ADI manifest with {len(manifest['history'])} entries")
        return manifest

    @classmethod
    def _fetch_adi_current_entry(cls, github_token=None, adi_ref=None, adi_version=None):
        """Fetch manifest.yaml and normalize it to a history-like ADI entry."""
        if adi_ref:
            logger.info(
                f"Fetching ADI manifest.yaml from GitHub "
                f"(ref: {adi_ref})")
        else:
            logger.info("Fetching ADI manifest.yaml from GitHub")
        headers = {
            'Accept': 'application/vnd.github.raw+json',
            'X-GitHub-Api-Version': '2026-03-10',
        }
        if github_token:
            headers['Authorization'] = f'Bearer {github_token}'
        params = {'ref': adi_ref} if adi_ref else None
        response = requests.get(ADI_MANIFEST_API_URL, headers=headers, params=params)
        if not response.ok:
            raise ArtifactError(
                f"Cannot fetch ADI manifest.yaml: {response.reason} ({response.status_code})")
        manifest = yaml.safe_load(response.text)
        if not manifest:
            raise ArtifactError("Invalid ADI manifest.yaml: empty document")

        if isinstance(manifest.get('components'), dict):
            components = manifest.get('components', {})
        else:
            components = {
                key: value for key, value in manifest.items()
                if key in ('ring', 's3c', 'scos') and isinstance(value, dict)
            }
        if not components:
            raise ArtifactError("Invalid ADI manifest.yaml: missing 'components'")

        entry_adi_version = (
            manifest.get('adi_version')
            or manifest.get('version')
            or adi_version
            or '')
        logger.debug("Fetched ADI manifest.yaml with components: %s",
                     ", ".join(sorted(components.keys())))
        return {
            'adi_version': entry_adi_version,
            'components': components,
        }

    @classmethod
    def _match_adi_by_ring(cls, manifest, ring_installer):
        """Find ADI manifest entry matching a RING installer.

        Fallback chain (stops at first match, prefers latest entry):
          1. Exact installer filename match
          2. Exact RING version match    (e.g. 10.0.0.1)
          3. Major.minor version match   (e.g. 10.0.*)

        Returns (entry, exact_match) tuple, or (None, False) if no match.
        """
        ring_basename = os.path.basename(ring_installer)
        ring_version = cls._get_ring_version(ring_installer)
        ring_version_short = ".".join(ring_version.split(".")[:2])

        # Step 1: Exact installer filename match (prefer latest entry)
        for entry in reversed(manifest.get('history', [])):
            ring_info = entry.get('components', {}).get('ring', {})
            if ring_info.get('installer') == ring_basename:
                logger.info(
                    f"Exact ADI match: ADI {entry['adi_version']} "
                    f"matches RING installer {ring_basename}")
                return entry, True

        # Step 2: Fallback — match by exact RING version
        logger.warning(
            f"No exact installer match for '{ring_basename}', "
            f"falling back to version-only match for RING {ring_version}")
        for entry in reversed(manifest.get('history', [])):
            ring_info = entry.get('components', {}).get('ring', {})
            manifest_version = ring_info.get('version', '')
            base_version = re.sub(r'_(pw|rc)\d+$', '', manifest_version)
            if base_version == ring_version:
                logger.warning(
                    f"Version-only ADI match: ADI {entry['adi_version']} "
                    f"has RING version {manifest_version} "
                    f"(matched against {ring_version})")
                return entry, False

        # Step 3: Fallback — match by major.minor RING version
        logger.warning(
            f"No exact version match for RING {ring_version}, "
            f"falling back to major.minor match ({ring_version_short}.*)")
        for entry in reversed(manifest.get('history', [])):
            ring_info = entry.get('components', {}).get('ring', {})
            manifest_version = ring_info.get('version', '')
            base_version = re.sub(r'_(pw|rc)\d+$', '', manifest_version)
            manifest_version_short = ".".join(base_version.split(".")[:2])
            if manifest_version_short == ring_version_short:
                logger.warning(
                    f"Major.minor ADI match: ADI {entry['adi_version']} "
                    f"has RING version {manifest_version} "
                    f"(matched against {ring_version_short}.*)")
                return entry, False

        logger.error(
            f"No ADI version matches RING {ring_version} "
            f"(installer: {ring_basename})")
        return None, False

    @classmethod
    def _find_adi_iso(cls, base_url, auth=None):
        """Find ADI ISO URL from an ADI artifact directory on artifacts.scality.net"""
        logger.info(f"Searching ADI ISO in {os.path.basename(base_url)}")
        response = requests.get(
            os.path.join(base_url, '?format=txt'),
            auth=auth,
        )
        if not response.ok:
            raise ArtifactError(
                f"_find_adi_iso(): {response.reason} ({response.status_code})")
        reIso = re.compile(r'^.+\.iso$')
        for line in response.text.splitlines():
            if reIso.match(line):
                iso_url = os.path.join(base_url, line)
                logger.debug(f"Found ADI ISO: {line}")
                return iso_url
        raise ArtifactError(f"No ADI ISO found in {os.path.basename(base_url)}")

    @staticmethod
    def _extract_adi_version(artifact_name):
        """Extract ADI version from a promoted artifact name.

        Returns the version string for promoted artifacts
        (e.g. 'github:scality:adi:promoted-0.0.1' -> '0.0.1'),
        or None for non-promoted artifacts (e.g. staging builds)
        whose version can only be determined from the ISO filename.
        """
        m = re.match(rf'^{re.escape(ADI_PROMOTED_BUILD)}(.+)$', artifact_name)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _extract_version_from_iso(iso_url):
        """Extract ADI version from an ISO URL or filename.

        e.g. '.../scality-adi-0.0.2.iso' -> '0.0.2'
        """
        basename = os.path.basename(iso_url)
        m = re.match(r'^scality-adi-(.+)\.iso$', basename)
        if m:
            return m.group(1)
        raise ValueError(
            f"Cannot extract ADI version from ISO filename '{basename}'")

    @classmethod
    def _find_latest_adi_artifact(cls, adi_version, auth=None):
        """Find the latest available ADI artifact for a version.

        Prefer the latest successful non-promoted ADI build so scalityos runs
        test the current ADI branch content. Fall back to the promoted
        artifact when no newer build can be resolved.
        """
        logger.info(f"Searching latest ADI artifact for version {adi_version}")

        response = requests.get(
            os.path.join(
                DEFAULT_SEARCH_URL,
                'last_success/version/github/scality/adi/Build-ADI-ISO',
                adi_version),
            auth=auth,
        )
        if response.ok and response.text:
            adi_build = response.text.splitlines()[0].strip().rstrip('/')
            logger.info(
                f"Using latest ADI artifact for {adi_version}: {adi_build}")
            return adi_build
        if not response.ok:
            logger.warning(
                f"Cannot resolve latest ADI build from search API: "
                f"{response.reason} ({response.status_code})")

        response = requests.get(
            os.path.join(DEFAULT_ARTIFACT_URL, '?format=txt'),
            auth=auth,
        )
        if response.ok:
            candidates = []
            for line in response.text.splitlines():
                adi_build = line.rstrip('/')
                if not adi_build.startswith(f'{ADI_BUILD}:'):
                    continue
                if adi_build.startswith(ADI_PROMOTED_BUILD):
                    continue
                if adi_version not in adi_build:
                    continue
                candidates.append(adi_build)
            if candidates:
                adi_build = natsorted(candidates)[-1]
                logger.info(
                    f"Using latest ADI artifact from listing for "
                    f"{adi_version}: {adi_build}")
                return adi_build
        else:
            logger.warning(
                f"Cannot list ADI artifacts: "
                f"{response.reason} ({response.status_code})")

        adi_build = f"{ADI_PROMOTED_BUILD}{adi_version}"
        promoted_url = os.path.join(DEFAULT_ARTIFACT_URL, adi_build)
        try:
            cls._find_adi_iso(promoted_url, auth=auth)
        except ArtifactError as err:
            raise ArtifactError(
                f"No latest-success or promoted ADI artifact found for "
                f"{adi_version}") from err
        logger.warning(
            f"Falling back to promoted ADI artifact for {adi_version}: "
            f"{adi_build}")
        return adi_build

    @classmethod
    def _find_promoted_adi_artifact(cls, adi_version, auth=None):
        """Return the promoted ADI artifact for a version after verifying it."""
        adi_build = f"{ADI_PROMOTED_BUILD}{adi_version}"
        promoted_url = os.path.join(DEFAULT_ARTIFACT_URL, adi_build)
        cls._find_adi_iso(promoted_url, auth=auth)
        logger.info(
            f"Using promoted ADI artifact for {adi_version}: {adi_build}")
        return adi_build

    @staticmethod
    def _find_adi_entry_by_version(manifest, adi_version):
        """Find manifest entry matching a specific ADI version"""
        for entry in manifest.get('history', []):
            if entry.get('adi_version') == adi_version:
                return entry
        return None

    @staticmethod
    def _find_previous_adi_entry(manifest, current_version):
        """Find the manifest entry for the ADI version preceding
        *current_version* in the manifest history.

        The history is ordered oldest-first (chronological).  If
        *current_version* is found at index *i*, returns the entry
        at index *i-1* (the previously released version).  If
        *current_version* is not in the manifest (unreleased), returns
        the last entry (the latest released version).
        """
        history = manifest.get('history', [])
        if not history:
            return None
        for i, entry in enumerate(history):
            if entry.get('adi_version') == current_version:
                if i > 0:
                    return history[i - 1]
                return None   # current is the oldest entry, no previous
        # Unreleased version: previous is the latest released
        return history[-1]

    @staticmethod
    def _get_scos_version(adi_entry):
        """Extract scos.version from an ADI manifest entry"""
        return adi_entry.get('components', {}).get('scos', {}).get('version', '')

    @classmethod
    def _detect_scos_from_artifact(cls, artifact_url, auth=None):
        """Detect ScalityOS version from the SBOM in an ADI artifact.

        Lists {artifact_url}/sbom/ and looks for a filename matching
        scalityos-{MAJOR.MINOR}-{RELEASE}-{ARCH}.iso-sbom.json,
        returning MAJOR.MINOR-RELEASE (e.g. '9.7-10').
        """
        sbom_url = os.path.join(artifact_url, 'sbom', '?format=txt')
        try:
            response = requests.get(sbom_url, auth=auth)
        except requests.RequestException as exc:
            logger.warning(f"Cannot reach SBOM directory: {exc}")
            return None
        if not response.ok:
            logger.warning(
                f"Cannot list SBOM directory: "
                f"{response.reason} ({response.status_code})")
            return None
        pattern = re.compile(
            r'^scalityos-(\d+\.\d+-\d+)-.+\.iso-sbom\.json$')
        for line in response.text.splitlines():
            m = pattern.match(line.strip())
            if m:
                logger.debug(f"Detected SCOS version from SBOM: {line.strip()}")
                return m.group(1)
        logger.warning(f"No scalityos SBOM found in {artifact_url}/sbom/")
        return None

    def _find_s3_from_manifest(self, adi_entry):
        """Find S3 installer URL from an ADI manifest entry.

        Searches for the promoted S3 build on artifacts.scality.net
        and verifies the installer exists.
        """
        s3c = adi_entry.get('components', {}).get('s3c', {})
        s3_version = s3c.get('version', '')
        if not s3_version:
            raise ArtifactError("ADI manifest entry missing S3C version")

        logger.info(
            f"Resolving S3 installer from ADI manifest (S3C version {s3_version})")

        for s3_org in ('federation', 'Federation'):
            s3_build = f"github:scality:{s3_org}:promoted-{s3_version}"
            s3_url = os.path.join(DEFAULT_ARTIFACT_URL, s3_build)
            try:
                s3_installer = self._find_s3_installer(
                    s3_url, self.os_name, self.offline, auth=self.auth)
                if s3_installer:
                    logger.info(
                        f"Found S3 installer from ADI manifest: "
                        f"{os.path.basename(s3_installer)}")
                    return s3_installer
            except ArtifactError:
                continue

        raise ArtifactError(
            f"S3 installer for version {s3_version} (from ADI manifest) "
            f"not found on artifacts.scality.net")

    def _resolve_adi(self, adi_artifact=None, adi_upgrade_from=None,
                     github_token=None):
        """Resolve ADI ISO and S3 installers for scalityos.

        For each version (target, upgrade):
        - Finds the matching ADI ISO URL
        - Resolves S3 installer from the manifest when not explicitly provided

        The previous ADI version for upgrades is determined by (in order):
        1. --adi-upgrade-from (explicit ADI version override)
        2. Manifest history (auto-detect previous entry)
        """
        # Target version
        if adi_artifact:
            # Explicit ADI artifact provided
            self._adi_version = self._extract_adi_version(adi_artifact)
            adi_url = os.path.join(DEFAULT_ARTIFACT_URL, adi_artifact)
            if self._adi_version is None:
                if not self._adi_iso:
                    self._adi_iso = self._find_adi_iso(adi_url, self.auth)
                self._adi_version = self._extract_version_from_iso(
                    self._adi_iso)
            if not self._adi_iso:
                self._adi_iso = self._find_adi_iso(adi_url, self.auth)
            # Component info (S3, RING, SCOS versions) comes from the
            # branch manifest.yaml
            adi_entry = (self._adi_entry_cache
                         or self._fetch_adi_current_entry(
                             github_token=github_token,
                             adi_ref=self._adi_branch,
                             adi_version=self._adi_version))
            logger.info(
                f"Using explicit ADI artifact: {adi_artifact} "
                f"(version {self._adi_version})")
        else:
            # No explicit artifact, resolve from manifest.yaml
            adi_entry = self._fetch_adi_current_entry(
                github_token=github_token,
                adi_ref=self._adi_branch)
            self._adi_version = adi_entry.get('adi_version')
            if not self._adi_version:
                raise ArtifactError(
                    "ADI manifest.yaml does not define an ADI version")
            adi_artifact_name = self._find_latest_adi_artifact(
                self._adi_version, auth=self.auth)
            adi_url = os.path.join(DEFAULT_ARTIFACT_URL, adi_artifact_name)
            self._adi_iso = self._find_adi_iso(adi_url, self.auth)
            logger.info(
                f"Resolved ADI ISO from manifest.yaml: ADI {self._adi_version} "
                f"using artifact {adi_artifact_name}")

        if adi_entry:
            self._scos_version = self._get_scos_version(adi_entry)
        if not self._scos_version:
            # Keep the artifact SBOM as a fallback for unreleased entries
            self._scos_version = self._detect_scos_from_artifact(
                adi_url, self.auth)
        if self._scos_version:
            logger.info(f"SCOS version: {self._scos_version}")

        if adi_entry:
            ring_info = adi_entry.get('components', {}).get('ring', {})
            manifest_ring_version = ring_info.get('version', '')
            if manifest_ring_version:
                self._adi_ring_version = self._get_ring_version(
                    manifest_ring_version)

            s3_info = adi_entry.get('components', {}).get('s3c', {})
            manifest_s3_version = s3_info.get('version', '')
            if manifest_s3_version:
                self._adi_s3_version = manifest_s3_version

            # S3 for target version from manifest (when not explicitly provided)
            if not self.s3_artifact and not self._s3_installer:
                self._s3_installer = self._find_s3_from_manifest(adi_entry)

        # Upgrade version — determine the previous ADI entry to upgrade from.
        # Priority: --adi-upgrade-from > manifest history
        prev_entry = None
        if 'upgrade' not in self.jobs and 'upgradeprev' not in self.jobs:
            return

        # Fetch ADI manifest history for upgrades (to find previous versions).
        manifest = self._adi_manifest
        if manifest is None:
            manifest = self._fetch_adi_manifest_history(
                github_token=github_token, adi_ref=self._adi_branch)
            self._adi_manifest = manifest

        if adi_upgrade_from:
            # Explicit ADI version override
            prev_entry = self._find_adi_entry_by_version(
                manifest, adi_upgrade_from)
            if prev_entry:
                logger.info(
                    f"Using explicit --adi-upgrade-from: "
                    f"ADI {adi_upgrade_from}")
            else:
                logger.warning(
                    f"ADI version {adi_upgrade_from} "
                    f"(from --adi-upgrade-from) not found in manifest")
        elif self._adi_version and self._adi_version != UNSUPPORTED:
            # Manifest history: find the entry preceding the current version
            prev_entry = self._find_previous_adi_entry(
                manifest, self._adi_version)
            if prev_entry:
                logger.info(
                    f"Previous ADI version from manifest history: "
                    f"{prev_entry['adi_version']}")
            elif 'upgrade' in self.jobs:
                logger.warning(
                    f"No previous ADI version found in manifest "
                    f"for ADI {self._adi_version}")

        if prev_entry:
            prev_adi_version = prev_entry['adi_version']
            prev_adi_name = self._find_promoted_adi_artifact(
                prev_adi_version, auth=self.auth)
            prev_adi_url = os.path.join(
                DEFAULT_ARTIFACT_URL, prev_adi_name)
            try:
                self._upgrade_adi_iso = self._find_adi_iso(
                    prev_adi_url, self.auth)
                logger.info(
                    f"Resolved upgrade ADI ISO: ADI {prev_adi_version}")
            except ArtifactError:
                logger.warning(
                    f"No ADI ISO found for previous version "
                    f"{prev_adi_version} — upgrade will be skipped")
                self._upgrade_adi_iso = UNSUPPORTED
                return
            self._upgrade_scos_version = self._get_scos_version(prev_entry)
            if self._upgrade_scos_version:
                logger.info(
                    f"Upgrade SCOS version: {self._upgrade_scos_version}")

            # Keep display versions from the previous ADI manifest entry.
            # For scalityos, the workflow upgrades from the previous ADI ISO,
            # so upgrade installers are not auto-resolved here.
            ring_info = prev_entry.get(
                'components', {}).get('ring', {})
            prev_ring_version = ring_info.get('version', '')
            self._upgrade_ring_version_display = prev_ring_version
            s3_info = prev_entry.get(
                'components', {}).get('s3c', {})
            self._upgrade_s3_version_display = s3_info.get('version', '')
            logger.info(
                f"Upgrade-from versions (display): "
                f"RING {self._upgrade_ring_version_display}, "
                f"S3 {self._upgrade_s3_version_display}")

            if self._is_scalityos:
                logger.info(
                    "Skipping upgrade RING/S3 installer lookup for scalityos "
                    "— previous ADI ISO will be used for upgrade")
            else:
                if prev_ring_version:
                    ring_promoted_url = os.path.join(
                        DEFAULT_ARTIFACT_URL,
                        f"{PROMOTED_BUILD}{prev_ring_version}")
                    try:
                        self._ring_upgrade_from = (
                            self._find_latest_stable(
                                ring_promoted_url, self.os_name,
                                prev_ring_version, auth=self.auth))
                    except (ArtifactError, VersionError):
                        logger.warning(
                            f"Could not find RING installer for "
                            f"previous ADI version {prev_adi_version} "
                            f"(RING {prev_ring_version})")
                if not self.s3_artifact and not self._s3_upgrade_from:
                    self._s3_upgrade_from = (
                        self._find_s3_from_manifest(prev_entry))

            self._upgrade_snapshot = self._find_adi_snapshot(
                prev_adi_version,
                nb_nodes=self.nb_nodes,
                snapshot_suffix=self.suffix)

    def as_bash_vars(self, use_snapshots=True, normalize=False, outfile=sys.stdout):
        """Print bash environment variables for this artifact"""

        if not use_snapshots:
            logger.info("Use of snapshots is disabled")
        if normalize:
            logger.info("Normalizing upgradeprev to upgrade")

        u_cmt = "# " if 'upgrade' not in self.jobs else ""
        up_cmt = "# " if 'upgradeprev' not in self.jobs else ""

        if "sbom" in self.jobs:
            # If sbom, we just want installer, skip everything else
            print("# ==== SBOM", file=outfile)
            print(f"INSTALLER_RING={self.ring_installer}", file=outfile)
            print(f"RING_VERSION={self.ring_version}", file=outfile)
        else:
            print("# ==== Install", file=outfile)
            print(f"INSTALLER_RING={self.ring_installer}", file=outfile)
            print(f"INSTALLER_S3={self.s3_installer}", file=outfile)
            print(f"RING_VERSION={self.ring_version}", file=outfile)
            print(f"S3_VERSION={self.s3_version}", file=outfile)

            if self._is_scalityos:
                print(file=outfile)
                print("# ==== ADI (scalityos)", file=outfile)
                print(f"ADI_ISO={self.adi_iso}", file=outfile)
                print(f"ADI_VERSION={self.adi_version}", file=outfile)
                print(f"SCOS_VERSION={self.scos_version}", file=outfile)

            print(file=outfile)
            print(f"# ==== Upgrade {self.upgrade_error_msg}", file=outfile)
            print(f"{u_cmt}UPGRADE_INSTALLER_RING={self.ring_upgrade_from}", file=outfile)
            print(f"{u_cmt}UPGRADE_INSTALLER_S3={self.s3_upgrade_from}", file=outfile)
            print(f"{u_cmt}UPGRADE_RING_VERSION={self.ring_upgrade_from_version}", file=outfile)
            print(f"{u_cmt}UPGRADE_S3_VERSION={self.s3_upgrade_from_version}", file=outfile)
            if use_snapshots:
                print(f"{u_cmt}UPGRADE_FROM_SNAPSHOT={self.upgrade_snapshot}", file=outfile)
            else:
                # Disable snapshots:
                print("# Use of snapshots disabled", file=outfile)
                print(f"{u_cmt}UPGRADE_FROM_SNAPSHOT=", file=outfile)
            if self._is_scalityos:
                print(f"{u_cmt}UPGRADE_ADI_ISO={self.upgrade_adi_iso}", file=outfile)
                print(f"{u_cmt}UPGRADE_SCOS_VERSION={self.upgrade_scos_version}", file=outfile)

            print(file=outfile)
            print(f"# ==== Upgradeprev {self.upgradeprev_error_msg}", file=outfile)
            print(f"{up_cmt}UPGRADEPREV_INSTALLER_RING={self.ring_upgradeprev_from}", file=outfile)
            print(f"{up_cmt}UPGRADEPREV_INSTALLER_S3={self.s3_upgradeprev_from}", file=outfile)
            print(f"{up_cmt}UPGRADEPREV_RING_VERSION={self.ring_upgradeprev_from_version}", file=outfile)
            print(f"{up_cmt}UPGRADEPREV_S3_VERSION={self.s3_upgradeprev_from_version}", file=outfile)
            if use_snapshots:
                print(f"{up_cmt}UPGRADEPREV_FROM_SNAPSHOT={self.upgrade_snapshotprev}", file=outfile)
            else:
                # Disable snapshots:
                print("# Use of snapshots disabled", file=outfile)
                print(f"{up_cmt}UPGRADEPREV_FROM_SNAPSHOT=", file=outfile)
            if self._is_scalityos:
                print(f"{up_cmt}UPGRADEPREV_ADI_ISO={self.upgradeprev_adi_iso}", file=outfile)
                print(f"{up_cmt}UPGRADEPREV_SCOS_VERSION={self.upgradeprev_scos_version}", file=outfile)

            if (not self._is_scalityos
                    and len(self.jobs) == 1
                    and self.jobs[0] == 'upgradeprev'
                    and normalize):
                print(file=outfile)
                print("# ==== Normalize upgradeprev to upgrade", file=outfile)
                print("UPGRADE_INSTALLER_RING=$UPGRADEPREV_INSTALLER_RING", file=outfile)
                print("UPGRADE_INSTALLER_S3=$UPGRADEPREV_INSTALLER_S3", file=outfile)
                print("UPGRADE_RING_VERSION=$UPGRADEPREV_RING_VERSION", file=outfile)
                print("UPGRADE_S3_VERSION=$UPGRADEPREV_S3_VERSION", file=outfile)
                print("UPGRADE_FROM_SNAPSHOT=$UPGRADEPREV_FROM_SNAPSHOT", file=outfile)
                print("unset UPGRADEPREV_INSTALLER_RING", file=outfile)
                print("unset UPGRADEPREV_INSTALLER_S3", file=outfile)
                print("unset UPGRADEPREV_RING_VERSION", file=outfile)
                print("unset UPGRADEPREV_S3_VERSION", file=outfile)
                print("unset UPGRADEPREV_FROM_SNAPSHOT", file=outfile)


def get_options():
    """Parse and return command line arguments."""

    def _fix_os_name(string):
        """Normalize OS name: lowercase and map redhat->rhel.

        The OS minor version (e.g. rhel9.6) is preserved: snapshot selection
        needs it (see ArtiCompute._select_snapshot). Stripping to major-only
        is done later, where a major-only name is required.
        """
        return string.lower().replace('redhat', 'rhel')

    def _check_version(string):
        """Check version format"""
        if not re.match(r'^\d+([.]\d+){2,3}$', string):
            raise argparse.ArgumentTypeError(
                f"Invalid version number '{string}'")
        return string

    parser = argparse.ArgumentParser(
        description='Compute artifact input data for installer tests workflow'
    )

    def _validate_os(os_name):
        """Validate OS name, accepting scalityos variants and an OS minor"""
        os_name = _fix_os_name(os_name)
        major_os, _ = _split_os_minor(os_name)
        if not is_valid_os(major_os):
            raise argparse.ArgumentTypeError(
                f"Invalid OS '{os_name}'."
            )
        return os_name

    parser.add_argument('--os',
                        help=f'Name of the OS ({",".join(OS)} or scalityos[-X.Y[-N]])',
                        type=_validate_os,
                        required=True)
    parser.add_argument('--job-type', choices=JOB_TYPE,
                        help=f'Job to perform ({",".join(JOB_TYPE)}) - all of them if not specified',
                        nargs='+',
                        default=list(JOB_TYPE))
    parser.add_argument('--ring-artifact',
                        help='RING artifact to use',
                        required=True)
    parser.add_argument('--ring-explicit',
                        action='store_true',
                        default=False,
                        help='RING artifact was explicitly provided (not auto-detected)')
    parser.add_argument('--s3-artifact',
                        help='S3 artifact to use')
    parser.add_argument('--adi-artifact',
                        help='ADI artifact to use (scalityos only, '
                             'e.g. github:scality:adi:promoted-0.0.1)')
    parser.add_argument('--auth',
                        help='Authentication credentials (format: username:password)',
                        required=True)
    parser.add_argument('--upgrade-from',
                        dest='upgrade_from_version',
                        help='Version to upgrade from')
    parser.add_argument('--adi-upgrade-from',
                        dest='adi_upgrade_from_version',
                        help='ADI version to upgrade from (scalityos only, '
                             'overrides manifest history lookup)')
    parser.add_argument('--adi-branch',
                        dest='adi_branch',
                        help='ADI git branch/tag/SHA to use for manifest lookups')
    parser.add_argument('--online',
                        dest='offline',
                        action='store_false',
                        default=True,
                        help='Run in online mode (default: offline)')
    parser.add_argument('--ring-architecture',
                        choices=ARCHITECTURE,
                        default=ARCHITECTURE[0],
                        help=f'RING architecture to use (default: {ARCHITECTURE[0]})')
    parser.add_argument('--suffix',
                        default=DEFAULT_SUFFIX,
                        help=f'Snapshot suffix (default: {DEFAULT_SUFFIX})')
    parser.add_argument('--region',
                        default=DEFAULT_REGION,
                        help=f'AWS region to use (default: {DEFAULT_REGION})')
    parser.add_argument('--debug',
                        action='store_true',
                        help='Debug mode')
    parser.add_argument('--quiet',
                        action='store_true',
                        help='Disable logging output')
    parser.add_argument('--normalize',
                        action='store_true',
                        help='Add bash commands to normalize upgradeprev to upgrade (use upgrade variables only)')
    parser.add_argument('--no-snapshots',
                        action='store_false',
                        dest='use_snapshots',
                        help='Disable use of snapshots for upgrades')
    parser.add_argument('--check-tech-train',
                        type=_check_version,
                        metavar='VERSION',
                        help='Check validity of tech train table for given version')
    parser.add_argument('--version-file',
                        help='Path to RING VERSION file (also read at startup via '
                             'RING_VERSION_FILE / GITHUB_WORKSPACE)')
    parser.add_argument('--output-file',
                        help='Write bash variables to this file instead of stdout')

    # Get required actions (hack)
    req_actions = []
    for action in parser._actions:
        if action.required:
            req_actions.append(action)

    # Process --check-tech-train only, without requiring other arguments
    if any(map(lambda a: a.startswith('--check'), sys.argv)):
        for action in req_actions:
            action.required = False
        opts = parser.parse_args()
        if opts.check_tech_train:
            return opts
        for action in req_actions:
            action.required = True

    opts = parser.parse_args()
    opts.job_type = list(set(opts.job_type))    # Remove duplicates

    if opts.quiet:
        # Disable logging
        logger.disabled = True

    if opts.upgrade_from_version and 'upgradeprev' in opts.job_type:
        # In this case, upgradeprev is irrelevant, replace it by upgrade only
        logger.warning("'--upgrade-from' specified, ignoring 'upgradeprev' from job-type")
        opts.job_type = list(
            set(opts.job_type) - set(['upgradeprev']) | set(['upgrade']))

    return opts


if __name__ == "__main__":
    # Quick configuration of logger
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        # '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Log to console
    consoleHandler = logging.StreamHandler()
    consoleHandler.setLevel(logging.INFO)
    consoleHandler.setFormatter(formatter)
    logger.addHandler(consoleHandler)

    try:
        args = get_options()
    except SystemExit:
        sys.exit(1)

    if args.debug:
        logger.setLevel(logging.DEBUG)
        consoleHandler.setLevel(logging.DEBUG)

    try:
        if args.check_tech_train:
            # Check that tech train table has entry for current RING version
            version = ".".join(args.check_tech_train.split('.')[:3])
            key = f"previous-{version}"
            if key not in TECH_TRAIN:
                raise RuntimeError(
                    f"{sys.argv[0]}: missing key '{key}' in TECH_TRAIN table"
                )
            sys.exit(0)

        artifact = ArtiCompute(
            jobs=args.job_type,
            os_name=args.os,
            ring_artifact=args.ring_artifact,
            s3_artifact=args.s3_artifact,
            offline=args.offline,
            auth=args.auth,
            upgrade_from_version=args.upgrade_from_version,
            architecture=args.ring_architecture,
            suffix=args.suffix,
            region=args.region,
            adi_artifact=args.adi_artifact,
            github_token=os.environ.get('GITHUB_TOKEN'),
            ring_explicit=args.ring_explicit,
            adi_upgrade_from_version=args.adi_upgrade_from_version,
            adi_branch=args.adi_branch,
        )
        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as outfile:
                artifact.as_bash_vars(
                    use_snapshots=args.use_snapshots,
                    normalize=args.normalize,
                    outfile=outfile,
                )
        else:
            artifact.as_bash_vars(
                use_snapshots=args.use_snapshots,
                normalize=args.normalize,
            )
    except (ArtifactError, VersionError, SnapshotError, RuntimeError) as err:
        logger.critical(str(err).split(': ', 1)[-1])
        if args.debug:
            raise
        sys.exit(1)
