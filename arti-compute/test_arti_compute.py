#!/usr/bin/env python3
"""Pure unit tests for arti_compute.py: upgrade/upgradeprev support matrix,
OS-tuple gating, and OS-minor-aware snapshot selection.

Table-driven, no network / AWS / artifact lookups: instances are built with
``__new__`` and only the attributes the tested helper reads are set, so
``__init__`` never runs, and the snapshot selector is a pure classmethod called
directly. Every OS, version and snapshot is passed explicitly, so the file
is independent of the RING branch the script was taken from.
"""
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

import arti_compute as ac                                # noqa: E402
from arti_compute import ArtiCompute, _split_os_minor    # noqa: E402


def _ac(os_name, ring_version):
    """Build a minimal ArtiCompute instance without running __init__."""
    obj = ArtiCompute.__new__(ArtiCompute)
    obj.os_name = os_name
    obj._ring_installer = f"scality-ring-{ring_version}.run"
    obj._adi_ring_version = None
    return obj


def _upgrade_supported(os_name, to_version, from_version, is_previous):
    try:
        _ac(os_name, to_version).is_valid_upgrade(
            from_version, is_previous=is_previous)
        return True
    except ac.Unsupported:
        return False


# The workflow passes minor-qualified --os names (redhat8.10, redhat9.7, ...).
# get_options._fix_os_name lowercases and maps redhat->rhel but keeps minor;
# ArtiCompute.__init__ splits it (_split_os_minor) into a major-only os_name
# used for the support decision and an os_minor used for snapshot selection. So
# redhat9.7 and redhat9.8 resolve to rhel9 here; the raw --os input is kept
# in the ``raw_os`` column; the decision uses the canonical major-only name.

# (current_version, raw_os, canonical_os, upgrade_from, supported)
# upgrade_from is what _get_precedent_major(..., 'stable') resolves to.
# scalityos: the live upgrade FROM comes from the ADI manifest (that path is
# skipped for scalityos in __init__); these rows assert the is_valid_upgrade
# rule only.
UPGRADE_MATRIX = [
    ("8.5.12.0", "redhat8.10", "rhel8", "8.5.11", True),
    ("8.5.12.0", "rocky8.10", "rocky8", "8.5.11", True),
    ("8.5.13.0", "redhat8.10", "rhel8", "8.5.12", True),
    ("8.5.13.0", "rocky8.10", "rocky8", "8.5.12", True),
    ("9.5.2.0", "redhat8.10", "rhel8", "9.5.1", True),
    ("9.5.2.0", "redhat9.7", "rhel9", "9.5.1", True),
    ("9.5.2.0", "redhat9.8", "rhel9", "9.5.1", True),
    ("9.5.2.0", "rocky8.10", "rocky8", "9.5.1", True),
    ("9.5.2.0", "rocky9", "rocky9", "9.5.1", True),
    ("9.5.3.0", "redhat8.10", "rhel8", "9.5.2", True),
    ("9.5.3.0", "redhat9.7", "rhel9", "9.5.2", True),
    ("9.5.3.0", "redhat9.8", "rhel9", "9.5.2", True),
    ("9.5.3.0", "rocky8.10", "rocky8", "9.5.2", True),
    ("9.5.3.0", "rocky9", "rocky9", "9.5.2", True),
    ("9.5.4.0", "redhat8.10", "rhel8", "9.5.3", True),
    ("9.5.4.0", "redhat9.7", "rhel9", "9.5.3", True),
    ("9.5.4.0", "redhat9.8", "rhel9", "9.5.3", True),
    ("9.5.4.0", "rocky8.10", "rocky8", "9.5.3", True),
    ("9.5.4.0", "rocky9", "rocky9", "9.5.3", True),
    ("10.0.0.0", "redhat9.7", "rhel9", "9", True),
    ("10.0.0.0", "redhat9.8", "rhel9", "9", True),
    ("10.0.0.0", "rocky9", "rocky9", "9", True),
    ("10.0.0.0", "scalityos", "scalityos", "9", False),
    ("10.1.0.0", "redhat9.7", "rhel9", "10.0", True),
    ("10.1.0.0", "redhat9.8", "rhel9", "10.0", True),
    ("10.1.0.0", "rocky9", "rocky9", "10.0", True),
    ("10.1.0.0", "scalityos", "scalityos", "10.0", True),
    # 10.1.0 is not promoted, so a 10.2.0.0 build upgrades from the last
    # promoted 10.0.x, not from the 10.1 the 'stable' resolution computes.
    ("10.2.0.0", "redhat9.7", "rhel9", "10.0", True),
    ("10.2.0.0", "redhat9.8", "rhel9", "10.0", True),
    ("10.2.0.0", "rocky9", "rocky9", "10.0", True),
    ("10.2.0.0", "scalityos", "scalityos", "10.0", True),
]

