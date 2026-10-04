#!/usr/bin/env python3
"""Run the integrity invariants over the district-days the analysis uses.

Reports, never deletes. Produces `data/outputs/case_integrity_findings.csv`
(one row per failed invariant, with its evidence) and a JSON summary.

Read the module docstring in `landslide_inventory/validation/case_integrity.py`
for why these checks exist. The short version: the pipeline's quality machinery
all measures whether an article is a real landslide report, and none of it asks
whether the record that article produced is internally coherent. An event dated
after its own publication is impossible and takes three lines to detect, and
the project has never run that check.

Usage::

    PYTHONPATH=src python3 scripts/run_case_integrity_audit.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

csv.field_size_limit(50_000_000)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_corpus(path: Path) -> dict[str, dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return {row["url"]: row for row in csv.DictReader(handle)}


def read_corpus_from_sqlite(path: Path) -> dict[str, dict[str, str]]:
    """Read the same evidence fields from the live article store.

    The historical corpus CSV is no longer produced, but ``raw_articles`` is
    the authoritative source from which it was built. Keeping this fallback in
    the audit prevents a missing intermediate export from leaving stale
    diagnostics in a later rainfall release.
    """

    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT url, title, text, published_date_ad FROM raw_articles"
        ).fetchall()
    return {str(row["url"]): dict(row) for row in rows}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--canonical", default="data/outputs/canonical_events_final.csv")
    parser.add_argument("--articles", default="data/outputs/article_events.csv")
    parser.add_argument("--corpus", default="data/corpus/corpus_for_extraction.csv.gz")
    parser.add_argument("--sqlite", default="data/raw_sqlite/landslide_inventory.sqlite")
    parser.add_argument("--cases", default="data/outputs/event_antecedent_rainfall.csv")
    parser.add_argument("--study-start", default="2015-01-01")
    parser.add_argument("--study-end", default="2026-08-14")
    parser.add_argument("--output", default="data/outputs/case_integrity_findings.csv")
    parser.add_argument("--summary", default="data/outputs/case_integrity_summary.json")
    parser.add_argument(
        "--lead-chars",
        type=int,
        default=1200,
        help=(
            "how much article body to search for hazard and occurrence terms. "
            "The whole body would pull in unrelated stories from page chrome "
            "and sidebars, which is how a gold-smuggling article can look like "
            "it mentions landslides."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    from landslide_inventory.validation import case_integrity as ci

    study_start = date.fromisoformat(args.study_start)
    study_end = date.fromisoformat(args.study_end)

    canonical = read_csv(ROOT / args.canonical)
    articles = {row["url"]: row for row in read_csv(ROOT / args.articles)}
    corpus_path = ROOT / args.corpus
    if corpus_path.exists():
        corpus = read_corpus(corpus_path)
    else:
        sqlite_path = ROOT / args.sqlite
        if not sqlite_path.exists():
            raise FileNotFoundError(
                f"neither corpus CSV nor article SQLite exists: {corpus_path}, {sqlite_path}"
            )
        corpus = read_corpus_from_sqlite(sqlite_path)
    case_days = {
        (row["district"], row["date"])
        for row in read_csv(ROOT / args.cases)
        if row["label"] == "1"
    }

    # Only the canonical events that actually became analysis case-days. An
    # integrity problem in an inventory row the analysis never reads is worth
    # knowing about but is not what this audit is for.
    in_case_set = [
        row for row in canonical if (row["district"], row["event_date_ad"]) in case_days
    ]

    findings: list[ci.IntegrityFinding] = []
    for row in in_case_set:
        district = row["district"]
        event_date_ad = row["event_date_ad"]
        url = row["representative_url"]
        article = articles.get(url, {})
        entry = corpus.get(url, {})
        title = entry.get("title") or row.get("representative_title") or ""
        text = f"{title}\n{(entry.get('text') or '')[: args.lead_chars]}"

        for finding in (
            ci.check_event_precedes_publication(
                district,
                event_date_ad,
                article.get("published_date_ad") or entry.get("published_date_ad"),
                url,
                title,
            ),
            ci.check_within_study_period(
                district, event_date_ad, study_start, study_end, url, title
            ),
            ci.check_article_mentions_the_hazard(district, event_date_ad, text, url, title),
            ci.check_not_a_forecast(district, event_date_ad, text, url, title),
            ci.check_anthropogenic_trigger_was_caught(
                district, event_date_ad, text, row.get("trigger"), url, title
            ),
        ):
            if finding is not None:
                findings.append(finding)

    findings.extend(
        ci.check_case_days_are_unique(
            (row["district"], row["event_date_ad"], row["event_id"]) for row in in_case_set
        )
    )

    report = ci.IntegrityReport(case_days=len(case_days), findings=findings)

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "district",
                "event_date_ad",
                "check",
                "severity",
                "detail",
                "url",
                "title",
            ],
        )
        writer.writeheader()
        for finding in sorted(
            findings, key=lambda f: (f.severity, f.check, f.district, f.event_date_ad)
        ):
            writer.writerow(
                {
                    "district": finding.district,
                    "event_date_ad": finding.event_date_ad,
                    "check": finding.check,
                    "severity": finding.severity,
                    "detail": finding.detail,
                    "url": finding.url,
                    "title": finding.title[:160],
                }
            )

    flagged_all = report.flagged_case_days()
    flagged_violations = report.flagged_case_days(ci.SEVERITY_VIOLATION)
    flagged_contamination = report.flagged_case_days(ci.SEVERITY_CONTAMINATION)
    # Informational findings are not defects and must not be counted as
    # excludable; see check_case_days_are_unique.
    excludable = flagged_violations | flagged_contamination
    summary = {
        "note": "Reports only. Nothing was removed from the inventory or any release.",
        "case_days_examined": len(case_days),
        "canonical_events_in_case_set": len(in_case_set),
        "findings": len(findings),
        "by_check": report.by_check(),
        "flagged_case_days": len(flagged_all),
        "flagged_case_days_pct": round(100 * len(flagged_all) / len(case_days), 2)
        if case_days
        else None,
        "flagged_case_days_violations_only": len(flagged_violations),
        "flagged_case_days_violations_pct": round(
            100 * len(flagged_violations) / len(case_days), 2
        )
        if case_days
        else None,
        "excludable_case_days": len(excludable),
        "excludable_case_days_pct": round(100 * len(excludable) / len(case_days), 2)
        if case_days
        else None,
    }
    (ROOT / args.summary).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"examined {len(case_days)} case-days ({len(in_case_set)} canonical events)")
    print(f"  findings: {len(findings)}")
    for check, count in report.by_check().items():
        print(f"    {check:32s} {count:4d}")
    print(
        f"\n  case-days flagged: {len(flagged_all)} "
        f"({summary['flagged_case_days_pct']}%)  of which impossible: "
        f"{len(flagged_violations)} ({summary['flagged_case_days_violations_pct']}%)"
    )
    print(
        f"  excludable (violation or contamination, not informational): "
        f"{len(excludable)} ({summary['excludable_case_days_pct']}%)"
    )
    excl_path = ROOT / args.output.replace(".csv", "_excludable_case_days.csv")
    with excl_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["district", "date"])
        for district, event_date_ad in sorted(excludable):
            writer.writerow([district, event_date_ad])
    print(f"  wrote {excl_path.name}")
    print(f"\nwrote {args.output} and {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
