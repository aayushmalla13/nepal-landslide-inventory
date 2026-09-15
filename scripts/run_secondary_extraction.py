#!/usr/bin/env python3
"""Run the secondary-failure extractor across the whole kept inventory.

This is a **dry run**. Nothing is written to the database, the inventory, or any
release. It produces `data/outputs/secondary_failures.csv` -- one row per
recovered district-day, with the sentence that justifies it -- and a summary
that can be compared against the development projection.

Why the comparison matters
--------------------------
The projection in `docs/MULTIEVENT_EXTRACTION.md` (+13.2% of case-days, 95% CI
[6.9, 20.2]) was extrapolated from 47 articles using stratum inclusion weights,
and 80% of it came from a single stratum. Running the extractor over all kept
articles measures the same quantity directly, on the whole population, with no
weighting assumptions. If the two disagree badly, the weighted extrapolation was
wrong and the gate that let this project proceed needs revisiting.

One asymmetry to keep in mind when reading the output: the extractor reaches
about half the defensible recoveries (development recall 0.53), so its corpus
yield is a *floor* on the true recoverable total, not an estimate of it.

Usage::

    PYTHONPATH=src python3 scripts/run_secondary_extraction.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

csv.field_size_limit(50_000_000)


def read_corpus(path: Path) -> dict[str, dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return {row["url"]: row for row in csv.DictReader(handle)}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--articles", default="data/outputs/article_events.csv")
    parser.add_argument("--canonical", default="data/outputs/canonical_events_final.csv")
    parser.add_argument("--corpus", default="data/corpus/corpus_for_extraction.csv.gz")
    parser.add_argument("--cases", default="data/outputs/event_antecedent_rainfall.csv")
    parser.add_argument("--output", default="data/outputs/secondary_failures.csv")
    parser.add_argument("--summary", default="data/outputs/secondary_failures_summary.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    from landslide_inventory.unify.multievent import (
        FIRM_DATE_BASES,
        extract_secondary_failures,
    )

    articles = read_csv(ROOT / args.articles)
    corpus = read_corpus(ROOT / args.corpus)
    canonical = read_csv(ROOT / args.canonical)
    case_days = {
        (row["district"], row["date"])
        for row in read_csv(ROOT / args.cases)
        if row["label"] == "1"
    }

    # Only articles the pipeline actually kept as class-1 events. A recovered
    # district-day from an article the pipeline rejected would be asserting an
    # event on the strength of a single sentence in a document already judged
    # not to be an event report.
    kept_urls = {row["representative_url"] for row in canonical}
    for row in canonical:
        try:
            payload = json.loads(row["event_payload"] or "{}")
        except json.JSONDecodeError:
            continue
        kept_urls.update(payload.get("urls") or [])

    existing_pairs = {
        (row["district"], row["event_date_ad"])
        for row in canonical
        if row["district"] and row["event_date_ad"]
    }

    recovered: list[dict[str, object]] = []
    considered = 0
    for article in articles:
        if article["url"] not in kept_urls:
            continue
        if str(article.get("class")) != "1":
            continue
        entry = corpus.get(article["url"])
        if entry is None:
            continue
        considered += 1
        results = extract_secondary_failures(
            entry.get("title") or article.get("title"),
            entry.get("text") or "",
            lang=article.get("route_lang") or "en",
            published_date_ad=article.get("published_date_ad"),
            primary_district=article.get("district"),
            primary_date=article.get("event_date_ad"),
            primary_municipality=article.get("municipality") or None,
        )
        for result in results:
            pair = (result.district, result.event_date_ad)
            recovered.append(
                {
                    "url": article["url"],
                    "source": article.get("source", ""),
                    "route_lang": article.get("route_lang", ""),
                    "primary_district": article.get("district", ""),
                    "primary_date": article.get("event_date_ad", ""),
                    "district": result.district,
                    "event_date_ad": result.event_date_ad,
                    "date_basis": result.date_basis,
                    "conf_date": result.confidence,
                    "firm_date": result.date_basis in FIRM_DATE_BASES,
                    "already_in_inventory": pair in existing_pairs,
                    "already_a_case_day": pair in case_days,
                    "evidence_sentence": result.sentence[:400],
                }
            )

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(recovered[0])) if recovered else None
        if writer is not None:
            writer.writeheader()
            for row in sorted(
                recovered, key=lambda item: (item["district"], item["event_date_ad"], item["url"])
            ):
                writer.writerow(row)

    novel_pairs = {
        (row["district"], row["event_date_ad"])
        for row in recovered
        if not row["already_a_case_day"]
    }
    firm_novel = {
        (row["district"], row["event_date_ad"])
        for row in recovered
        if not row["already_a_case_day"] and row["firm_date"]
    }

    summary = {
        "note": "Dry run. Nothing was written to the inventory or any release.",
        "articles_considered": considered,
        "recovered_records": len(recovered),
        "distinct_recovered_district_days": len(
            {(row["district"], row["event_date_ad"]) for row in recovered}
        ),
        "novel_district_days": len(novel_pairs),
        "novel_district_days_with_firm_date": len(firm_novel),
        "collision_rate_observed": round(
            1 - len(novel_pairs) / len({(r["district"], r["event_date_ad"]) for r in recovered}), 4
        )
        if recovered
        else None,
        "case_days_v0_6_0": len(case_days),
        "gain_pct_vs_case_days": round(100 * len(novel_pairs) / len(case_days), 2)
        if case_days
        else None,
        "gain_pct_firm_only": round(100 * len(firm_novel) / len(case_days), 2)
        if case_days
        else None,
        "development_projection_pct": 13.16,
        "development_projection_ci95": [6.88, 20.19],
        "development_recall": 0.5294,
        "date_basis_mix": dict(Counter(row["date_basis"] for row in recovered).most_common()),
        "articles_by_recovered_count": dict(
            Counter(Counter(row["url"] for row in recovered).values()).most_common()
        ),
        "top_districts": dict(Counter(row["district"] for row in recovered).most_common(15)),
        "top_sources": dict(Counter(row["source"] for row in recovered).most_common(10)),
    }

    summary_path = ROOT / args.summary
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"considered {considered} kept class-1 articles")
    print(f"  recovered {len(recovered)} records -> "
          f"{summary['distinct_recovered_district_days']} distinct district-days")
    print(f"  novel (not already a case-day): {summary['novel_district_days']} "
          f"= {summary['gain_pct_vs_case_days']}% of {len(case_days)} case-days")
    print(f"  of those, with a firm date anchor: {summary['novel_district_days_with_firm_date']} "
          f"= {summary['gain_pct_firm_only']}%")
    print(f"  observed collision rate: {summary['collision_rate_observed']}")
    print(f"\n  development projection was 13.16% [6.88, 20.19] at recall 0.53")
    print(f"  date basis mix: {summary['date_basis_mix']}")
    print(f"\nwrote {args.output} and {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