# (current_version, raw_os, canonical_os, upgradeprev_from, supported)
# upgradeprev_from is what _get_precedent_major(..., 'previous') resolves to
# via TECH_TRAIN.
# rhel9/rocky9 upgradeprev is refused for a RING 9 target (previous tech-train
# is RING 8, no rhel9/rocky9 image) and allowed for RING >= 10 (previous
# tech-train 9.5.x is rhel9/rocky9-capable) — see RING-54645 (PR #7045).
UPGRADEPREV_MATRIX = [
    ("8.5.12.0", "redhat8.10", "rhel8", "7.4.10", False),
    ("8.5.12.0", "rocky8.10", "rocky8", "7.4.10", False),
    ("8.5.13.0", "redhat8.10", "rhel8", "7.4.10", False),
    ("8.5.13.0", "rocky8.10", "rocky8", "7.4.10", False),
    ("9.5.2.0", "redhat8.10", "rhel8", "8.5.12", True),
    ("9.5.2.0", "redhat9.7", "rhel9", "8.5.12", False),
    ("9.5.2.0", "redhat9.8", "rhel9", "8.5.12", False),
    ("9.5.2.0", "rocky8.10", "rocky8", "8.5.12", True),
    ("9.5.2.0", "rocky9", "rocky9", "8.5.12", False),
    ("9.5.3.0", "redhat8.10", "rhel8", "8.5.12", True),
    ("9.5.3.0", "redhat9.7", "rhel9", "8.5.12", False),
    ("9.5.3.0", "redhat9.8", "rhel9", "8.5.12", False),
    ("9.5.3.0", "rocky8.10", "rocky8", "8.5.12", True),
    ("9.5.3.0", "rocky9", "rocky9", "8.5.12", False),
    ("9.5.4.0", "redhat8.10", "rhel8", "8.5.12", True),
    ("9.5.4.0", "redhat9.7", "rhel9", "8.5.12", False),
    ("9.5.4.0", "redhat9.8", "rhel9", "8.5.12", False),
    ("9.5.4.0", "rocky8.10", "rocky8", "8.5.12", True),
    ("9.5.4.0", "rocky9", "rocky9", "8.5.12", False),
    ("10.0.0.0", "redhat9.7", "rhel9", "9.5.2", True),
    ("10.0.0.0", "redhat9.8", "rhel9", "9.5.2", True),
    ("10.0.0.0", "rocky9", "rocky9", "9.5.2", True),
    ("10.0.0.0", "scalityos", "scalityos", "9.5.2", False),
    ("10.1.0.0", "redhat9.7", "rhel9", "9.5.3", True),
    ("10.1.0.0", "redhat9.8", "rhel9", "9.5.3", True),
    ("10.1.0.0", "rocky9", "rocky9", "9.5.3", True),
    ("10.1.0.0", "scalityos", "scalityos", "9.5.3", False),
    ("10.2.0.0", "redhat9.7", "rhel9", "9.5.3", True),
    ("10.2.0.0", "redhat9.8", "rhel9", "9.5.3", True),
    ("10.2.0.0", "rocky9", "rocky9", "9.5.3", True),
    ("10.2.0.0", "scalityos", "scalityos", "9.5.3", False),
]


@pytest.mark.parametrize(
    "current,raw_os,canonical,upgrade_from,supported", UPGRADE_MATRIX,
    ids=[f"{c}-{o}" for c, o, _, _, _ in UPGRADE_MATRIX])
def test_upgrade_matrix(current, raw_os, canonical, upgrade_from, supported):
    assert _upgrade_supported(
        canonical, current, upgrade_from, is_previous=False) is supported


