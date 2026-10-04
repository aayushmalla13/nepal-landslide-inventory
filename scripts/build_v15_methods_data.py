#!/usr/bin/env python3
"""Generate paper-ready Methods and Data material from frozen v1.5 evidence."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ID = "nepal_landslide_inventory_v1.5.0_event_detection_validated_20261004"
RELEASE = ROOT / "data/releases" / RELEASE_ID
OUTPUTS = ROOT / "data/outputs"
OUTPUT = ROOT / "docs/V15_METHODS_AND_DATA.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def article_counts(database: Path) -> tuple[int, Counter[str]]:
    with sqlite3.connect(database) as connection:
        total = int(connection.execute("SELECT COUNT(*) FROM raw_articles").fetchone()[0])
        counts = Counter(
            {
                str(source): int(count)
                for source, count in connection.execute(
                    "SELECT source, COUNT(*) FROM raw_articles GROUP BY source"
                )
            }
        )
    return total, counts


def yes_no_counts(rows: list[dict[str, str]], field: str) -> Counter[str]:
    return Counter((row.get(field) or "blank").strip().lower() for row in rows)


def attribute_profile(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        "municipality": sum(bool(row["municipality"].strip()) for row in rows),
        "known_trigger": sum(
            (row["trigger"] or "").strip().lower() not in {"", "unknown"}
            for row in rows
        ),
        "deaths": sum(bool(row["deaths"].strip()) for row in rows),
        "missing": sum(bool(row["missing"].strip()) for row in rows),
        "injured": sum(bool(row["injured"].strip()) for row in rows),
        "multi_article": sum(int(row["cluster_size"] or 0) > 1 for row in rows),
        "full_text_basis": sum(row["extraction_basis"] == "full_text" for row in rows),
        "date_conf_ge_078": sum(float(row["conf_date"] or 0) >= 0.78 for row in rows),
        "date_conf_ge_080": sum(float(row["conf_date"] or 0) >= 0.80 for row in rows),
        "date_conf_ge_090": sum(float(row["conf_date"] or 0) >= 0.90 for row in rows),
    }


def sampling_strata(weights: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in weights:
        stratum = row["stratum"]
        grouped.setdefault(
            stratum,
            {
                "stratum": stratum,
                "population_n": int(row["population_n"]),
                "sample_n": int(row["sample_n"]),
                "weight": float(row["sampling_weight"]),
            },
        )
    return sorted(grouped.values(), key=lambda row: str(row["stratum"]))


def render() -> str:
    manifest = read_json(RELEASE / "release_manifest.json")
    validation = read_json(RELEASE / "validation/v15_final_validation_score.json")
    profile = read_json(OUTPUTS / "v15_inventory_profile.json")
    external = read_json(
        ROOT
        / "data/releases/nepal_landslide_external_validation_v0.2.0_20261004/external_agreement.json"
    )
    rainfall = read_json(OUTPUTS / "rainfall_analysis_report.json")
    interrater = read_json(OUTPUTS / "canonical_event_audit_interannotator_agreement.json")
    canonical = read_csv(RELEASE / "canonical_events_final.csv")
    audit = read_csv(RELEASE / "validation/v15_final_validation_COMPLETED.csv")
    weights = read_csv(RELEASE / "validation/v15_final_validation_weights.csv")
    corrections = read_csv(RELEASE / "correction_application_log.csv")
    strata = sampling_strata(weights)
    attributes = attribute_profile(canonical)

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    language_by_source = {source["slug"]: source["language"] for source in config["sources"]}
    total_articles, raw_by_source = article_counts(
        ROOT / "data/raw_sqlite/landslide_inventory.sqlite"
    )
    event_by_source = Counter(row["representative_source"] for row in canonical)
    article_by_language = Counter()
    event_by_language = Counter()
    for source, count in raw_by_source.items():
        article_by_language[language_by_source.get(source, "unknown")] += count
    for source, count in event_by_source.items():
        event_by_language[language_by_source.get(source, "unknown")] += count

    action_counts = Counter(row["action"] for row in corrections)
    non_events = yes_no_counts(audit, "event_really_happened")["no"]
    multi_events = yes_no_counts(audit, "one_physical_event")["no"]
    district_errors = yes_no_counts(audit, "district_correct")["no"]
    date_errors = yes_no_counts(audit, "date_correct")["no"]
    municipality_errors = yes_no_counts(audit, "municipality_correct")["no"]
    duplicate_errors = yes_no_counts(audit, "duplicate_merge_correct")["no"]
    missing_districts = ["Kanchanpur", "Saptari", "Siraha"]
    total = len(canonical)

    lines = [
        "# v1.5 Methods and Data",
        "",
        "**Generated file - do not edit numeric results by hand.** Rebuild with",
        "`PYTHONPATH=src python3 scripts/build_v15_methods_data.py`.",
        "",
        "## Processing workflow",
        "",
        "```mermaid",
        "flowchart LR",
        f"    A[Collected articles<br/>{total_articles:,}] --> B[Date and language normalization]",
        "    B --> C[English and Nepali event extraction]",
        "    C --> D[Event specificity and Nepal scope]",
        "    D --> E[District consistency and event typing]",
        "    E --> F[Cross-source deduplication]",
        f"    F --> G[Human review and {len(corrections)} logged release actions]",
        f"    G --> H[Frozen canonical inventory<br/>{total:,} records]",
        "    H --> I[Fresh locked probability audit<br/>150 of 568 eligible records]",
        "    H --> J[BIPAD agreement analysis]",
        "    H --> K[Matched district-day rainfall analysis]",
        "```",
        "",
        "The workflow preserves raw article evidence separately from canonical events.",
        "External BIPAD and COOLR records are never silently inserted into the news",
        "inventory, preventing circular validation. Full article text remains in the",
        "local evidence database and is not part of the public release.",
        "",
        "## Corpus and inventory scope",
        "",
        f"The collection contains {total_articles:,} articles from {len(raw_by_source)}",
        f"observed source slugs ({len(language_by_source)} configured sources plus one",
        "legacy one-row source). The frozen release contains",
        f"{total:,} canonical report clusters dated {profile['date_min']} to",
        f"{profile['date_max']}, covering {profile['districts_represented']} of Nepal's",
        "77 districts. Kanchanpur, Saptari, and Siraha have no retained canonical",
        "record; absence from this media inventory is not evidence of hazard absence.",
        "",
        "| Language route | Collected articles | Final representative records |",
        "|---|---:|---:|",
        f"| English | {article_by_language['en']:,} | {event_by_language['en']:,} |",
        f"| Nepali | {article_by_language['np']:,} | {event_by_language['np']:,} |",
        f"| Legacy/unmapped | {article_by_language['unknown']:,} | {event_by_language['unknown']:,} |",
        "",
        "### Publisher coverage",
        "",
        "| Publisher | Language | Collected articles | Final records | Final share |",
        "|---|---|---:|---:|---:|",
    ]
    for source in sorted(set(raw_by_source) | set(event_by_source)):
        events = event_by_source[source]
        lines.append(
            f"| {source} | {language_by_source.get(source, 'unknown')} | "
            f"{raw_by_source[source]:,} | {events:,} | {events / total:.1%} |"
        )

    lines += [
        "",
        "The three largest representative publishers account for",
        f"{profile['top_three_source_share']:.1%} of final records. Two publishers occur",
        "only in the development period, three only in the temporal-test period, and",
        "eleven contribute to both. Raw annual counts must therefore be interpreted",
        "alongside publisher composition rather than as an unbiased incidence trend.",
        "",
        "## Final inventory composition",
        "",
        "| Characteristic | Count | Share |",
        "|---|---:|---:|",
        f"| Landslide event type | {profile['event_type_counts'].get('landslide', 0):,} | {profile['event_type_counts'].get('landslide', 0) / total:.1%} |",
        f"| Road-obstruction event type | {profile['event_type_counts'].get('road_obstruction', 0):,} | {profile['event_type_counts'].get('road_obstruction', 0) / total:.1%} |",
        f"| Multi-article support | {attributes['multi_article']:,} | {attributes['multi_article'] / total:.1%} |",
        f"| Municipality populated | {attributes['municipality']:,} | {attributes['municipality'] / total:.1%} |",
        f"| Known trigger populated | {attributes['known_trigger']:,} | {attributes['known_trigger'] / total:.1%} |",
        f"| Death count populated | {attributes['deaths']:,} | {attributes['deaths'] / total:.1%} |",
        f"| Missing-person count populated | {attributes['missing']:,} | {attributes['missing'] / total:.1%} |",
        f"| Injury count populated | {attributes['injured']:,} | {attributes['injured'] / total:.1%} |",
        f"| Date confidence >=0.78 | {attributes['date_conf_ge_078']:,} | {attributes['date_conf_ge_078'] / total:.1%} |",
        f"| Date confidence >=0.80 | {attributes['date_conf_ge_080']:,} | {attributes['date_conf_ge_080'] / total:.1%} |",
        f"| Date confidence >=0.90 | {attributes['date_conf_ge_090']:,} | {attributes['date_conf_ge_090'] / total:.1%} |",
        f"| June-September records | {profile['monsoon_events_jun_sep']:,} | {profile['monsoon_share_jun_sep']:.1%} |",
        "",
        "Blank casualty fields mean not reported or not reliably extracted, not zero.",
        "All released rows carry exact ISO-formatted dates structurally, but the locked",
        "audit shows that an exact-looking date is not always the true occurrence date.",
        "",
        "## Release corrections and provenance",
        "",
        f"The v1.5 assembly applied {len(corrections)} logged actions without changing the",
        "frozen v1.4 source. Every action records its layer, affected ID, changed fields,",
        "reviewer, and notes.",
        "",
        "| Release action | Count |",
        "|---|---:|",
    ]
    for action, count in action_counts.most_common():
        lines.append(f"| `{action}` | {count} |")

    lines += [
        "",
        "## Locked validation design",
        "",
        "The final evaluation was drawn only after the candidate was frozen. Previously",
        "reviewed events and article evidence were excluded from the eligible frame.",
        "The remaining frame contained 568 records. A 150-record stratified probability",
        "sample used language, time period, event type, and single-versus-multi-article",
        "support as strata. Estimates use inverse-probability weights and confidence",
        "intervals use within-stratum bootstrap resampling. The sample is spent and must",
        "not be reused to validate a repaired future candidate.",
        "",
        "| Stratum | Population | Sample | Weight |",
        "|---|---:|---:|---:|",
    ]
    for row in strata:
        lines.append(
            f"| `{row['stratum']}` | {row['population_n']} | {row['sample_n']} | "
            f"{row['weight']:.3f} |"
        )

    lines += [
        "",
        "### Validation results",
        "",
        "| Metric | Weighted estimate | 95% CI | Decision |",
        "|---|---:|---:|---|",
    ]
    checks = validation["promotion_decision"]["checks"]
    metric_order = (
        ("event_existence_precision", "Event-existence precision"),
        ("usable_record_precision", "Usable-record precision"),
        ("single_event_accuracy", "Single-event accuracy"),
        ("district_accuracy", "District accuracy"),
        ("date_accuracy", "Exact-date accuracy"),
        ("municipality_accuracy", "Municipality accuracy"),
        ("event_type_accuracy", "Event-type accuracy"),
        ("hazard_type_accuracy", "Hazard-type accuracy"),
        ("deaths_exact_accuracy", "Deaths exact accuracy"),
        ("duplicate_merge_accuracy", "Duplicate-merge accuracy"),
    )
    for key, label in metric_order:
        metric = validation["metrics"][key]
        low, high = metric["ci95_stratified_bootstrap"]
        decision = (
            "pass" if key in checks and checks[key]["passed"] else
            "fail" if key in checks else "descriptive"
        )
        lines.append(
            f"| {label} | {metric['estimate']:.3f} | {low:.3f}-{high:.3f} | {decision} |"
        )

    lines += [
        "",
        "### Observed error taxonomy",
        "",
        "Counts below are raw sample counts and may overlap; weighted estimates above",
        "are the inferential results.",
        "",
        "| Error category | Sample count |",
        "|---|---:|",
        f"| No landslide event | {non_events} |",
        f"| Multiple physical events represented as one record | {multi_events} |",
        f"| District incorrect | {district_errors} |",
        f"| Exact date incorrect | {date_errors} |",
        f"| Municipality incorrect | {municipality_errors} |",
        f"| Duplicate merge incorrect | {duplicate_errors} |",
        "",
        "## Annotation reliability",
        "",
        "A separate earlier 150-row canonical-event audit was independently reviewed by",
        "two human annotators. This is an annotation-reliability study, not the fresh",
        "v1.5 performance sample. Agreement was 0.973 (kappa 0.874) for whether an event",
        "occurred, 0.969 (kappa 0.897) for district correctness, and 0.823 (kappa 0.613)",
        "for date correctness. Lower date agreement reinforces the final audit's finding",
        "that temporal assignment is the principal unresolved measurement limitation.",
        "",
        "## External agreement and rainfall triangulation",
        "",
        f"The common BIPAD frame contains {external['layer2_overlap']['news_total']:,}",
        f"news events and {external['layer2_overlap']['bipad_total']:,} harmonized BIPAD",
        f"clusters. Tier-A observed overlap is {external['layer3_chance_corrected']['tier_A']['observed_overlap']:.3f}",
        f"versus {external['layer3_chance_corrected']['tier_A']['expected_by_chance']:.3f}",
        "under date permutation. BIPAD is incomplete and is not treated as ground truth.",
        "",
        f"The rainfall analysis includes {rainfall['variants']['primary_conf_ge_0.78']['cases']:,}",
        f"primary case-days and {rainfall['variants']['primary_conf_ge_0.78']['controls']:,}",
        "matched controls. Its concurrent temporal-test AUC is",
        f"{rainfall['primary_temporal_test_result']['auc']:.3f}. Deliberate +/-1 and",
        "+/-3-day shifts materially change the selected rainfall window and threshold,",
        "so rainfall is reported as association and convergent validity, not as an",
        "operational early-warning rule.",
        "",
        "## Canonical data dictionary",
        "",
        "| Field group | Fields | Interpretation |",
        "|---|---|---|",
        "| Identity | `event_id`, `dedup_cluster_id` | Stable event and report-cluster identifiers |",
        "| Time and place | `event_date_ad`, `district`, `province`, `municipality` | Normalized event assignment; exact-date correctness is imperfect |",
        "| Event description | `event_type`, `hazard_type`, `trigger`, `event_granularity` | Parsed and reviewed event characterization |",
        "| Evidence | `representative_url`, `representative_source`, `representative_title`, `sources_json`, `cluster_size` | Traceable article support without redistributing full text |",
        "| Consequences | `deaths`, `missing`, `injured` | Blank means unknown/not reported, never an assumed zero |",
        "| Confidence | `conf_date`, `conf_class`, `extraction_basis` | Pipeline confidence and evidence mode, not calibrated probabilities |",
        "| Scope controls | `specificity_reason`, `in_nepal`, `scope_reason`, `location_consistent`, `location_reason` | Recorded inclusion and location checks |",
        "| Candidate detail | municipality, ward, and place-name JSON fields | Alternative extracted place evidence retained for auditability |",
        "",
        "## Interpretation boundary",
        "",
        "The release supports a validated high-precision event-detection claim and a",
        "validated district-assignment claim. It does not support claims of census",
        "completeness, high-precision full records, uniformly correct exact dates, or",
        "operational rainfall-warning performance. Publisher concentration, source",
        "turnover, missing districts, and severity-dependent news selection must remain",
        "visible in the paper rather than being treated as nuisance details.",
        "",
        f"Authoritative release: `{manifest['release_id']}`. Canonical SHA-256:",
        f"`{manifest['canonical_summary']['sha256']}`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUTPUT.write_text(render() + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
