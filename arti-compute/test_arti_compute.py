#!/usr/bin/env python3
"""Pure unit tests for arti_compute.py: upgrade/upgradeprev support matrix,
OS-tuple gating, and OS-minor-aware snapshot selection.

Table-driven, no network / AWS / artifact lookups: instances are built with
``__new__`` and only the attributes the tested helper reads are set, so
``__init__`` never runs, and the snapshot selector is a pure classmethod called
directly. Every OS, version and snapshot is passed explicitly, so the file
is independent of the RING branch the script was taken from.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

import arti_compute as ac                                # noqa: E402
from arti_compute import ArtiCompute, _split_os_minor    # noqa: E402


RING = "9.5.2.5"
SUFFIX = "GA"


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
    ("10.0.0.0", "redhat9.7", "rhel9", "9", True),
    ("10.0.0.0", "redhat9.8", "rhel9", "9", True),
    ("10.0.0.0", "rocky9", "rocky9", "9", True),
    ("10.0.0.0", "scalityos", "scalityos", "9", False),
    ("10.1.0.0", "redhat9.7", "rhel9", "10.0", True),
    ("10.1.0.0", "redhat9.8", "rhel9", "10.0", True),
    ("10.1.0.0", "rocky9", "rocky9", "10.0", True),
    ("10.1.0.0", "scalityos", "scalityos", "10.0", True),
]

# (current_version, raw_os, canonical_os, upgradeprev_from, supported)
# upgradeprev_from is what _get_precedent_major(..., 'previous') resolves to
# via TECH_TRAIN.
# rhel9/rocky9 upgradeprev is refused for a RING 9 target (previous tech-train
# is RING 8, no rhel9/rocky9 image) and allowed for RING >= 10 (previous
# tech-train 9.5.2 is rhel9/rocky9-capable) — see RING-54645 (PR #7045).
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
    ("10.0.0.0", "redhat9.7", "rhel9", "9.5.2", True),
    ("10.0.0.0", "redhat9.8", "rhel9", "9.5.2", True),
    ("10.0.0.0", "rocky9", "rocky9", "9.5.2", True),
    ("10.0.0.0", "scalityos", "scalityos", "9.5.2", False),
    ("10.1.0.0", "redhat9.7", "rhel9", "9.5.2", True),
    ("10.1.0.0", "redhat9.8", "rhel9", "9.5.2", True),
    ("10.1.0.0", "rocky9", "rocky9", "9.5.2", True),
    ("10.1.0.0", "scalityos", "scalityos", "9.5.2", False),
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


def _snap(osver, ring=RING, nodes=3, suffix=SUFFIX, family="redhat"):
    """Build a snapshot platform_name as tagged by installci."""
    return f"RING-{ring}-{family}{osver}-{nodes}nodes[{suffix}]"


def _select(snapshots, os_minor, os_major="9", family="redhat", suffix=SUFFIX):
    return ArtiCompute._select_snapshot(
        snapshots, RING, family, os_major, os_minor, suffix)


class TestSplitOsMinor:
    def test_with_minor(self):
        assert _split_os_minor("rhel9.6") == ("rhel9", "9.6")

    def test_without_minor(self):
        assert _split_os_minor("rhel9") == ("rhel9", None)
        assert _split_os_minor("rocky9") == ("rocky9", None)

    def test_double_digit_major(self):
        assert _split_os_minor("rhel10.2") == ("rhel10", "10.2")

    def test_scalityos_unchanged(self):
        assert _split_os_minor("scalityos-9.7") == ("scalityos-9.7", None)


class TestSelectSnapshot:
    def test_exact_minor(self):
        snaps = [_snap("9.6"), _snap("9.7")]
        assert _select(snaps, "9.6") == _snap("9.6")

    def test_highest_below_target(self):
        # target 9.8, only 9.6/9.7 exist -> highest <= target
        snaps = [_snap("9.6"), _snap("9.7")]
        assert _select(snaps, "9.8") == _snap("9.7")

    def test_no_minor_below_target_returns_none(self):
        # No-match case 1: candidates exist for this (ring, major, suffix) set
        # but none is <= target (target 9.4, only 9.6/9.7). Returns None ->
        # caller falls back to a fresh install-for-upgrade (as before).
        snaps = [_snap("9.6"), _snap("9.7")]
        assert _select(snaps, "9.4") is None

    def test_no_candidates_returns_none(self):
        # No-match case 2: no snapshot at all for this (ring, major, suffix)
        # set (only another major present). Returns None -> fresh install.
        snaps = [_snap("8.10")]
        assert _select(snaps, "9.6", os_major="9") is None
        assert _select(snaps, None, os_major="9") is None

    def test_major_only_target_picks_highest(self):
        snaps = [_snap("9.6"), _snap("9.7")]
        assert _select(snaps, None) == _snap("9.7")

    def test_bare_major_fallback(self):
        # target 9.6: 9.8 too high, bare "9" (minor 0) is the fallback
        snaps = [_snap("9"), _snap("9.8")]
        assert _select(snaps, "9.6") == _snap("9")

    def test_bare_major_only_available(self):
        snaps = [_snap("9")]
        assert _select(snaps, "9.7") == _snap("9")
        assert _select(snaps, None) == _snap("9")

    def test_other_major_ignored(self):
        snaps = [_snap("8.10"), _snap("9.6")]
        assert _select(snaps, "9.6") == _snap("9.6")
        assert _select([_snap("8.10")], "9.6", os_major="9") is None

    def test_suffix_mismatch_ignored(self):
        snaps = [_snap("9.6", suffix="mytest")]
        assert _select(snaps, "9.6", suffix="GA") is None
        assert _select(snaps, "9.6", suffix="mytest") == _snap("9.6", suffix="mytest")

    def test_rocky_family(self):
        snaps = [_snap("9", family="rocky"), _snap("9.6", family="redhat")]
        assert _select(snaps, None, family="rocky") == _snap("9", family="rocky")

    def test_empty(self):
        assert _select([], "9.6") is None