@pytest.mark.parametrize(
    "current,raw_os,canonical,upgradeprev_from,supported", UPGRADEPREV_MATRIX,
    ids=[f"{c}-{o}" for c, o, _, _, _ in UPGRADEPREV_MATRIX])
def test_upgradeprev_matrix(current, raw_os, canonical, upgradeprev_from,
                            supported):
    assert _upgrade_supported(
        canonical, current, upgradeprev_from, is_previous=True) is supported


# OS tuple is built from _ring_major; assert each OS's membership against the
# _ring_major resolved at import (testdata/VERSION via conftest.py) so this
# stays correct whichever RING version the action is pinned to.
@pytest.mark.parametrize("os_name,expected_present", [
    ("rhel9", ac._ring_major > 8),
    ("rocky9", ac._ring_major > 8),
    ("scalityos", ac._ring_major > 9),
    ("rhel8", ac._ring_major < 10),
    ("rocky8", ac._ring_major < 10),
])
def test_os_tuple_gating(os_name, expected_present):
    assert (os_name in ac.OS) is expected_present


SPLIT_OS_MINOR_CASES = [
    ("rhel9.6", ("rhel9", "9.6")),
    ("rhel9", ("rhel9", None)),
    ("rocky9", ("rocky9", None)),
    ("rocky8.10", ("rocky8", "8.10")),
    # double-digit major: the minor must not swallow the major's second digit
    ("rhel10.2", ("rhel10", "10.2")),
    ("scalityos-9.7", ("scalityos-9.7", None)),
]


@pytest.mark.parametrize("os_name,expected", SPLIT_OS_MINOR_CASES,
                         ids=[c[0] for c in SPLIT_OS_MINOR_CASES])
def test_split_os_minor(os_name, expected):
    assert _split_os_minor(os_name) == expected


# Real platform_name snapshot tags (from live AWS). Bare-major tags (redhat9,
# rocky9) count as minor 0; two non-GA redhat9.6 tags test suffix filtering.
SNAPSHOTS = [
    "RING-9.5.2.6-redhat8-3nodes[GA]",
    "RING-9.5.2.6-redhat9-3nodes[GA]",
    "RING-9.5.2.6-redhat9.6-3nodes[GA]",
    "RING-9.5.2.6-redhat9.6-3nodes[9.5.2.6_pw1]",
    "RING-9.5.2.6-redhat9.6-3nodes[redhat96-test]",
    "RING-9.5.2.6-rocky8-3nodes[GA]",
    "RING-9.5.2.6-rocky9-3nodes[GA]",
    "RING-10.0.0.0-redhat9.6-3nodes[GA]",
    "RING-10.0.0.0-redhat9.7-3nodes[GA]",
    "RING-10.1.0.0-redhat9.7-3nodes[GA]",
    "RING-10.1.0.0-redhat9.8-3nodes[GA]",
]

# The trailing "9.9" is a middle segment: the anchored regex must read osver as
# the bare major (minor 0), never 9.9.
ANCHOR_SNAPSHOTS = [
    "RING-9.5.2.6-redhat9-3nodes-extra-redhat9.9[GA]",
    "RING-9.5.2.6-redhat9.5-3nodes[GA]",
]

# Only another major is present, so a major-9 request has no candidate at all.
OTHER_MAJOR_ONLY = ["RING-9.5.2.6-redhat8.10-3nodes[GA]"]

# Only a bare-major tag is present (minor 0).
BARE_MAJOR_ONLY = ["RING-9.5.2.6-redhat9-3nodes[GA]"]

