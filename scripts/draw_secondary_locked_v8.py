#!/usr/bin/env python3
"""Draw the fresh article-level locked test for secondary failure extraction.

The spent precision census judged claims already emitted by the old extractor.
It could estimate precision but not recall, and its labels were subsequently
used to design strict v2. This draw instead samples previously unjudged articles
and asks the annotator to list the article's primary district-day and every
additional district-day it supports.

Predictions, sampling strata, and weights are written only to the hidden key.
The manifest hash-locks the ordered URLs and visible label file. Existing v8
artifacts are never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
csv.field_size_limit(50_000_000)

VERSION = "secondary_locked_v8"
SEED = 20260913
QUOTAS = {
    "en:legacy_candidate": None,
    "np:legacy_candidate": None,
    "en:district_rich": 40,
    "np:district_rich": 40,
    "en:ordinary": 15,
    "np:ordinary": 15,
}

LABEL_COLUMNS = [
    "row_id",
    "url",
    "source",
    "route_lang",
    "title",
    "primary_district_date_true",
    "additional_district_dates_true",
    "unresolved_additional_events_true",
    "annotator",
    "notes",
]

READING_COLUMNS = [
    "row_id",
    "url",
    "source",
    "route_lang",
    "title",
    "published_date_ad",
    "article_text",
]

HIDDEN_COLUMNS = [
    "row_id",
    "url",
    "stratum",
    "stratum_population",
    "sampled_from_stratum",
    "inclusion_weight",
    "pipeline_primary_district",
    "pipeline_primary_date",
    "strict_v2_predictions",
    "strict_v2_prediction_count",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_corpus(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_order(seed: int, key: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    ordered = sorted(rows, key=lambda row: row["url"])
    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).digest()
    random.Random(int.from_bytes(digest[:8], "big")).shuffle(ordered)
    return ordered


def prior_label_files(root: Path, version: str = VERSION) -> list[Path]:
    """Return human-label artifacts while excluding this pack's own files."""

    found: set[Path] = set()
    patterns = ("*LABEL_HERE*.csv", "*labels_final*.csv", "*COMPLETED*.csv")
    for directory in (root / "data" / "outputs", root / "docs", root / "output"):
        if not directory.exists():
            continue
        for pattern in patterns:
            for path in directory.rglob(pattern):
                if version.lower() not in path.name.lower():
                    found.add(path)
    human_precision = root / "data" / "outputs" / "secondary_precision_HUMAN_COMPLETED.csv"
    if human_precision.exists():
        found.add(human_precision)
    return sorted(found)


def spent_urls(paths: list[Path]) -> tuple[set[str], dict[str, int]]:
    seen: set[str] = set()
    audit: dict[str, int] = {}
    for path in paths:
        before = len(seen)
        try:
            rows = read_csv(path)
        except (OSError, csv.Error, UnicodeError):
            continue
        for row in rows:
            url = (row.get("url") or "").strip()
            if url:
                seen.add(url)
        audit[str(path.relative_to(ROOT))] = len(seen) - before
    return seen, audit


def prediction_map(path: Path) -> dict[str, list[dict[str, str]]]:
    by_url: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not path.exists():
        return by_url
    for row in read_csv(path):
        by_url[row["url"]].append(row)
    return by_url


def district_count(text: str, lang: str) -> int:
    from landslide_inventory.unify.multievent import _districts_in

    return len(_districts_in(text, lang, None))


def classify_stratum(
    row: dict[str, str], legacy_urls: set[str]
) -> str:
    language = "np" if row.get("route_lang") == "np" else "en"
    if row["url"] in legacy_urls:
        family = "legacy_candidate"
    elif district_count(row.get("text") or "", language) >= 2:
        family = "district_rich"
    else:
        family = "ordinary"
    return f"{language}:{family}"


def eligible_articles(corpus: list[dict[str, str]], spent: set[str]) -> list[dict[str, str]]:
    return [
        row
        for row in corpus
        if row.get("class") == "1"
        and row.get("in_nepal") == "1"
        and row.get("specificity_ok") == "1"
        and (row.get("text") or "").strip()
        and row["url"] not in spent
    ]


