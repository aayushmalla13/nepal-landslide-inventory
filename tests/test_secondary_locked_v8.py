"""Integrity checks for the article-level secondary extractor locked test v8."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "outputs"
csv.field_size_limit(50_000_000)


def load_drawer():
    sys.path.insert(0, str(ROOT / "src"))
    path = ROOT / "scripts" / "draw_secondary_locked_v8.py"
    spec = importlib.util.spec_from_file_location("draw_secondary_locked_v8", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def drawer():
    return load_drawer()


@pytest.fixture(scope="module")
def pack(drawer):
    prefix = drawer.VERSION
    return {
        "labels": read(BASE / f"{prefix}_LABEL_HERE.csv"),
        "reading": read(BASE / f"{prefix}_reading_pack.csv"),
        "hidden": read(BASE / f"{prefix}_DO_NOT_OPEN_predictions.csv"),
        "manifest": json.loads((BASE / f"{prefix}_manifest.json").read_text()),
    }


def test_visible_files_hide_predictions_and_strata(pack):
    leaks = {
        "stratum", "inclusion_weight", "strict_v2_predictions",
        "strict_v2_prediction_count", "pipeline_primary_district",
        "pipeline_primary_date", "date_basis",
    }
    assert not (set(pack["labels"][0]) & leaks)
    assert not (set(pack["reading"][0]) & leaks)


def test_truth_columns_begin_empty(pack):
    truth = (
        "primary_district_date_true", "additional_district_dates_true",
        "unresolved_additional_events_true", "annotator", "notes",
    )
    assert all(all(row[column] == "" for column in truth) for row in pack["labels"])


def test_all_files_have_the_same_unique_ordered_rows(pack):
    ids = [row["row_id"] for row in pack["labels"]]
    urls = [row["url"] for row in pack["labels"]]
    assert ids == [row["row_id"] for row in pack["reading"]]
    assert ids == [row["row_id"] for row in pack["hidden"]]
    assert urls == [row["url"] for row in pack["reading"]]
    assert urls == [row["url"] for row in pack["hidden"]]
    assert len(ids) == len(set(ids))
    assert len(urls) == len(set(urls))
    assert all(value.startswith("secv8-") for value in ids)


def test_reading_pack_has_full_article_text(pack):
    assert all(row["article_text"].strip() for row in pack["reading"])


def test_pack_contains_positive_and_negative_prediction_articles(pack):
    counts = [int(row["strict_v2_prediction_count"]) for row in pack["hidden"]]
    assert any(value > 0 for value in counts)
    assert any(value == 0 for value in counts)


def test_manifest_hash_locks_visible_rows(drawer, pack):
    urls = [row["url"] for row in pack["labels"]]
    assert drawer.lock_hash(urls) == pack["manifest"]["lock_hash"]
    path = BASE / f"{drawer.VERSION}_LABEL_HERE.csv"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pack["manifest"]["labels_sha256"]


def test_no_previously_labelled_url_was_drawn(drawer, pack):
    spent, _ = drawer.spent_urls(drawer.prior_label_files(ROOT))
    drawn = {row["url"] for row in pack["labels"]}
    assert not drawn & spent
    assert pack["manifest"]["overlap_with_prior_evaluation"] == 0


def test_weights_equal_population_over_sample(pack):
    for row in pack["hidden"]:
        expected = int(row["stratum_population"]) / int(row["sampled_from_stratum"])
        assert float(row["inclusion_weight"]) == pytest.approx(expected, abs=1e-6)


def test_legacy_candidate_strata_are_a_census(pack):
    manifest = pack["manifest"]
    for language in ("en", "np"):
        key = f"{language}:legacy_candidate"
        assert manifest["sample_by_stratum"].get(key, 0) == manifest["population_by_stratum"][key]


def test_sampling_is_stable(drawer):
    rows = [{"url": f"https://example.test/{index}"} for index in range(20)]
    first = drawer.stable_order(drawer.SEED, "np:ordinary", rows)
    second = drawer.stable_order(drawer.SEED, "np:ordinary", rows)
    assert [row["url"] for row in first] == [row["url"] for row in second]


def test_precision_limitation_is_declared(pack):
    assert "do not use v8 alone" in pack["manifest"]["precision_power_warning"]
    assert pack["manifest"]["strict_v2_positive_claims_in_sample"] < 20
