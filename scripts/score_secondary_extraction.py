#!/usr/bin/env python3
"""Measure the secondary-failure extractor against the 47-article audit.

This is a **development** measurement. The audit in
``data/outputs/multievent_yield_audit.csv`` was produced by reading all 47
human-labelled ``multi`` articles, and that reading is what the extractor's
rules encode. Scoring against it therefore reports how faithfully the rules
capture that reading -- not how well they generalise. The honest evaluation is
locked test set v8, which does not yet exist.

What this does measure, and what it is for:

* **precision** -- of the district-days the extractor emits, how many are in the
  audited defensible set. This is the number that matters. A false secondary
  record puts a fabricated landslide into the canonical inventory, spatially
  correlated with rainfall.
* **recall** -- how much of the defensible yield the rules actually reach.
  Deliberately secondary: a missed recovery costs one district-day out of a
  projected two hundred.
* **the trap check** -- that none of the nine audited trap districts is emitted.
  A regression here is the failure mode that would do real damage, so each trap
  is named individually in the output rather than folded into precision.

Usage::

    PYTHONPATH=src python3 scripts/score_secondary_extraction.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

csv.field_size_limit(50_000_000)

# The (row_id, district, date) pairs the audit found defensible, transcribed
# from `multievent_yield_audit.csv`'s notes. Kept here rather than in the CSV
# because the CSV records the *count* and the reasoning, and these are the
# resolved pairs that count implies.
DEFENSIBLE: tuple[tuple[str, str, str, str], ...] = (
    ("c1-0002", "Tanahu", "2022-06-28", "strong"),
    ("c1-0009", "Kalikot", "2019-04-06", "strong"),
    ("c1-0017", "Dhading", "2022-06-14", "strong"),
    ("c1-0035", "Myagdi", "2021-06-21", "strong"),
    ("c1-0039", "Chitwan", "2018-06-26", "strong"),
    ("c1-0039", "Chitwan", "2018-06-25", "strong"),
    ("c1-0040", "Dhading", "2020-07-20", "strong"),
    ("c1-0044", "Kavrepalanchok", "2026-04-20", "strong"),
    ("c1-0070", "Sankhuwasabha", "2016-09-21", "strong"),
    ("c1-0092", "Chitwan", "2025-09-23", "strong"),
    ("c1-0002", "Myagdi", "2022-06-28", "weak"),
    ("c1-0017", "Dhading", "2022-06-16", "weak"),
    ("c1-0033", "Manang", "2018-09-14", "weak"),
    ("c1-0044", "Myagdi", "2026-04-16", "weak"),
    ("c1-0079", "Sankhuwasabha", "2026-05-06", "weak"),
    ("c1-0080", "Chitwan", "2021-07-01", "weak"),
    ("c1-0083", "Palpa", "2020-07-22", "weak"),
)

# Three entries above were revised after the extractor disagreed with the first
# read and the article text was checked again. Recorded here because revising
# ground truth in response to a model's output is the thing most likely to make
# a development measurement dishonest, and it should be visible rather than
# silent:
#
#   c1-0017 Dhading 2022-06-14  added   -- explicitly dated, first read missed it
#   c1-0035 Myagdi  2021-06-21  added   -- first read wrongly treated a
#                                          retrospectively reported but
#                                          explicitly dated failure as unusable
#   c1-0033 Manang  2018-09-14  strong -> weak, applied for symmetry: every
#                                          enumerated failure is in Lamjung and
#                                          Manang is the corridor endpoint
#
# The extractor is not scored on v8, which remains undrawn and untouched.

# Districts that must never be emitted for these articles. Each one was
# observed in the audit as a trap, and each would be a fabricated event.
FORBIDDEN: tuple[tuple[str, str, str], ...] = (
    ("c1-0034", "Sindhupalchok", "victim_home_district"),
    ("c1-0034", "Nuwakot", "victim_home_district"),
    ("c1-0070", "Bhojpur", "victim_home_district"),
    ("c1-0009", "Surkhet", "dateline"),
    ("c1-0046", "Rupandehi", "dateline"),
    ("c1-0095", "Kathmandu", "dateline"),
    ("c1-0011", "Mustang", "road_destination"),
    ("c1-0032", "Mustang", "road_destination"),
    ("c1-0047", "Gorkha", "stranded_destination"),
    ("c1-0047", "Tanahu", "stranded_destination"),
    ("c1-0047", "Kathmandu", "stranded_destination"),
    ("c1-0002", "Lalitpur", "publisher_address"),
    ("c1-0010", "Syangja", "adjacency_mention"),
    ("c1-0081", "Jajarkot", "hospital_referral"),
    ("c1-0020", "Salyan", "spurious_gazetteer_hit"),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--labels", default="data/outputs/granularity_class1_COMPLETED.csv")
    parser.add_argument("--pack", default="data/outputs/granularity_class1_reading_pack.csv")
    parser.add_argument("--articles", default="data/outputs/article_events.csv")
    parser.add_argument("--output", default="data/outputs/secondary_extraction_score.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    from landslide_inventory.unify.multievent import extract_secondary_failures

    labels = {row["row_id"]: row for row in read_csv(ROOT / args.labels)}
    pack = {row["row_id"]: row for row in read_csv(ROOT / args.pack)}
    articles = {row["url"]: row for row in read_csv(ROOT / args.articles)}

    multi_ids = sorted(
        row_id for row_id, row in labels.items() if row["event_granularity_true"] == "multi"
    )

    defensible = {(row_id, district, day) for row_id, district, day, _ in DEFENSIBLE}
    forbidden = {(row_id, district) for row_id, district, _ in FORBIDDEN}

    emitted: list[tuple[str, str, str, str, str]] = []
    for row_id in multi_ids:
        label = labels[row_id]
        article = articles.get(label["url"])
        entry = pack.get(row_id)
        if article is None or entry is None:
            continue
        results = extract_secondary_failures(
            entry.get("title"),
            entry.get("article_text") or "",
            lang=entry.get("route_lang") or article.get("route_lang") or "en",
            published_date_ad=article.get("published_date_ad"),
            primary_district=article.get("district"),
            primary_date=article.get("event_date_ad"),
            primary_municipality=article.get("municipality") or None,
        )
        for result in results:
            emitted.append(
                (row_id, result.district, result.event_date_ad, result.date_basis, result.sentence)
            )

    # Negative control. The audit only covers `multi` articles, so nothing in
    # it says what the extractor does on an ordinary one -- and the corpus run
    # applies it to every kept class-1 article, ~70% of which the annotator
    # called `single`. A `single` article reports one failure by definition, so
    # every record emitted from one is wrong. This is the only human-labelled
    # evidence available that the rules stay quiet when they should.
    control: dict[str, dict[str, int]] = {}
    for row_id, label in sorted(labels.items()):
        truth = label["event_granularity_true"]
        if truth in ("multi", ""):
            continue
        article = articles.get(label["url"])
        entry = pack.get(row_id)
        if article is None or entry is None:
            continue
        results = extract_secondary_failures(
            entry.get("title"),
            entry.get("article_text") or "",
            lang=entry.get("route_lang") or article.get("route_lang") or "en",
            published_date_ad=article.get("published_date_ad"),
            primary_district=article.get("district"),
            primary_date=article.get("event_date_ad"),
            primary_municipality=article.get("municipality") or None,
        )
        cell = control.setdefault(truth, {"articles": 0, "articles_emitting": 0, "records": 0})
        cell["articles"] += 1
        cell["articles_emitting"] += 1 if results else 0
        cell["records"] += len(results)

    emitted_keys = {(row_id, district, day) for row_id, district, day, _, _ in emitted}
    emitted_districts = {(row_id, district) for row_id, district, _, _, _ in emitted}

    true_positive = sorted(emitted_keys & defensible)
    false_positive = sorted(emitted_keys - defensible)
    missed = sorted(defensible - emitted_keys)
    trap_violations = sorted(emitted_districts & forbidden)

    precision = len(true_positive) / len(emitted_keys) if emitted_keys else None
    recall = len(true_positive) / len(defensible) if defensible else None
    strong = {(r, d, day) for r, d, day, kind in DEFENSIBLE if kind == "strong"}
    strong_recall = len(strong & emitted_keys) / len(strong) if strong else None

    result = {
        "set": "class1_multi_development_audit",
        "caveat": (
            "Development measurement. The audit these rules were written from "
            "cannot also evaluate them; locked test set v8 is the honest "
            "evaluation and has not been drawn."
        ),
        "articles": len(multi_ids),
        "emitted_district_days": len(emitted_keys),
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "recall_strong_only": round(strong_recall, 4) if strong_recall is not None else None,
        "negative_control": {
            "note": (
                "Human-labelled non-multi articles from the same pack. A record "
                "emitted from a `single` article is wrong by definition."
            ),
            "by_truth": control,
            "total_records": sum(cell["records"] for cell in control.values()),
        },
        "trap_violations": [
            {"row_id": row_id, "district": district} for row_id, district in trap_violations
        ],
        "false_positives": [
            {"row_id": r, "district": d, "date": day} for r, d, day in false_positive
        ],
        "missed": [{"row_id": r, "district": d, "date": day} for r, d, day in missed],
        "emitted": [
            {
                "row_id": r,
                "district": d,
                "date": day,
                "date_basis": basis,
                "sentence": sentence[:200],
            }
            for r, d, day, basis, sentence in sorted(emitted)
        ],
    }

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{len(multi_ids)} multi articles -> {len(emitted_keys)} secondary district-days")
    print(f"  precision {result['precision']}   recall {result['recall']} "
          f"(strong only {result['recall_strong_only']})")
    print("\n  negative control (human-labelled non-multi articles):")
    for truth, cell in sorted(control.items()):
        print(
            f"    {truth:16s} {cell['articles']:3d} articles -> "
            f"{cell['records']} records from {cell['articles_emitting']} articles"
        )
    print(f"\n  trap violations: {len(trap_violations)}")
    for row_id, district in trap_violations:
        print(f"    !! {row_id} emitted {district}")
    print(f"\n  false positives ({len(false_positive)}):")
    for row_id, district, day in false_positive[:20]:
        print(f"    {row_id} {district} {day}")
    print(f"\n  missed ({len(missed)}):")
    for row_id, district, day in missed:
        print(f"    {row_id} {district} {day}")
    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