def lock_hash(urls: list[str]) -> str:
    payload = json.dumps(
        ["secondary_locked_test", VERSION, sorted(urls)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def visible_row(index: int, row: dict[str, str]) -> dict[str, str]:
    return {
        "row_id": f"secv8-{index:04d}",
        "url": row["url"],
        "source": row.get("source", ""),
        "route_lang": "np" if row.get("route_lang") == "np" else "en",
        "title": row.get("title", ""),
        "primary_district_date_true": "",
        "additional_district_dates_true": "",
        "unresolved_additional_events_true": "",
        "annotator": "",
        "notes": "",
    }


def format_predictions(rows: list[dict[str, str]]) -> str:
    pairs = sorted({f"{row['district']}|{row['event_date_ad']}" for row in rows})
    return "; ".join(pairs) if pairs else "none"


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="_xfer/corpus_for_extraction.csv.gz")
    parser.add_argument("--legacy", default="data/outputs/secondary_failures.csv")
    parser.add_argument("--predictions", default="data/outputs/secondary_failures_strict_v2.csv")
    parser.add_argument("--outputs", default="data/outputs")
    parser.add_argument("--seed", type=int, default=SEED)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    outputs = ROOT / args.outputs
    outputs.mkdir(parents=True, exist_ok=True)
    paths = {
        "labels": outputs / f"{VERSION}_LABEL_HERE.csv",
        "reading": outputs / f"{VERSION}_reading_pack.csv",
        "hidden": outputs / f"{VERSION}_DO_NOT_OPEN_predictions.csv",
        "manifest": outputs / f"{VERSION}_manifest.json",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise SystemExit(
            "refusing to overwrite locked v8 artifacts: "
            + ", ".join(path.name for path in existing)
        )

    corpus = read_corpus(ROOT / args.corpus)
    label_paths = prior_label_files(ROOT)
    spent, exclusion_audit = spent_urls(label_paths)
    eligible = eligible_articles(corpus, spent)

    legacy_rows = read_csv(ROOT / args.legacy)
    legacy_urls = {row["url"] for row in legacy_rows} - spent
    strict = prediction_map(ROOT / args.predictions)

    strata: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in eligible:
        strata[classify_stratum(row, legacy_urls)].append(row)

    drawn: list[tuple[str, dict[str, str]]] = []
    for stratum, quota in QUOTAS.items():
        pool = stable_order(args.seed, stratum, strata.get(stratum, []))
        take = len(pool) if quota is None else min(quota, len(pool))
        drawn.extend((stratum, row) for row in pool[:take])
    drawn.sort(key=lambda item: item[1]["url"])

    drawn_urls = [row["url"] for _, row in drawn]
    if len(drawn_urls) != len(set(drawn_urls)):
        raise RuntimeError("duplicate URL in locked draw")
    if set(drawn_urls) & spent:
        raise RuntimeError("prior-evaluation contamination in locked draw")

    drawn_counts = Counter(stratum for stratum, _ in drawn)
    visible = [visible_row(index, row) for index, (_, row) in enumerate(drawn, 1)]
    reading: list[dict[str, object]] = []
    hidden: list[dict[str, object]] = []
    for index, (stratum, row) in enumerate(drawn, 1):
        population = len(strata[stratum])
        sampled = drawn_counts[stratum]
        reading.append(
            {
                "row_id": f"secv8-{index:04d}",
                "url": row["url"],
                "source": row.get("source", ""),
                "route_lang": "np" if row.get("route_lang") == "np" else "en",
                "title": row.get("title", ""),
                "published_date_ad": row.get("published_date_ad", ""),
                "article_text": row.get("text", ""),
            }
        )
        predictions = strict.get(row["url"], [])
        hidden.append(
            {
                "row_id": f"secv8-{index:04d}",
                "url": row["url"],
                "stratum": stratum,
                "stratum_population": population,
                "sampled_from_stratum": sampled,
                "inclusion_weight": round(population / sampled, 6),
                "pipeline_primary_district": row.get("district", ""),
                "pipeline_primary_date": row.get("event_date_ad", ""),
                "strict_v2_predictions": format_predictions(predictions),
                "strict_v2_prediction_count": len(
                    {(item["district"], item["event_date_ad"]) for item in predictions}
                ),
            }
        )

    write_csv(paths["labels"], LABEL_COLUMNS, visible)
    write_csv(paths["reading"], READING_COLUMNS, reading)
    write_csv(paths["hidden"], HIDDEN_COLUMNS, hidden)

    positive_articles = sum(int(row["strict_v2_prediction_count"]) > 0 for row in hidden)
    positive_claims = sum(int(row["strict_v2_prediction_count"]) for row in hidden)
    manifest = {
        "design_version": VERSION,
        "seed": args.seed,
        "unit": "article",
        "eligible_definition": "class=1, in_nepal=1, specificity_ok=1, nonempty text",
        "eligible_frame_size": len(eligible),
        "previously_labelled_urls_excluded": len(spent),
        "overlap_with_prior_evaluation": len(set(drawn_urls) & spent),
        "sample_size": len(drawn),
        "population_by_stratum": {key: len(strata.get(key, [])) for key in QUOTAS},
        "sample_by_stratum": dict(sorted(drawn_counts.items())),
        "quotas": QUOTAS,
        "strict_v2_positive_articles_in_sample": positive_articles,
        "strict_v2_positive_claims_in_sample": positive_claims,
        "precision_power_warning": (
            "The current corpus has very few unspent strict-v2 positive predictions. "
            "If fewer than 20 predicted claims are present after exclusions, report "
            "precision descriptively with exact intervals and do not use v8 alone "
            "to authorize release integration."
        ),
        "truth_format": {
            "primary_district_date_true": "District|YYYY-MM-DD, or unclear",
            "additional_district_dates_true": (
                "semicolon-separated District|YYYY-MM-DD pairs, none, or unclear"
            ),
            "unresolved_additional_events_true": "yes or no",
        },
        "lock_hash": lock_hash(drawn_urls),
        "labels_sha256": sha256(paths["labels"]),
        "reading_pack_sha256": sha256(paths["reading"]),
        "hidden_predictions_sha256": sha256(paths["hidden"]),
        "exclusion_sources": exclusion_audit,
        "instructions": (
            "Open only the LABEL_HERE and reading_pack files while labeling. "
            "Do not open the predictions file until all labels are frozen."
        ),
    }
    paths["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"drew {len(drawn)} previously unjudged articles")
    for key in QUOTAS:
        print(f"  {key:24s} {drawn_counts.get(key, 0):3d} / {len(strata.get(key, [])):4d}")
    print(f"strict-v2 positives: {positive_articles} articles, {positive_claims} claims")
    print("wrote " + ", ".join(path.name for path in paths.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
