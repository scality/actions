"""Pytest setup for the arti-compute unit tests.

``arti_compute`` resolves the RING VERSION file at import time (module-level
``_ring_major``), which outside a RING checkout would fail. Point it at the
bundled testdata VERSION before any test module imports it.
"""
import os

os.environ.setdefault(
    'RING_VERSION_FILE',
    os.path.join(os.path.dirname(__file__), 'testdata', 'VERSION'),
)
