"""Tests for deterministic hashing."""

from __future__ import annotations

from landslide_inventory.utils import stable_hash


def test_stable_hash_is_deterministic() -> None:
    assert stable_hash("district", 1, {"a": 2}) == stable_hash("district", 1, {"a": 2})


def test_stable_hash_changes_with_input() -> None:
    assert stable_hash("district", 1) != stable_hash("district", 2)
