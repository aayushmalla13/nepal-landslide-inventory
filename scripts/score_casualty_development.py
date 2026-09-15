#!/usr/bin/env python3
"""Score casualty extraction against the labelled casualty development set.

Reports three numbers that matter for different reasons:

``recall``
    of the articles a human read a death count out of, how many does the
    extractor now produce a count for. This is the recall gap the work targets.

``precision``
    of the counts the extractor produces, how many are right. A recall gain
    bought with wrong numbers is worse than the gap.

``false zeros``
    how often the extractor writes 0 where the human left the value unknown.
    This one has a target of exactly zero, because the project's standing rule
    is that an unknown casualty value is never replaced by zero, and a wrong
    zero is invisible downstream -- it looks like a measurement.

Usage::

    PYTHONPATH=src python3 scripts/score_casualty_development.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from landslide_inventory.nlp_en.extract import extract_en  # noqa: E402
from landslide_inventory.nlp_np.extract import extract_np  # noqa: E402


def to_int(value: str) -> int | None:
    value = (value or "").strip()
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="data/outputs/casualty_development_casualty_v1.csv")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--outputs", default="data/outputs")
    args = parser.parse_args()

    import yaml

    keywords_cfg = dict(
        yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))["keywords"]
    )

    csv.field_size_limit(sys.maxsize)
    with (ROOT / args.labels).open("rt", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    scored = 0
    correct = 0
    produced = 0
    truth_has_count = 0
    recalled = 0
    false_zeros = 0
    missed_zeros = 0
    by_stratum: Counter[str] = Counter()
    errors: list[dict[str, object]] = []

    for row in rows:
        raw_truth = row.get("deaths_true", "")
        if raw_truth == "" and (row.get("notes") or "").strip() == "":
            continue  # not labelled
        scored += 1
        truth = to_int(raw_truth)
        extractor = extract_np if row.get("route_lang") == "np" else extract_en
        result = extractor(
            row.get("title") or None,
            row.get("text") or "",
            None,
            None,
            keywords_cfg,
        )
        got = result.get("deaths")

        if truth is not None and truth > 0:
            truth_has_count += 1
            if got is not None and got > 0:
                recalled += 1
        if got is not None:
            produced += 1
        if got == truth:
            correct += 1
        else:
            if got == 0 and truth is None:
                false_zeros += 1
            if truth == 0 and got != 0:
                missed_zeros += 1
            by_stratum[row.get("stratum", "?")] += 1
            errors.append(
                {
                    "row_id": row.get("row_id", ""),
                    "stratum": row.get("stratum", ""),
                    "language": row.get("route_lang", ""),
                    "deaths_true": raw_truth,
                    "deaths_extracted": "" if got is None else got,
                    "title": (row.get("title") or "")[:100],
                    "notes": row.get("notes", ""),
                }
            )

    summary = {
        "labelled_rows_scored": scored,
        "exact_agreement": correct,
        "exact_agreement_rate": round(correct / scored, 4) if scored else None,
        "rows_where_a_human_read_a_count": truth_has_count,
        "of_those_a_count_was_extracted": recalled,
        "recall_on_counts": round(recalled / truth_has_count, 4) if truth_has_count else None,
        "false_zeros": false_zeros,
        "explicit_zeros_missed": missed_zeros,
        "errors_by_stratum": dict(by_stratum),
        "note": (
            "Development diagnostics for rule design only. Not held-out "
            "performance. false_zeros must stay at 0: writing 0 where the "
            "article does not state that nobody was harmed violates the "
            "project's standing rule against imputing zero."
        ),
    }

    outputs = ROOT / args.outputs
    (outputs / "casualty_development_score.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    error_path = outputs / "casualty_development_errors.csv"
    columns = [
        "row_id",
        "stratum",
        "language",
        "deaths_true",
        "deaths_extracted",
        "title",
        "notes",
    ]
    with error_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(errors)

    for key, value in summary.items():
        if key != "note":
            print(f"{key:38} {value}")
    print(f"wrote {error_path.relative_to(ROOT)} ({len(errors)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
