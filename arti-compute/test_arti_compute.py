"""Unit tests for arti_compute OS-minor-aware snapshot selection (RING-54644)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from arti_compute import ArtiCompute, _split_os_minor   # noqa: E402


RING = "9.5.2.5"
SUFFIX = "GA"


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
