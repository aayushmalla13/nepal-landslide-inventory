#!/usr/bin/env python3
"""Measure whether the rebuilt gazetteer changes article-level district assignment.

Why this exists
---------------
The municipality gazetteer grew from 142 to 753 local units. More names now
match, so in principle a different place mention can win and an article can be
assigned to a different district. District is the analysis unit for the whole
rainfall study, so this has to be measured, not assumed, before any new
inventory release.

Method
------
Runs the project's own ``build_article_event_record`` -- the exact function the
extract stage uses, including ``_reconcile_place``, which is the step where a
municipality can inform the district -- over every stored article, and compares
the district it now produces with the district in ``article_events.csv``, the
released extract-stage output produced with the previous 142-unit gazetteer.

Baseline choice matters here and was got wrong once
---------------------------------------------------
``corpus_for_extraction.csv.gz`` also carries ``class`` and ``district``
columns, and they are the obvious thing to compare against. They are the wrong
baseline for this script, because the two artifacts are taken at different
points in the pipeline:

* ``article_events.csv`` is the **extract-stage** output — exactly what
  ``build_article_event_record`` returns, which is what this script recomputes.
  It holds 6,344 class-1 rows in the v0.4.0 release.
* the corpus export is taken **after** ``event_specificity``, ``filter_scope``,
  ``location_consistency`` and ``corrections`` have demoted rows. It holds 3,380
  class-1 rows for the same release.

Comparing recomputed extract-stage output against the post-filter corpus
reported ~2,990 "class transitions" that are simply the filter stages doing
their job, and buried a real drift of about 1.6%. Compare like with like: the
extract-stage output is the only correct baseline here.

Note that ``--baseline`` must point at a *preserved* copy once the pipeline has
been re-run, since the stage overwrites ``data/outputs/article_events.csv`` in
place. The v0.4.0 copy is kept at
``_baseline/outputs_v0.4.0_v0.2.0/article_events.csv``.

Four outcomes are counted per article:

``unchanged``    same district before and after
``gained``       no district before, a district now
``lost``         a district before, none now
``changed``      a different district

Only ``changed`` and ``lost`` can invalidate an existing released event.
Class-1 articles are reported separately because those are the ones that become
canonical events and therefore rainfall cases.

Usage::

    PYTHONPATH=src python3 scripts/measure_district_drift.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from landslide_inventory.gazetteer import (  # noqa: E402
    district_to_province,
    municipality_to_district,
    normalize_district,
    normalize_municipality,
)
from landslide_inventory.unify.extract_stage import (  # noqa: E402
    ArticleRow,
    build_article_event_record,
)

EXTRACTED_AT = "2026-08-14T00:00:00Z"


def read_corpus(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:  # type: ignore[operator]
        return list(csv.DictReader(handle))


def build_gazetteers() -> tuple[dict, dict]:
    """Reproduce exactly the gazetteer dicts the extract stage builds."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="data/corpus/corpus_for_extraction.csv.gz")
    parser.add_argument(
        "--baseline",
        default="data/outputs/article_events.csv",
        help="released extract-stage output to compare against",
    )
    parser.add_argument("--outputs", default="data/outputs")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--limit", type=int, default=0, help="0 = all articles")
    parser.add_argument(
        "--only-class",
        default="",
        help="restrict to one stored class (1, 2 or 3); blank = all",
    )
    args = parser.parse_args()

    import yaml

    raw = yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))
    study_start = date.fromisoformat(raw["study_period"]["start"])
    study_end = date.fromisoformat(raw["study_period"]["end"])
    keywords_cfg = dict(raw["keywords"])
    english, nepali = build_gazetteers()

    baseline = {row["url"]: row for row in read_corpus(ROOT / args.baseline)}
    rows = [row for row in read_corpus(ROOT / args.corpus) if row.get("url") in baseline]
    if args.only_class:
        rows = [
            row
            for row in rows
            if (baseline[row["url"]].get("class") or "").strip() == args.only_class
        ]
    if args.limit:
        rows = rows[: args.limit]

    outcomes: Counter[str] = Counter()
    class_one_outcomes: Counter[str] = Counter()
    class_changes: Counter[str] = Counter()
    drift_rows: list[dict[str, object]] = []
    by_district_lost: Counter[str] = Counter()
    municipality_gain = 0

    for row in rows:
        article = ArticleRow(
            url=row.get("url", ""),
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
        was = baseline[row["url"]]
        before = (was.get("district") or "").strip() or None
        after = record.get("district") or None
        old_class = (was.get("class") or "").strip()
        new_class = str(record.get("class") or "")

        if before == after:
            outcome = "unchanged"
        elif before is None:
            outcome = "gained"
        elif after is None:
            outcome = "lost"
        else:
            outcome = "changed"
        outcomes[outcome] += 1
        if old_class == "1":
            class_one_outcomes[outcome] += 1
            if outcome == "lost":
                by_district_lost[before or "?"] += 1
        if old_class != new_class:
            class_changes[f"{old_class}->{new_class}"] += 1

        old_municipality = (was.get("municipality") or "").strip()
        new_municipality = (record.get("municipality") or "").strip()
        if not old_municipality and new_municipality:
            municipality_gain += 1

        if outcome != "unchanged" or old_class != new_class:
            drift_rows.append(
                {
                    "url": row.get("url", ""),
                    "source": row.get("source", ""),
                    "language": row.get("route_lang", ""),
                    "baseline": args.baseline,
                    "old_class": old_class,
                    "new_class": new_class,
                    "old_district": before or "",
                    "new_district": after or "",
                    "outcome": outcome,
                    "old_municipality": old_municipality,
                    "new_municipality": new_municipality,
                    "title": (row.get("title") or "")[:120],
                }
            )

    outputs = ROOT / args.outputs
    outputs.mkdir(parents=True, exist_ok=True)
    drift_path = outputs / "district_drift_rows.csv"
    columns = list(drift_rows[0]) if drift_rows else ["url"]
    with drift_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(drift_rows)

    total = len(rows)
    class_one_total = sum(
        1 for row in rows if (baseline[row["url"]].get("class") or "").strip() == "1"
    )
    summary = {
        "articles": total,
        "class_one_articles": class_one_total,
        "all_articles": dict(outcomes),
        "class_one_articles_outcomes": dict(class_one_outcomes),
        "class_transitions": dict(class_changes),
        "municipality_newly_assigned": municipality_gain,
        "class_one_districts_lost_by_district": dict(by_district_lost.most_common()),
        "interpretation": (
            "Only 'changed' and 'lost' on class-1 articles can invalidate an "
            "existing released event. 'gained' is additive. A non-zero changed "
            "or lost count on class-1 articles means the rainfall analysis must "
            "be re-run and re-released alongside a new inventory version."
        ),
        "verdict": (
            "SAFE: district assignment is unchanged for every class-1 article"
            if not class_one_outcomes["changed"] and not class_one_outcomes["lost"]
            else "DRIFT DETECTED: see district_drift_rows.csv"
        ),
    }
    summary_path = outputs / "district_drift_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"articles processed        : {total} ({class_one_total} class-1)")
    print(f"all articles              : {dict(outcomes)}")
    print(f"class-1 articles          : {dict(class_one_outcomes)}")
    print(f"class transitions         : {dict(class_changes)}")
    print(f"municipality newly set    : {municipality_gain}")
    print(f"VERDICT                   : {summary['verdict']}")
    print(f"wrote {drift_path.relative_to(ROOT)} ({len(drift_rows)} rows)")
    print(f"wrote {summary_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
