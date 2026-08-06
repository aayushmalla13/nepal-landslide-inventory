"""Tests for doctor diagnostics."""

from __future__ import annotations

from landslide_inventory.doctor import run_doctor


def test_doctor_runs_in_minimal_mode(config_file) -> None:
    checks = run_doctor(config_file, minimal=True)
    assert checks
    assert all(check.name != "spacy_model" for check in checks)
    assert any(check.name == "python" for check in checks)
    assert any(check.name == "config" and check.ok for check in checks)
