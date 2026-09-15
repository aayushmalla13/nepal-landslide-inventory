"""The granularity development pack must be drawable, clean, and human-unspent.

Granularity is the biggest lever on article-level precision, and the project has
no trustworthy labels for it: locked v7 is spent, and development_set_v1's
granularity labels are model-produced and unreliable for this field (28/22 split
on the pipeline's own documented road-obstruction rule). So a new human-labelled
development set is the next step, and these tests pin the properties that make
it worth someone's afternoon.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "data" / "outputs"


def load(name: str):
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


PACK = OUTPUTS / "granularity_development_LABEL_HERE.csv"
READING = OUTPUTS / "granularity_development_reading_pack.csv"
PREDICTIONS = OUTPUTS / "granularity_development_predictions.csv"
MANIFEST = OUTPUTS / "granularity_development_manifest.json"

pytestmark = pytest.mark.skipif(
    not PACK.exists(), reason="granularity pack not drawn in this checkout"
)


def test_no_article_in_the_pack_had_human_truth_labels_before_it_was_drawn() -> None:
    """Reusing human truth labels would waste annotation and bias the result.

    The pack's own completed labels are excluded from the comparison: this pack
    has since been labelled and so appears in SPENT_SETS itself, which is what
    keeps the *next* pack away from it.
    """

    drawer = load("draw_granularity_development_set")
    own = "granularity_development_COMPLETED.csv"
    earlier = [ROOT / path for path in drawer.SPENT_SETS if not path.endswith(own)]
    spent = drawer.spent_urls(earlier)
    assert spent, "the earlier labelled sets should not all be missing"
    drawn = {row["url"] for row in read(PACK)}
    assert not (drawn & spent), f"{len(drawn & spent)} previously labelled articles were drawn"


def test_the_pack_does_not_reveal_the_pipeline_prediction() -> None:
    """Anchoring the annotator on the answer defeats the purpose of the set."""

    columns = set(read(PACK)[0])
    assert "predicted_granularity" not in columns
    assert not any("pred" in column for column in columns), columns
    # It must still be recoverable for scoring, from a separate file.
    assert PREDICTIONS.exists()
    assert "predicted_granularity" in read(PREDICTIONS)[0]


def test_every_row_is_joinable_to_its_text_and_its_prediction() -> None:
    pack = {row["row_id"] for row in read(PACK)}
    assert pack == {row["row_id"] for row in read(READING)}
    assert pack == {row["row_id"] for row in read(PREDICTIONS)}


def test_the_reading_pack_carries_real_article_text() -> None:
    """The annotator must never need to open a URL."""

    rows = read(READING)
    empty = [row["row_id"] for row in rows if len(row["article_text"].strip()) < 50]
    assert len(empty) <= len(rows) // 20, f"{len(empty)} rows have almost no text"


def test_the_label_columns_are_present_and_empty() -> None:
    rows = read(PACK)
    for column in (
        "event_granularity_true",
        "is_landslide_event_true",
        "in_nepal_true",
        "annotator",
    ):
        assert column in rows[0], column
        assert all(not row[column].strip() for row in rows), f"{column} is pre-filled"


def test_the_strata_are_balanced_across_predicted_granularity() -> None:
    """A sample proportional to the population would barely contain multi rows.

    Class 1 is 100% predicted `single` by construction, so drawing from class 1
    alone gives no contrast at all -- the first version of this pack made
    exactly that mistake and produced two strata instead of six.
    """

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    drawn = manifest["drawn_per_stratum"]
    assert len(drawn) == 6, drawn
    assert {key.split(":")[1] for key in drawn} == {"single", "multi", "roundup"}
    assert {key.split(":")[0] for key in drawn} == {"en", "np"}
    counts = set(drawn.values())
    assert counts == {manifest["per_stratum"]}, drawn
    assert "1" in manifest["classes_drawn_from"] and "2" in manifest["classes_drawn_from"]


def test_the_manifest_records_why_the_model_labelled_set_was_not_reused() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reason = manifest["why_development_set_v1_is_not_used"].lower()
    assert "model" in reason
    assert manifest["excluded_previously_labelled_urls"] > 0


def test_any_v6_overlap_is_model_labelled_not_prior_human_truth() -> None:
    """v6 cannot be represented as an independent human reference set.

    A post-draw audit found exact-URL overlaps with v6. That set was labelled
    entirely by a model and its answers were not exposed in either human pack,
    so the overlap does not leak a human target. This assertion prevents that
    provenance distinction from being silently lost.
    """

    v6_path = OUTPUTS / "locked_test_set_v6_labels_final.csv"
    if not v6_path.exists():
        pytest.skip("v6 labels absent in this checkout")
    v6_rows = read(v6_path)
    assert v6_rows
    assert {row["annotator"] for row in v6_rows} == {"gpt-5.6-sol"}

    v6_urls = {row["url"] for row in v6_rows}
    for pack, manifest_path in ((PACK, MANIFEST), (C1_PACK, C1_MANIFEST)):
        if pack.exists():
            overlap = {row["url"] for row in read(pack)} & v6_urls
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            audited = manifest["post_draw_disjointness_audit"]
            assert len(overlap) == audited["model_label_overlap_rows"]
            assert audited["human_truth_overlap_rows"] == 0


def test_drawing_is_deterministic_under_the_recorded_seed() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    import hashlib

    digest = hashlib.sha256(PACK.read_bytes()).hexdigest()
    assert digest == manifest["label_file_sha256"], (
        "the pack on disk does not match its manifest; it was edited or redrawn"
    )


# ---------------------------------------------------------------------------
# The measured facts the diagnosis rests on
# ---------------------------------------------------------------------------


def test_the_body_signal_looks_harmful_on_the_MODEL_labelled_set() -> None:
    """Records a negative result that LATER TURNED OUT TO BE AN ARTEFACT.

    On development_set_v1 -- annotated by a language model -- treating a
    whole-body multi-event pattern as evidence of plurality gains 9 multi
    articles and wrongly flips 15 single ones. On that evidence the idea was
    rejected.

    The human-labelled class-1 pack reverses it. On the population that
    actually matters -- the 3,110 articles the pipeline KEEPS -- the same
    signal reclassifies 394 articles correctly against 174 wrongly (2.27:1),
    lifting weighted granularity accuracy from 0.585 to 0.675, a change of
    +0.090 with a stratified bootstrap 95% CI of [+0.037, +0.137].

    Both facts are kept, and this test pins only the first: it asserts what the
    MODEL-labelled set says, and exists now as evidence of how badly that set
    misleads on this field. See test_the_body_signal_helps_on_the_HUMAN_labelled_set
    for the measurement that should drive any decision.
    """

    corpus_path = ROOT / "data" / "corpus" / "corpus_for_extraction.csv.gz"
    labels_path = OUTPUTS / "development_set_v1_labels_final.csv"
    if not (corpus_path.exists() and labels_path.exists()):
        pytest.skip("corpus or development labels absent in this checkout")

    import gzip

    csv.field_size_limit(50_000_000)
    sys.path.insert(0, str(ROOT / "src"))
    from landslide_inventory.unify import event_typing as typing_module

    with gzip.open(corpus_path, "rt", encoding="utf-8", newline="") as handle:
        corpus = {row["url"]: row for row in csv.DictReader(handle)}

    gained = flipped = 0
    for row in read(labels_path):
        truth = (row.get("event_granularity_true") or "").strip()
        article = corpus.get(row["url"])
        if article is None or truth not in {"single", "multi"}:
            continue
        body = article.get("text") or ""
        predicted = typing_module.classify_event_granularity(article.get("title"), body)
        whole_body_hit = bool(
            typing_module.MULTI_EVENT_PATTERN.search(body)
            or typing_module.MULTI_ADMIN_PATTERN.search(body)
        )
        if truth == "multi" and predicted == "single" and whole_body_hit:
            gained += 1
        if truth == "single" and whole_body_hit:
            flipped += 1

    assert flipped > gained, (
        f"on the model-labelled set the signal gains {gained} and wrongly flips "
        f"{flipped}; if this ever reverses, the model labels changed, not the world"
    )


# ---------------------------------------------------------------------------
# The class-1 pack
#
# v7's precision loss lives in one cell: articles the pipeline KEPT that are
# truly multi. The first pack could not reach it -- class 1 is 100% predicted
# `single` by construction, so stratifying by the prediction puts almost no
# class-1 rows in the sample (17 of 120). This pack samples class 1 only, and
# enriches on a body-level multi signal so the rare true-multi articles are
# actually present. The enrichment is undone by inclusion weights.
# ---------------------------------------------------------------------------

C1_PACK = OUTPUTS / "granularity_class1_LABEL_HERE.csv"
C1_PREDICTIONS = OUTPUTS / "granularity_class1_predictions.csv"
C1_MANIFEST = OUTPUTS / "granularity_class1_manifest.json"

c1_only = pytest.mark.skipif(
    not C1_PACK.exists(), reason="class-1 pack not drawn in this checkout"
)


@c1_only
def test_the_class1_pack_contains_only_kept_class1_articles() -> None:
    rows = read(C1_PREDICTIONS)
    assert {row["pipeline_class"] for row in rows} == {"1"}, (
        "a non-class-1 article would not be in the population where the false "
        "positives live"
    )


@c1_only
def test_every_class1_row_is_predicted_single_by_construction() -> None:
    """If this ever fails, the class-1 gate has changed and the design needs revisiting."""

    assert {row["predicted_granularity"] for row in read(C1_PREDICTIONS)} == {"single"}


@c1_only
def test_inclusion_weights_reconstruct_the_stratum_populations() -> None:
    """Without correct weights the enriched sample's multi rate is not the inventory's."""

    rows = read(C1_PREDICTIONS)
    manifest = json.loads(C1_MANIFEST.read_text(encoding="utf-8"))
    drawn = Counter(row["stratum"] for row in rows)
    for stratum, count in drawn.items():
        population = manifest["strata"][stratum]
        weight = float(next(r for r in rows if r["stratum"] == stratum)["inclusion_weight"])
        assert weight == pytest.approx(population / count, rel=1e-3), stratum
        # Each row stands for `weight` articles; the stratum must sum to its size.
        assert count * weight == pytest.approx(population, rel=1e-3)


@c1_only
def test_the_enrichment_actually_enriches_and_is_disclosed() -> None:
    manifest = json.loads(C1_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["stratify_by"] == "body_signal"
    strata = manifest["strata"]
    signal = sum(v for k, v in strata.items() if k.endswith(":signal"))
    total = sum(strata.values())
    # Signal-bearing articles are a minority of the inventory but half the sample.
    assert signal / total < 0.35, signal / total
    drawn = Counter(row["stratum"] for row in read(C1_PREDICTIONS))
    drawn_signal = sum(v for k, v in drawn.items() if k.endswith(":signal"))
    assert drawn_signal / sum(drawn.values()) == pytest.approx(0.5, abs=0.05)


@c1_only
def test_the_class1_pack_is_disjoint_from_earlier_human_truth_sets() -> None:
    drawer = load("draw_granularity_development_set")
    spent = drawer.spent_urls([ROOT / path for path in drawer.SPENT_SETS])
    drawn = {row["url"] for row in read(C1_PACK)}
    assert not (drawn & spent), f"{len(drawn & spent)} spent articles were drawn again"
    # Including the first granularity pack, which is now itself spent.
    first = OUTPUTS / "granularity_development_COMPLETED.csv"
    if first.exists():
        assert not (drawn & {row["url"] for row in read(first)})


@c1_only
def test_the_class1_pack_hides_the_prediction_too() -> None:
    columns = set(read(C1_PACK)[0])
    assert "predicted_granularity" not in columns
    assert "stratum" not in columns, "the stratum leaks the enrichment signal"


@c1_only
def test_the_two_packs_do_not_share_a_row_id_namespace() -> None:
    """A completed file must be identifiable as one pack or the other.

    Both packs originally numbered their rows `gran-0001...`, so a copy of the
    first pack renamed to the second's filename looked plausible: same columns,
    same id format. Only the row count (120 vs 100) and a URL comparison
    revealed it. Distinct prefixes make the mix-up visible at a glance.
    """

    first = {row["row_id"] for row in read(PACK)}
    second = {row["row_id"] for row in read(C1_PACK)}
    assert not (first & second), "the packs share row ids and can be confused"
    assert all(row_id.startswith("c1-") for row_id in second)


C1_COMPLETED = OUTPUTS / "granularity_class1_COMPLETED.csv"


@pytest.mark.skipif(
    not (C1_COMPLETED.exists() and C1_PREDICTIONS.exists()),
    reason="class-1 labels not present in this checkout",
)
def test_the_body_signal_helps_on_the_HUMAN_labelled_set() -> None:
    """The reversal, measured on the population the pipeline actually keeps.

    The model-labelled set said this signal was harmful. Human labels on class-1
    articles say the opposite, and by a wide margin. This test pins the
    direction and rough size so neither result can be quietly lost.
    """

    import gzip

    corpus_path = ROOT / "data" / "corpus" / "corpus_for_extraction.csv.gz"
    if not corpus_path.exists():
        pytest.skip("corpus absent in this checkout")

    csv.field_size_limit(50_000_000)
    sys.path.insert(0, str(ROOT / "src"))
    from landslide_inventory.unify import event_typing as typing_module

    with gzip.open(corpus_path, "rt", encoding="utf-8", newline="") as handle:
        corpus = {row["url"]: row for row in csv.DictReader(handle)}
    predictions = {row["row_id"]: row for row in read(C1_PREDICTIONS)}

    current = candidate = total = 0.0
    gained = wrongly = 0.0
    for row in read(C1_COMPLETED):
        truth = row["event_granularity_true"].strip()
        if truth not in {"single", "multi", "roundup", "not_applicable"}:
            continue
        article = corpus.get(row["url"])
        if article is None:
            continue
        weight = float(predictions[row["row_id"]]["inclusion_weight"])
        body = article.get("text") or ""
        signal = bool(
            typing_module.MULTI_EVENT_PATTERN.search(body)
            or typing_module.MULTI_ADMIN_PATTERN.search(body)
        )
        total += weight
        current += weight if truth == "single" else 0.0  # class 1 always predicts single
        candidate += weight if truth == ("multi" if signal else "single") else 0.0
        if signal:
            gained += weight if truth == "multi" else 0.0
            wrongly += weight if truth != "multi" else 0.0

    assert gained > wrongly, "the human-labelled reversal has disappeared"
    assert gained / wrongly > 1.5, gained / wrongly
    change = (candidate - current) / total
    assert 0.05 < change < 0.13, change


@pytest.mark.skipif(
    not C1_COMPLETED.exists(), reason="class-1 labels not present in this checkout"
)
def test_the_kept_inventory_is_substantially_not_single_events() -> None:
    """The headline finding: the pipeline keeps far more than single events.

    Weighted to the 3,110 class-1 articles, an estimated 41.5% of the kept
    inventory is multi, roundup or not an event at all, while the class-1 gate
    labels every one of them `single` by construction.
    """

    predictions = {row["row_id"]: row for row in read(C1_PREDICTIONS)}
    weight_by_truth: dict[str, float] = {}
    total = 0.0
    for row in read(C1_COMPLETED):
        truth = row["event_granularity_true"].strip()
        if truth not in {"single", "multi", "roundup", "not_applicable"}:
            continue
        weight = float(predictions[row["row_id"]]["inclusion_weight"])
        weight_by_truth[truth] = weight_by_truth.get(truth, 0.0) + weight
        total += weight

    single_share = weight_by_truth["single"] / total
    assert 0.5 < single_share < 0.7, single_share
    assert weight_by_truth["multi"] / total > 0.2, "multi is a large minority, not an edge case"


@pytest.mark.skipif(
    not (C1_COMPLETED.exists() and C1_PREDICTIONS.exists()),
    reason="class-1 labels not present in this checkout",
)
def test_retained_articles_are_overwhelmingly_real_events() -> None:
    """The measure that decided the paper keeps its multi-event articles.

    Article-level headline precision on locked v7 is 0.626, which reads as a
    weak inventory. It is not: that definition additionally requires an article
    to describe exactly ONE failure. Measured directly, 95.5% of retained
    articles report a real landslide in Nepal, and every multi-event article in
    the class-1 sample was a genuine Nepali landslide.

    Because the analysis unit is the district-day, a multi-event article yields
    the same correct district-day as a single-event one. Dropping such articles
    to lift the article-level metric would delete true case-days. This test pins
    the measurement so that reasoning cannot be quietly reversed.
    """

    predictions = {row["row_id"]: row for row in read(C1_PREDICTIONS)}
    numerator = denominator = 0.0
    multi_total = multi_real = 0
    for row in read(C1_COMPLETED):
        weight = float(predictions[row["row_id"]]["inclusion_weight"])
        real = (
            row["is_landslide_event_true"].strip() == "yes"
            and row["in_nepal_true"].strip() == "yes"
        )
        denominator += weight
        numerator += weight if real else 0.0
        if row["event_granularity_true"].strip() == "multi":
            multi_total += 1
            multi_real += 1 if real else 0

    assert multi_total > 0
    assert multi_real == multi_total, (
        "a multi-event article that is not a real Nepali landslide would break "
        "the argument for retaining them"
    )
    assert numerator / denominator > 0.90, numerator / denominator