# (id, snapshots, ring_version, family, major, minor, suffix, expected)
# minor is the full 'major.minor' or None; family is 'redhat', not 'rhel'.
SELECT_SNAPSHOT_CASES = [
    ("exact-minor", SNAPSHOTS, "10.0.0.0", "redhat", "9", "9.7", "GA",
     "RING-10.0.0.0-redhat9.7-3nodes[GA]"),
    # real CI anchor: 9.8 requested, highest available is 9.6
    ("highest-below-target", SNAPSHOTS, "9.5.2.6", "redhat", "9", "9.8", "GA",
     "RING-9.5.2.6-redhat9.6-3nodes[GA]"),
    ("never-higher-minor", SNAPSHOTS, "10.1.0.0", "redhat", "9", "9.6", "GA",
     None),
    ("major-only-highest", SNAPSHOTS, "10.1.0.0", "redhat", "9", None, "GA",
     "RING-10.1.0.0-redhat9.8-3nodes[GA]"),
    ("bare-major-minor0-fallback", SNAPSHOTS, "9.5.2.6", "redhat", "9", "9.5",
     "GA", "RING-9.5.2.6-redhat9-3nodes[GA]"),
    ("bare-major-rocky", SNAPSHOTS, "9.5.2.6", "rocky", "9", "9.9", "GA",
     "RING-9.5.2.6-rocky9-3nodes[GA]"),
    ("other-major-isolated", SNAPSHOTS, "9.5.2.6", "redhat", "8", "8.10", "GA",
     "RING-9.5.2.6-redhat8-3nodes[GA]"),
    ("suffix-mismatch-ignored", SNAPSHOTS, "9.5.2.6", "redhat", "9", "9.6",
     "GA", "RING-9.5.2.6-redhat9.6-3nodes[GA]"),
    ("wrong-ring-version", SNAPSHOTS, "9.9.9.9", "redhat", "9", "9.9", "GA",
     None),
    ("family-mismatch", SNAPSHOTS, "9.5.2.6", "redhat", "9", None, "GA",
     "RING-9.5.2.6-redhat9.6-3nodes[GA]"),
    ("empty-list", [], "9.5.2.6", "redhat", "9", "9.6", "GA", None),
    ("anchoring", ANCHOR_SNAPSHOTS, "9.5.2.6", "redhat", "9", "9.9", "GA",
     "RING-9.5.2.6-redhat9.5-3nodes[GA]"),
    # No candidate for the requested major at all -> None, both with and
    # without a requested minor (caller falls back to a fresh install).
    ("no-candidate-for-major", OTHER_MAJOR_ONLY, "9.5.2.6", "redhat", "9",
     "9.6", "GA", None),
    ("no-candidate-for-major-no-minor", OTHER_MAJOR_ONLY, "9.5.2.6", "redhat",
     "9", None, "GA", None),
    # Bare major is the only tag: eligible for a minor request and for a
    # major-only request alike.
    ("bare-major-only-with-minor", BARE_MAJOR_ONLY, "9.5.2.6", "redhat", "9",
     "9.7", "GA", "RING-9.5.2.6-redhat9-3nodes[GA]"),
    ("bare-major-only-no-minor", BARE_MAJOR_ONLY, "9.5.2.6", "redhat", "9",
     None, "GA", "RING-9.5.2.6-redhat9-3nodes[GA]"),
    # Requested suffix matches nothing -> None.
    ("suffix-matches-nothing", SNAPSHOTS, "9.5.2.6", "redhat", "9", "9.6",
     "no-such-suffix", None),
]


@pytest.mark.parametrize(
    "snapshots,ring_version,family,major,minor,suffix,expected",
    [c[1:] for c in SELECT_SNAPSHOT_CASES],
    ids=[c[0] for c in SELECT_SNAPSHOT_CASES])
def test_select_snapshot(snapshots, ring_version, family, major, minor, suffix,
                         expected):
    assert ArtiCompute._select_snapshot(
        snapshots, ring_version, family, major, minor, suffix) == expected


# Install thresholds (is_valid): lowest supported RING version per OS.
INSTALL_THRESHOLDS = [
    ("rhel8", "8.5.1.0", False),
    ("rhel8", "8.5.2.0", True),
    ("rocky8", "8.5.3.0", False),
    ("rocky8", "8.5.4.0", True),
    ("rhel9", "9.2.0.0", False),
    ("rhel9", "9.3.0.0", True),
    ("rocky9", "9.3.0.0", False),
    ("rocky9", "9.4.0.0", True),
    ("scalityos", "9.5.0.0", False),
    ("scalityos", "10.0.0.0", True),
]


@pytest.mark.parametrize("os_name,version,supported", INSTALL_THRESHOLDS,
                         ids=[f"{o}-{v}" for o, v, _ in INSTALL_THRESHOLDS])
