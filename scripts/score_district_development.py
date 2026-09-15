#!/usr/bin/env python3
"""Score district assignment against the labelled development set, with ablation.

Why this exists
---------------
Expanding the municipality gazetteer from 142 to 753 local units changed which
district some articles are assigned to. District is the analysis unit for the
whole rainfall study, so "did it change?" (``measure_district_drift.py``) is not
enough -- the question is whether it changed *for the better*, and drift alone
cannot answer that because the baseline it compares against is itself a mixture
of correct and incorrect assignments.

``development_set_v1_labels_final.csv`` carries a human ``district_true`` for
123 articles. Per ``docs/DEVELOPMENT_SET.md`` this set exists precisely so that
rules may be designed against it; its numbers are development diagnostics and
must never be reported as held-out performance. The locked test sets are not
touched here, and nothing in this script writes a label.

What is compared
----------------
Two independent decision points were identified as the cause of the drift, and
each is exposed as an ablation switch so the comparison is reproducible without
editing code:

``BODY_DISTRICT_OUTRANKS_DATELINE`` (``nlp_en.extract``)
    Whether an explicit "<X> district" phrase in the body beats the dateline.
    A dateline names the filing bureau, which is frequently the neighbouring
    regional centre rather than the district the event occurred in.

``MUNICIPALITY_OVERRIDES_DISTRICT`` (``unify.extract_stage``)
    Whether a municipality's district always overrides an extracted district.
    The alternative keeps the established district and drops the contradicting
    municipality, on the grounds that the language extractor has already
    adjudicated that conflict against the evidence in the text.

All four combinations are scored. The released pipeline's own output -- the
``district`` column of the extraction corpus, produced with the 142-unit
gazetteer -- is reported alongside as the frozen baseline.

Usage::

    PYTHONPATH=src python3 scripts/score_district_development.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from datetime import date
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from landslide_inventory.gazetteer import (  # noqa: E402
    all_districts,
    district_to_province,
    municipality_to_district,
    normalize_district,
    normalize_municipality,
)
from landslide_inventory.nlp_en import extract as nlp_en_extract  # noqa: E402
from landslide_inventory.unify import extract_stage  # noqa: E402
from landslide_inventory.unify.extract_stage import (  # noqa: E402
    ArticleRow,
    build_article_event_record,
)

EXTRACTED_AT = "2026-08-14T00:00:00Z"


def read_corpus(path: Path) -> dict[str, dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:  # type: ignore[operator]
        return {row["url"]: row for row in csv.DictReader(handle)}


def build_gazetteers() -> tuple[dict, dict]:
    english = {
        "normalize_district": lambda name: normalize_district(name, "en"),
        "normalize_municipality": lambda name: normalize_municipality(name, "en"),
        "municipality_to_district": municipality_to_district,
        "district_to_province": district_to_province,
    }
    nepali = {
        "normalize_district": lambda name: normalize_district(name, "np"),
        "normalize_municipality": lambda name: normalize_municipality(name, "np"),
        "municipality_to_district": municipality_to_district,
        "district_to_province": district_to_province,
    }
    return english, nepali


def to_int(value: str | None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def canonical_truth(raw: str, canonical: set[str]) -> str | None:
    """Map an annotator's district string onto the project vocabulary.

    Annotators wrote free text. A value that does not resolve to a canonical
    district is dropped from scoring rather than guessed at, and the count of
    dropped rows is reported so the denominator is never silently reduced.
    """

    value = (raw or "").strip()
    if not value or value.lower() in {"unknown", "unclear", "n/a", "na", "none", "-"}:
        return None
    if value in canonical:
        return value
    return normalize_district(value, "en") or normalize_district(value, "np")


def predict(rows, english, nepali, keywords_cfg, study_start, study_end) -> dict[str, str | None]:
    predictions: dict[str, str | None] = {}
    for url, row in rows.items():
        article = ArticleRow(
            url=url,
            source=row.get("source", ""),
            title=row.get("title") or None,
            year_hint=to_int((row.get("published_date_ad") or "")[:4]),
            published_date_raw=row.get("published_date_raw") or None,
            published_date_ad=row.get("published_date_ad") or None,
            text=row.get("text") or "",
            route_lang=row.get("route_lang") or "en",
            mixed_flag=str(row.get("mixed_flag") or "").strip() in ("1", "True", "true"),
        )
        record = build_article_event_record(
            row=article,
            extracted_at=EXTRACTED_AT,
            keywords_cfg=keywords_cfg,
            en_gazetteer=english,
            np_gazetteer=nepali,
            study_start=study_start,
            study_end=study_end,
        )
        predictions[url] = record.get("district") or None
    return predictions


def score(predictions: dict[str, str | None], truth: dict[str, str]) -> dict[str, object]:
    correct = wrong = missing = 0
    for url, expected in truth.items():
        got = predictions.get(url)
        if got == expected:
            correct += 1
        elif got is None:
            missing += 1
        else:
            wrong += 1
    total = len(truth)
    return {
        "labelled_rows": total,
        "correct": correct,
        "wrong_district": wrong,
        "no_district": missing,
        "accuracy": round(correct / total, 4) if total else None,
        # Precision among rows the pipeline was willing to assign: the metric
        # that matters for the rainfall analysis, because an unassigned article
        # is dropped rather than misplaced.
        "precision_when_assigned": round(correct / (correct + wrong), 4)
        if (correct + wrong)
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="data/corpus/corpus_for_extraction.csv.gz")
    parser.add_argument("--labels", default="data/outputs/development_set_v1_labels_final.csv")
    parser.add_argument("--outputs", default="data/outputs")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    import yaml

    raw = yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))
    study_start = date.fromisoformat(raw["study_period"]["start"])
    study_end = date.fromisoformat(raw["study_period"]["end"])
    keywords_cfg = dict(raw["keywords"])
    english, nepali = build_gazetteers()
    canonical = set(all_districts())

    corpus = read_corpus(ROOT / args.corpus)
    with (ROOT / args.labels).open("rt", encoding="utf-8-sig", newline="") as handle:
        label_rows = list(csv.DictReader(handle))

    truth: dict[str, str] = {}
    unresolved: list[str] = []
    absent: list[str] = []
    for row in label_rows:
        url = (row.get("url") or "").strip()
        expected = canonical_truth(row.get("district_true", ""), canonical)
        if expected is None:
            if (row.get("district_true") or "").strip():
                unresolved.append(row.get("district_true", "").strip())
            continue
        if url not in corpus:
            absent.append(url)
            continue
        truth[url] = expected

    scored_rows = {url: corpus[url] for url in truth}

    # The frozen baseline: whatever the released pipeline stored, produced with
    # the 142-unit gazetteer. Read, never recomputed.
    released = {url: (row.get("district") or "").strip() or None for url, row in scored_rows.items()}

    results: dict[str, object] = {
        "labelled_district_rows": len(truth),
        "labels_unresolved_to_canonical": sorted(set(unresolved)),
        "labelled_urls_absent_from_corpus": len(absent),
        "released_baseline_v0.4.0_142_unit_gazetteer": score(released, truth),
        "variants": {},
    }

    original_body = nlp_en_extract.BODY_DISTRICT_OUTRANKS_DATELINE
    original_override = extract_stage.MUNICIPALITY_OVERRIDES_DISTRICT
    per_variant_predictions: dict[str, dict[str, str | None]] = {}
    try:
        for body_first, municipality_wins in product((False, True), (True, False)):
            nlp_en_extract.BODY_DISTRICT_OUTRANKS_DATELINE = body_first
            extract_stage.MUNICIPALITY_OVERRIDES_DISTRICT = municipality_wins
            name = (
                f"body_district_first={body_first}"
                f",municipality_overrides_district={municipality_wins}"
            )
            predictions = predict(
                scored_rows, english, nepali, keywords_cfg, study_start, study_end
            )
            per_variant_predictions[name] = predictions
            results["variants"][name] = score(predictions, truth)  # type: ignore[index]
    finally:
        nlp_en_extract.BODY_DISTRICT_OUTRANKS_DATELINE = original_body
        extract_stage.MUNICIPALITY_OVERRIDES_DISTRICT = original_override

    chosen = (
        f"body_district_first={original_body}"
        f",municipality_overrides_district={original_override}"
    )
    results["chosen_configuration"] = chosen
    results["note"] = (
        "Development-set diagnostics for rule design only, per "
        "docs/DEVELOPMENT_SET.md. These are not held-out performance and must "
        "not be reported as such; a newly drawn locked test set is required "
        "before any accuracy claim enters the manuscript."
    )

    outputs = ROOT / args.outputs
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "district_development_ablation.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    error_rows = []
    chosen_predictions = per_variant_predictions[chosen]
    for url, expected in sorted(truth.items()):
        got = chosen_predictions.get(url)
        if got == expected:
            continue
        row = scored_rows[url]
        error_rows.append(
            {
                "url": url,
                "source": row.get("source", ""),
                "language": row.get("route_lang", ""),
                "district_true": expected,
                "district_released": released.get(url) or "",
                "district_chosen": got or "",
                "released_was_correct": int(released.get(url) == expected),
                "title": (row.get("title") or "")[:120],
            }
        )
    error_path = outputs / "district_development_errors.csv"
    columns = [
        "url",
        "source",
        "language",
        "district_true",
        "district_released",
        "district_chosen",
        "released_was_correct",
        "title",
    ]
    with error_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(error_rows)

    print(f"labelled district rows scored : {len(truth)}")
    if unresolved:
        print(f"labels not resolvable         : {sorted(set(unresolved))}")
    baseline = results["released_baseline_v0.4.0_142_unit_gazetteer"]
    print(f"released baseline (v0.4.0)    : {baseline}")
    for name, metrics in results["variants"].items():  # type: ignore[union-attr]
        marker = " <- chosen" if name == chosen else ""
        print(f"{name:58} {metrics}{marker}")
    print(f"wrote {error_path.relative_to(ROOT)} ({len(error_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
