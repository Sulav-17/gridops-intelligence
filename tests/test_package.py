"""Tests for the GridOps package foundation."""

import gridops


def test_package_import_and_metadata() -> None:
    """The installed package exposes stable initial metadata."""
    assert gridops.__name__ == "gridops"
    assert gridops.__version__ == "0.1.0"
