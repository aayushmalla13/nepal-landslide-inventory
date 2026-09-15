"""The pack that will decide whether the recovered records are usable.

Everything measured so far says the secondary-failure extractor is precise, and
none of it is trustworthy: the only labelled evidence is the 47-article audit
the rules were written from. This pack is the first measurement that could
actually say no.

That makes its integrity worth pinning. The tests below cover the three ways a
labelling pack quietly stops measuring anything: the annotator can see the
answer, the draw is not reproducible, or rows that have already been judged get
judged again.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

csv.field_size_limit(50_000_000)


def load(name: str):
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def drawer():
    return load("draw_secondary_precision_pack")


def read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def pack() -> dict[str, list[dict[str, str]]]:
    base = ROOT / "data" / "outputs"
    return {
        "labels": read(base / "secondary_precision_LABEL_HERE.csv"),
        "reading": read(base / "secondary_precision_reading_pack.csv"),
        "strata": read(base / "secondary_precision_strata.csv"),
    }


# ---------------------------------------------------------------------------
# The annotator must not be shown the answer
# ---------------------------------------------------------------------------


def test_the_label_file_hides_the_extractors_confidence(pack):
    """`date_basis` says whether the extractor had a firm anchor, and the
    stratum says which error family a row was drawn to test. Either would turn
    the labels into agreement with the machine rather than a check on it."""

    columns = set(pack["labels"][0])
    for leak in ("date_basis", "stratum", "inclusion_weight", "conf_date", "firm_date"):
        assert leak not in columns, f"the label file exposes {leak}"


def test_the_reading_pack_hides_it_too(pack):
    columns = set(pack["reading"][0])
    for leak in ("date_basis", "stratum", "inclusion_weight", "conf_date", "firm_date"):
        assert leak not in columns, f"the reading pack exposes {leak}"


def test_the_claim_itself_is_shown(pack):
    """The claim is what is being judged, so it has to be visible -- unlike the
    machine's confidence in it."""

    columns = set(pack["labels"][0])
    assert {"claimed_district", "claimed_date", "evidence_sentence"} <= columns


def test_the_judgement_columns_start_empty(pack):
    for row in pack["labels"]:
        assert row["failure_really_happened_there"] == ""
        assert row["date_is_right"] == ""


# ---------------------------------------------------------------------------
# The three files must describe the same rows
# ---------------------------------------------------------------------------


def test_the_three_files_agree_row_for_row(pack):
    label_ids = [row["row_id"] for row in pack["labels"]]
    assert label_ids == [row["row_id"] for row in pack["reading"]]
    assert label_ids == [row["row_id"] for row in pack["strata"]]


def test_row_ids_are_unique_and_prefixed(drawer, pack):
    ids = [row["row_id"] for row in pack["labels"]]
    assert len(ids) == len(set(ids))
    assert all(row_id.startswith(f"{drawer.ROW_PREFIX}-") for row_id in ids)


def test_every_row_carries_its_evidence_sentence(pack):
    """A claim with no sentence behind it cannot be judged, only guessed at."""

    for row in pack["labels"]:
        assert row["evidence_sentence"].strip(), f"{row['row_id']} has no evidence"


def test_the_reading_pack_carries_article_text(pack):
    """The sentence is what the machine saw; the article is the truth. Without
    the surrounding text the annotator can only re-check the machine's own
    reading of one sentence."""

    empty = [row["row_id"] for row in pack["reading"] if not row["article_text"].strip()]
    assert len(empty) <= len(pack["reading"]) * 0.02, f"articles missing text: {empty[:5]}"


# ---------------------------------------------------------------------------
# The draw must be reproducible and must not re-judge spent rows
# ---------------------------------------------------------------------------


def test_the_row_rng_is_keyed_by_hash_not_by_builtin_hash(drawer):
    """`hash()` is salted per process, so a draw built on it cannot be
    reproduced across runs."""

    first = drawer.row_rng(drawer.SEED, "cross:firm").random()
    second = drawer.row_rng(drawer.SEED, "cross:firm").random()
    assert first == second
    assert drawer.row_rng(drawer.SEED, "cross:soft").random() != first


def test_a_census_leaves_no_sampling_error(pack):
    """Below the census threshold every row is labelled, so the result is the
    precision rather than an estimate of it. A proportional draw was covering
    79% of the population, which buys sampling error for nothing."""

    for row in pack["strata"]:
        assert float(row["inclusion_weight"]) == 1.0


def test_the_pack_is_restricted_to_district_days_the_inventory_lacks(pack):
    """A recovered record that collides with an existing case-day changes
    nothing about the analysis whether it is right or wrong, so labelling it
    would spend the annotator's attention for no measurement."""

    recovered = read(ROOT / "data" / "outputs" / "secondary_failures.csv")
    novel = {
        (row["url"], row["district"], row["event_date_ad"])
        for row in recovered
        if row["already_a_case_day"] == "False"
    }
    for row in pack["strata"]:
        assert (row["url"], row["district"], row["event_date_ad"]) in novel


def test_spent_sets_are_declared_even_when_empty(drawer):
    """The mechanism has to exist before the first pack is labelled, not after:
    re-drawing a judged row would report agreement with an earlier reading as
    if it were fresh evidence."""

    assert hasattr(drawer, "SPENT_SETS")
    assert isinstance(drawer.SPENT_SETS, tuple)


# ---------------------------------------------------------------------------
# Stratification must reflect the error families actually observed
# ---------------------------------------------------------------------------


def test_strata_separate_same_district_from_cross_district(drawer):
    """Same-district recoveries are where re-dating the article's own landslide
    shows up, and they behave differently enough to be reported separately."""

    cross = drawer.stratum_of(
        {"date_basis": "weekday", "district": "Kalikot", "primary_district": "Dailekh"}
    )
    same = drawer.stratum_of(
        {"date_basis": "weekday", "district": "Dailekh", "primary_district": "Dailekh"}
    )
    assert cross.startswith("cross:")
    assert same.startswith("same:")


def test_strata_separate_firm_from_soft_date_anchors(drawer):
    firm = drawer.stratum_of(
        {"date_basis": "explicit_bs_date", "district": "A", "primary_district": "B"}
    )
    soft = drawer.stratum_of(
        {"date_basis": "previous_day", "district": "A", "primary_district": "B"}
    )
    assert firm.endswith(":firm")
    assert soft.endswith(":soft")


def test_the_firm_basis_list_matches_the_extractor(drawer):
    from landslide_inventory.unify.multievent import FIRM_DATE_BASES

    assert drawer.FIRM_BASES == frozenset(FIRM_DATE_BASES)
