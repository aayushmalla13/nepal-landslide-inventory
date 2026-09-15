#!/usr/bin/env python3
"""Draw a labelling sample for casualty extraction development.

Why a sample, and why before any pattern is written
---------------------------------------------------
``docs/MISSING_DATA_RECOVERY.md`` §5 scoped casualty backfill and then declined
to build it, for a specific reason: the failure mode is dangerous. "कुनै क्षति
भएको छैन" (no losses occurred) must become an explicit zero, "जानकारी आइसकेको
छैन" (no information yet) must stay unknown, and a count in the same article
often belongs to a different event. The project's standing rule is that an
unknown casualty value is never replaced by zero, so a pattern written from
intuition can quietly manufacture zeros that look like data.

The remedy is the project's usual one: draw a sample, label it blind of any
implementation, then write patterns and measure against it.

Strata
------
``death_language_no_count``
    class 1 or 2, death vocabulary present in the text, no death count
    extracted. This is the recall gap -- 933 articles, 703 of them Nepali.
``explicit_no_casualty``
    text contains a phrase asserting that nobody was hurt. These are the only
    articles that may legitimately produce a zero.
``not_yet_known``
    text says the toll is not yet established. These must stay unknown, and they
    are in the sample specifically as traps for an over-eager zero rule.
``has_count``
    a count was already extracted. Included as a control, so that a change can
    be shown not to damage what already worked.

Contamination control
---------------------
Every URL appearing in any locked test set or in a prior development set is
excluded before sampling, so this sample can be inspected freely without
spending an evaluation artifact.

Usage::

    PYTHONPATH=src python3 scripts/draw_casualty_development_set.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

VERSION = "casualty_v1"
SEED = 20260903
ALLOCATION = {
    "death_language_no_count": 70,
    "explicit_no_casualty": 30,
    "not_yet_known": 20,
    "has_count": 20,
}

DEATH_LANGUAGE = {
    "np": re.compile(r"(मृत्यु|मृतक|निधन|ज्यान\s*गुम|शव|मरे|मारिए)"),
    "en": re.compile(r"\b(died|dead|death|killed|deceased|bodies|body of)\b", re.I),
}

# Phrases asserting that nobody was harmed. Only these may license a zero.
EXPLICIT_NONE = {
    "np": re.compile(
        r"(मानवीय\s*क्षति\s*(?:भएको\s*छैन|छैन|भएन)"
        r"|कुनै\s*(?:प्रकारको\s*)?(?:मानवीय\s*)?क्षति\s*(?:भएको\s*छैन|छैन|भएन)"
        r"|हताहत\s*(?:भएको\s*छैन|छैन)"
        r"|कोही\s*(?:पनि\s*)?(?:हताहत|घाइते)\s*(?:भएको\s*छैन|छैन)"
        r"|कसैको\s*ज्यान\s*(?:गएको\s*छैन|गएन)"
        r"|ज्यानको\s*क्षति\s*(?:भएको\s*छैन|छैन))"
    ),
    "en": re.compile(
        r"(no\s+(?:human\s+)?(?:casualt|loss\s+of\s+life|death|fatalit)\w*"
        r"|no\s+one\s+(?:was|were|has\s+been)\s+(?:hurt|injured|killed)"
        r"|nobody\s+was\s+(?:hurt|injured|killed)"
        r"|there\s+(?:was|were)\s+no\s+(?:human\s+)?(?:loss|casualt)\w*"
        r"|escaped\s+unhurt|all\s+(?:were\s+)?(?:rescued|safe))",
        re.I,
    ),
}

# Phrases saying the toll is not yet established. These must stay unknown.
NOT_YET_KNOWN = {
    "np": re.compile(
        r"(जानकारी\s*(?:आइसकेको\s*छैन|प्राप्त\s*भएको\s*छैन|छैन)"
        r"|यकिन\s*(?:भइसकेको\s*छैन|हुन\s*सकेको\s*छैन|छैन)"
        r"|खुल्न\s*सकेको\s*छैन|पहिचान\s*(?:हुन\s*सकेको\s*छैन|खुलेको\s*छैन)"
        r"|विवरण\s*(?:आउन\s*बाँकी|आइसकेको\s*छैन))"
    ),
    "en": re.compile(
        r"(no\s+(?:information|details?|word|confirmation)\b"
        r"|details?\s+(?:are|is)\s+(?:not\s+)?yet"
        r"|yet\s+to\s+be\s+(?:ascertained|confirmed|determined|established)"
        r"|exact\s+(?:figure|number)\s+(?:is|has)\s+not)",
        re.I,
    ),
}


def read_gz(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:  # type: ignore[operator]
        return list(csv.DictReader(handle))


def prior_evaluation_urls() -> set[str]:
    """Every URL already spent on a locked or development evaluation."""

    urls: set[str] = set()
    for directory in (ROOT / "data" / "outputs", ROOT / "docs"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.csv")):
            name = path.name
            if not (name.startswith("locked_test_set_") or name.startswith("development_set_")):
                continue
            try:
                with path.open("rt", encoding="utf-8-sig", newline="") as handle:
                    for row in csv.DictReader(handle):
                        url = (row.get("url") or "").strip()
                        if url:
                            urls.add(url)
            except (OSError, csv.Error):
                continue
    return urls


def stable_order(rows: list[dict[str, str]], salt: str) -> list[dict[str, str]]:
    """Deterministic, seed-dependent ordering that does not depend on row order."""

    def key(row: dict[str, str]) -> str:
        material = f"{VERSION}|{SEED}|{salt}|{row.get('url','')}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    return sorted(rows, key=key)


def classify(row: dict[str, str]) -> str | None:
    language = "np" if (row.get("route_lang") or "en") == "np" else "en"
    text = row.get("text") or ""
    recorded = (row.get("deaths") or "").strip() not in ("", "None")
    if EXPLICIT_NONE[language].search(text):
        return "explicit_no_casualty"
    if NOT_YET_KNOWN[language].search(text):
        return "not_yet_known"
    if recorded:
        return "has_count"
    if DEATH_LANGUAGE[language].search(text):
        return "death_language_no_count"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="data/corpus/corpus_for_extraction.csv.gz")
    parser.add_argument("--outputs", default="data/outputs")
    args = parser.parse_args()

    excluded = prior_evaluation_urls()
    rows = [
        row
        for row in read_gz(ROOT / args.corpus)
        if row.get("class") in ("1", "2") and row.get("url") not in excluded
    ]

    buckets: dict[str, list[dict[str, str]]] = {name: [] for name in ALLOCATION}
    for row in rows:
        stratum = classify(row)
        if stratum in buckets:
            buckets[stratum].append(row)

    sample: list[dict[str, object]] = []
    population = {name: len(items) for name, items in buckets.items()}
    for stratum, quota in ALLOCATION.items():
        # Balance the languages within each stratum so a rule cannot be tuned on
        # one language and reported as if it generalised.
        by_language = {
            "np": stable_order([r for r in buckets[stratum] if r.get("route_lang") == "np"], stratum),
            "en": stable_order([r for r in buckets[stratum] if r.get("route_lang") != "np"], stratum),
        }
        picked: list[dict[str, str]] = []
        index = 0
        while len(picked) < quota and (
            index < len(by_language["np"]) or index < len(by_language["en"])
        ):
            for language in ("np", "en"):
                if len(picked) >= quota:
                    break
                if index < len(by_language[language]):
                    picked.append(by_language[language][index])
            index += 1
        for row in picked:
            sample.append(
                {
                    "row_id": f"cas-{len(sample) + 1:04d}",
                    "stratum": stratum,
                    "url": row.get("url", ""),
                    "source": row.get("source", ""),
                    "route_lang": row.get("route_lang", ""),
                    "class": row.get("class", ""),
                    "title": (row.get("title") or "").replace("\n", " "),
                    "text": re.sub(r"\s+", " ", row.get("text") or "").strip()[:1800],
                    "deaths_pred": (row.get("deaths") or "").strip(),
                    "missing_pred": (row.get("missing") or "").strip(),
                    "injured_pred": (row.get("injured") or "").strip(),
                    # annotator fills these; blank means unknown, 0 means the
                    # article states nobody was harmed
                    "deaths_true": "",
                    "missing_true": "",
                    "injured_true": "",
                    "notes": "",
                }
            )

    outputs = ROOT / args.outputs
    outputs.mkdir(parents=True, exist_ok=True)
    path = outputs / f"casualty_development_{VERSION}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sample[0]))
        writer.writeheader()
        writer.writerows(sample)

    manifest = {
        "version": VERSION,
        "seed": SEED,
        "allocation": ALLOCATION,
        "population_by_stratum": population,
        "sampled": len(sample),
        "sampled_by_stratum": dict(Counter(str(r["stratum"]) for r in sample)),
        "sampled_by_language": dict(Counter(str(r["route_lang"]) for r in sample)),
        "prior_evaluation_urls_excluded": len(excluded),
        "note": (
            "Development sample for casualty-rule design. Blank means unknown; "
            "0 means the article states that nobody was harmed. Never write 0 "
            "for an article that is merely silent about casualties."
        ),
    }
    (outputs / f"casualty_development_{VERSION}_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"population by stratum : {population}")
    print(f"sampled               : {len(sample)} {manifest['sampled_by_stratum']}")
    print(f"by language           : {manifest['sampled_by_language']}")
    print(f"prior-evaluation URLs excluded: {len(excluded)}")
    print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