def test_install_thresholds(os_name, version, supported):
    obj = _ac(os_name, version)
    if supported:
        obj.is_valid(os_name, version)
    else:
        with pytest.raises(ac.Unsupported):
            obj.is_valid(os_name, version)


# Upgrade target thresholds: lowest target version each OS may upgrade to.
# FROM equals the target so FROM stays valid and only the target is tested.
UPGRADE_TARGET_THRESHOLDS = [
    ("rhel8", "8.5.2.0", False),
    ("rhel8", "8.5.3.0", True),
    ("rocky8", "8.5.3.0", False),
    ("rocky8", "8.5.4.0", True),
    ("rhel9", "9.2.0.0", False),
    ("rhel9", "9.3.0.0", True),
    ("rocky9", "9.3.0.0", False),
    ("rocky9", "9.4.0.0", True),
]


@pytest.mark.parametrize("os_name,to_version,supported", UPGRADE_TARGET_THRESHOLDS,
                         ids=[f"{o}-{v}" for o, v, _ in UPGRADE_TARGET_THRESHOLDS])
def test_upgrade_target_thresholds(os_name, to_version, supported):
    assert _upgrade_supported(
        os_name, to_version, to_version, is_previous=False) is supported


def test_upgrade_target_below_ring8_unsupported():
    assert _upgrade_supported(
        "rhel8", "7.4.10.0", "7.4.9", is_previous=False) is False


# rhel8/rocky8 upgradeprev FROM threshold. NOTE: the code cutoff is 8.0.0.0
# (the message text says "9.0.0.0"); FROM below RING 8 is refused, RING 8+ ok.
@pytest.mark.parametrize("os_name", ["rhel8", "rocky8"])
@pytest.mark.parametrize("from_version,supported", [
    ("7.4.10", False),
    ("8.0.0.0", True),
    ("9.0.0.0", True),
])
def test_rhel8_rocky8_upgradeprev_from_threshold(os_name, from_version,
                                                 supported):
    # Target 9.5.3.0 keeps the target threshold satisfied for both OSes.
    assert _upgrade_supported(
        os_name, "9.5.3.0", from_version, is_previous=True) is supported


# scalityos is_valid_upgrade rule (live FROM is manifest-driven, not tested):
# upgrade needs FROM >= 10.0.0.0; upgradeprev is always refused.
@pytest.mark.parametrize("from_version,is_previous,supported", [
    ("9.5.2.0", False, False),
    ("10.0.0.0", False, True),
    ("10.0.0.0", True, False),
    ("9.5.2.0", True, False),
])
def test_scalityos_upgrade_rule(from_version, is_previous, supported):
    assert _upgrade_supported(
        "scalityos", "10.1.0.0", from_version, is_previous) is supported


# _get_precedent_major, 'stable': precedent in the same tech-train (decrement
# after dropping trailing zeros).
@pytest.mark.parametrize("from_string,expected", [
    ("scality-ring-8.5.13.0.run", "8.5.12"),
    ("scality-ring-8.5.12.0.run", "8.5.11"),
    ("scality-ring-9.5.4.0.run", "9.5.3"),
    ("scality-ring-9.5.3.0.run", "9.5.2"),
    ("scality-ring-9.5.2.0.run", "9.5.1"),
    ("scality-ring-10.2.0.0.run", "10.1"),
    ("scality-ring-10.1.0.0.run", "10.0"),
    ("scality-ring-10.0.0.0.run", "9"),
    ("10.0.0.1", "10.0.0.0"),
])
def test_get_precedent_major_stable(from_string, expected):
    assert ArtiCompute._get_precedent_major(
        from_string, version_type="stable") == expected


# _get_precedent_major, 'previous': previous tech-train via TECH_TRAIN.
@pytest.mark.parametrize("from_string,expected", [
    ("scality-ring-8.5.13.0.run", "7.4.10"),
    ("scality-ring-9.5.3.0.run", "8.5.12"),
    ("scality-ring-9.5.4.0.run", "8.5.12"),
    ("scality-ring-10.2.0.0.run", "9.5.3"),
    ("scality-ring-10.1.0.0.run", "9.5.3"),
    ("scality-ring-10.0.0.0.run", "9.5.2"),
])
def test_get_precedent_major_previous(from_string, expected):
    assert ArtiCompute._get_precedent_major(
        from_string, version_type="previous") == expected


# TECH_TRAIN must have an entry for each active current version.
@pytest.mark.parametrize("current", ["8.5.13", "9.5.4", "10.1.0", "10.2.0"])
def test_tech_train_has_key_for_current_versions(current):
    assert f"previous-{current}" in ac.TECH_TRAIN


def test_tech_train_missing_key_raises():
    with pytest.raises(RuntimeError):
        ArtiCompute._get_precedent_major(
            "scality-ring-9.9.9.0.run", version_type="previous")


# Offline installer of a RING installer: generated by offline-generator.yaml
# for a run whose build is not the build of the RING installer.
@pytest.mark.parametrize("os_name, os_minor, dist", [
    ("rhel8", "8.10", "rhel8.10"),
    ("rocky8", "8.10", "rocky8.10"),
    ("rhel9", "9.7", "rhel9.7"),
    ("rocky9", None, "rocky9"),
])
def test_get_offline_dist(os_name, os_minor, dist):
    assert ArtiCompute._get_offline_dist(os_name, os_minor) == dist


RING_BUILD = "github:scality:ring:promoted-8.5.13.0_rc1"
RING_INSTALLER = (f"{ac.DEFAULT_ARTIFACT_URL}/{RING_BUILD}/installer/"
                  "scality-ring-8.5.13.0.r251104123456.0c137f79fd_rocky_8.run")
OFFLINE_ID = "8.5.13.0.r251104123456.0c137f79fd"
NEW_RELEASE_BUILD = "github:scality:ring:staging-0c137f79fd.New-release.881"
OTHER_COMMIT_BUILD = "github:scality:ring:staging-a13b1276ab.Installer-tests.5745"


def _offline(dist, stamp="202611041200", offline_id=OFFLINE_ID):
    return f"offline_installers/scality-ring-offline-{offline_id}_{dist}_{stamp}.run"


@pytest.fixture
def builds(monkeypatch):
    """Fake artifacts store: build name -> file list ('' lists the builds)."""
    store = {"": [f"{RING_BUILD}/", f"{NEW_RELEASE_BUILD}/", f"{OTHER_COMMIT_BUILD}/"]}
    calls = []

    def _list_build(build, auth=None):
        calls.append(build)
        return tuple(store.get(build, ()))

    monkeypatch.setattr(ArtiCompute, "_list_build", staticmethod(_list_build))
    store["calls"] = calls
    return store


def _find(os_name="rocky8", os_minor="8.10", extra=()):
    return ArtiCompute._find_offline_installer(
        RING_INSTALLER, os_name, os_minor, builds=[*extra, RING_BUILD])


def test_find_offline_in_commit_build(builds):
    builds[NEW_RELEASE_BUILD] = [_offline("rhel8.10"), _offline("rocky8.10")]
    assert _find() == f"{ac.DEFAULT_ARTIFACT_URL}/{NEW_RELEASE_BUILD}/{_offline('rocky8.10')}"


def test_find_offline_given_build_first(builds):
    # The generator of another commit: only found when given
    builds[OTHER_COMMIT_BUILD] = [_offline("rocky8.10", "202611051200")]
    builds[NEW_RELEASE_BUILD] = [_offline("rocky8.10")]
    assert _find(extra=[OTHER_COMMIT_BUILD]).startswith(f"{ac.DEFAULT_ARTIFACT_URL}/{OTHER_COMMIT_BUILD}/")
    # Found in a given build: the 0.5 MB list of all the builds is not read
    assert "" not in builds["calls"]


def test_find_offline_most_recent(builds):
    builds[NEW_RELEASE_BUILD] = [_offline("rocky8.10", "202611051200"), _offline("rocky8.10", "202611041200")]
    assert _find().endswith("_202611051200.run")


@pytest.mark.parametrize("name", [
    _offline("rocky8.10", offline_id="8.5.13.0.r251104123456.a13b1276ab"),    # other commit
    _offline("rocky8.10", offline_id="8.5.12.0.r251104123456.0c137f79fd"),    # other version
    _offline("rocky8.10", offline_id="8.5.13.0.r251104000000.0c137f79fd"),    # other revision
    _offline("rhel8.10"),                                                     # other dist
    _offline("rocky8.10", stamp="latest"),                                    # symlink name
    "offline_installers/scality-ring-offline-8.5.13.0.r251104123456.0c137f79fd_rhel_8.run",  # installci name
])
def test_find_offline_no_match(builds, name):
    builds[NEW_RELEASE_BUILD] = [name]
    assert _find() is None


def test_find_offline_bad_installer_name(builds):
    assert ArtiCompute._find_offline_installer("scality-ring-latest.run", "rocky8", "8.10") is None


def _offline_ac(os_name, ring_installer, offline_ring):
    """Build a minimal ArtiCompute for find_offline_installers()."""
    obj = ArtiCompute.__new__(ArtiCompute)
    obj.os_name, obj.os_minor = _split_os_minor(os_name)
    obj._is_scalityos = ac.is_scality_managed_os(obj.os_name)
    obj._ring_installer = ring_installer
    obj._offline_ring = offline_ring
    return obj


def test_find_offline_installers(monkeypatch):
    results = {
        "rhel8.10": _offline_ac("rhel8.10", RING_INSTALLER, "https://x/offline-rhel8.10.run"),
        "rocky8.10": _offline_ac("rocky8.10", RING_INSTALLER, None),
        "rhel9.7": _offline_ac("rhel9.7", ac.UNSUPPORTED, None),
        "scalityos": _offline_ac("scalityos", RING_INSTALLER, None),
    }
    monkeypatch.setattr(ac, "ArtiCompute", lambda jobs, os_name, **kwargs: results[os_name])
    out = io.StringIO()
    # The map keys are the OS names as given (redhat), not the normalized ones (rhel)
    os_names = [("redhat8.10", "rhel8.10"), ("rocky8.10", "rocky8.10"),
                ("redhat9.7", "rhel9.7"), ("scalityos", "scalityos")]
    ac.find_offline_installers(os_names, outfile=out)
    assert out.getvalue().splitlines()[1:] == [
        """OFFLINE_INSTALLERS='{"redhat8.10":"https://x/offline-rhel8.10.run"}'""",
        "OFFLINE_MISSING_DISTS='rocky8.10'",
    ]


def test_offline_job_type_skips_the_other_lookups(monkeypatch):
    """--job-type offline: only the RING installer and its offline installer."""
    monkeypatch.setattr(ArtiCompute, "_find_ring_installer", classmethod(lambda cls, *a, **k: (RING_INSTALLER, None)))
    monkeypatch.setattr(ArtiCompute, "_find_offline_installer", classmethod(lambda cls, *a, **k: "https://x/o.run"))

    def _no_s3(*args, **kwargs):
        raise AssertionError("S3 lookup with --job-type offline")

    monkeypatch.setattr(ArtiCompute, "_find_latest_s3_installer", classmethod(_no_s3))
    obj = ArtiCompute(jobs=[ac.OFFLINE_JOB_TYPE], os_name="rocky9", ring_artifact=RING_BUILD,
                      s3_artifact=None, offline=True, auth=None)
    assert obj.offline_ring == "https://x/o.run"


@pytest.mark.parametrize("argv, error", [
    (["--job-type", "offline", "install"], "cannot be used with other job types"),
    (["--job-type", "install", "--os", "rocky9", "rhel9"], "several --os need"),
    (["--job-type", "install", "--offline-build", "b"], "--offline-build needs"),
    (["--job-type", "offline", "--os", "rhel7"], "Invalid OS"),
])
def test_offline_options_errors(monkeypatch, capsys, argv, error):
    base = ["arti_compute.py", "--ring-artifact", RING_BUILD, "--auth", "u:p"]
    if "--os" not in argv:
        argv = [*argv, "--os", "rocky9"]
    monkeypatch.setattr(sys, "argv", [*base, *argv])
    with pytest.raises(SystemExit):
        ac.get_options()
    assert error in capsys.readouterr().err


def test_offline_options_keep_the_os_names(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["arti_compute.py", "--ring-artifact", RING_BUILD, "--auth", "u:p",
                                      "--job-type", "offline", "--os", "Redhat9.7", "rocky9"])
    opts = ac.get_options()
    assert opts.os_names == ["redhat9.7", "rocky9"]
    assert opts.os == ["rhel9.7", "rocky9"]
