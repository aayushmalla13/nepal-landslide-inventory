#!/usr/bin/env python3
"""Assemble validated post-correction plans into a locked candidate release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from landslide_inventory.gazetteer import all_districts, district_to_province
from landslide_inventory.gazetteer_municipality import (
    municipality_districts,
    normalize_municipality,
)

DEFAULT_RELEASE_ID = "nepal_landslide_inventory_v0.8.0_candidate_20260923"
SOURCE_RELEASE_ID = "nepal_landslide_inventory_v0.7.0_candidate_20260916"
EXPECTED_SOURCE_ROWS = 2904
EXPECTED_ROWS = 2872

PLAN_FILES = {
    "remove": "post_correction_identity_plan_REMOVE_OLD_EVENTS.csv",
    "new": "post_correction_identity_plan_NEW_EVENTS.csv",
    "merge": "post_correction_identity_plan_MERGES_EXISTING.csv",
    "identity_excluded": "post_correction_identity_plan_EXCLUDED_CANDIDATES.csv",
    "true_corrections": "post_correction_true_value_plan_CORRECTIONS.csv",
    "true_exclusions": "post_correction_true_value_plan_EXCLUSIONS.csv",
    "structured_corrections": (
        "post_correction_structured_attribute_plan_CORRECTIONS.csv"
    ),
    "structured_exclusions": (
        "post_correction_structured_attribute_plan_EXCLUSIONS.csv"
    ),
}
PLAN_MANIFESTS = {
    "post_correction_identity_plan_manifest.json": (
        "post_correction_identity_plan_unapplied_parser_fixes_and_attribute_gates_pending"
    ),
    "post_correction_true_value_plan_manifest.json": (
        "post_correction_true_value_plan_unapplied_attributes_pending"
    ),
    "post_correction_structured_attribute_plan_manifest.json": (
        "all_post_correction_manual_gates_complete_candidate_assembly_pending"
    ),
}

DISTRICT_ALIASES = {
    "Nawalparasi (Bardaghat Susta East)": "Nawalpur",
    "Nawalparasi": "Nawalpur",
    "Tanahun": "Tanahu",
}
LOCATION_OVERRIDES = {
    "postcorr_candidate_7b2a51eea180d84c": {
        "district": "Baglung",
        "municipality": "Baglung Municipality",
        "reason": (
            "Recovered full publisher text places the 2025-08-08 blockage at "
            "Kalakhola, Baglung Municipality-12, Baglung."
        ),
    }
}
ARTICLE_DATABASE_RELATIVE = Path("data/raw_sqlite/landslide_inventory.sqlite")
ASSEMBLER_SCRIPT = Path(__file__)
README_TITLE = "Post-correction inventory candidate"
README_PLAN_LABEL = "post-correction"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_list(raw: str) -> list[str]:
    value = json.loads(raw or "[]")
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Expected a JSON string list, got {raw!r}")
    return value


def release_value(raw: str) -> str:
    return "" if raw in {"", "not_reported"} else raw


def verify_plan_provenance(root: Path, source_csv: Path) -> dict[str, str]:
    outputs = root / "data" / "outputs"
    source_hash = sha256(source_csv)
    observed: dict[str, str] = {}
    for name, expected_status in PLAN_MANIFESTS.items():
        path = outputs / name
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["status"] != expected_status:
            raise ValueError(f"Plan manifest is not release-ready: {name}")
        observed[str(path.relative_to(root))] = sha256(path)
        for output_name, expected_hash in manifest["output_sha256"].items():
            output_path = outputs / output_name
            actual_hash = sha256(output_path)
            if actual_hash != expected_hash:
                raise ValueError(f"Plan output checksum mismatch: {output_name}")
            observed[str(output_path.relative_to(root))] = actual_hash
        source_entries = {
            key: value
            for key, value in manifest["input_sha256"].items()
            if key.endswith("canonical_events_final.csv")
        }
        if source_entries and source_hash not in source_entries.values():
            raise ValueError(f"{name} is not pinned to the configured source inventory")
    return observed


def load_article_metadata(database: Path, urls: set[str]) -> dict[str, dict[str, str]]:
    if not urls:
        return {}
    placeholders = ",".join("?" for _ in urls)
    query = f"""
        SELECT url, source, title, trigger, conf_date, conf_class
        FROM article_events
        WHERE url IN ({placeholders})
    """
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, tuple(sorted(urls))).fetchall()
    metadata = {
        row["url"]: {key: str(row[key] or "") for key in row.keys()} for row in rows
    }
    missing = sorted(urls - set(metadata))
    if missing:
        raise ValueError(f"Article metadata missing for planned URLs: {missing[:3]}")
    return metadata


def _candidate_suffix(candidate_id: str) -> str:
    prefix = "postcorr_candidate_"
    if not candidate_id.startswith(prefix):
        raise ValueError(f"Unexpected candidate ID: {candidate_id}")
    return candidate_id.removeprefix(prefix)


def canonical_location(
    plan: dict[str, str], location_log: list[dict[str, str]]
) -> tuple[str, str]:
    candidate_id = plan["candidate_event_id"]
    raw_district = plan["district"].strip()
    raw_municipality = plan["municipality"].strip()
    override = LOCATION_OVERRIDES.get(candidate_id)
    if override:
        district = override["district"]
        municipality = override["municipality"]
        reason = override["reason"]
    else:
        district = DISTRICT_ALIASES.get(raw_district, raw_district)
        reason = "Canonical district alias and municipality normalization."
        municipality = ""
        if raw_municipality and raw_municipality.casefold() != "unclear":
            if "/" not in raw_municipality and "border" not in raw_municipality.casefold():
                municipality = normalize_municipality(raw_municipality, "en") or ""

    if district not in set(all_districts()):
        raise ValueError(f"{candidate_id}: noncanonical district remains: {district}")
    if municipality:
        allowed = municipality_districts(municipality)
        if not allowed or district not in allowed:
            municipality = ""
            reason += " Municipality was blanked because it conflicts with the district."

    if district != raw_district or municipality != raw_municipality:
        location_log.append(
            {
                "candidate_event_id": candidate_id,
                "raw_district": raw_district,
                "final_district": district,
                "raw_municipality": raw_municipality,
                "final_municipality": municipality,
                "reason": reason,
            }
        )
    return district, municipality


def _append_manual_history(row: dict[str, str], entry: dict[str, Any]) -> None:
    payload = json.loads(row.get("event_payload") or "{}")
    payload.setdefault("manual_release_actions", []).append(entry)
    row["event_payload"] = compact_json(payload)


def _reviewer(plan: dict[str, str]) -> str:
    return plan.get("reviewed_by") or plan.get("reviewed_by_final", "")


def _review_notes(plan: dict[str, str]) -> str:
    return (
        plan.get("review_notes")
        or plan.get("final_collision_notes")
        or plan.get("reason", "")
    )


def _new_event_row(
    plan: dict[str, str],
    articles: dict[str, dict[str, str]],
    columns: list[str],
    location_log: list[dict[str, str]],
) -> dict[str, str]:
    candidate_id = plan["candidate_event_id"]
    suffix = _candidate_suffix(candidate_id)
    urls = parse_list(plan["article_urls_json"])
    if not urls:
        raise ValueError(f"{candidate_id}: reconstructed event has no articles")
    representative_url = urls[0]
    representative = articles[representative_url]
    sources = sorted({articles[url]["source"] for url in urls})
    district, municipality = canonical_location(plan, location_log)
    payload = {
        "urls": sorted(urls),
        "sources": sources,
        "size": len(set(urls)),
        "representative_url": representative_url,
        "municipality_candidates": [municipality] if municipality else [],
        "ward_candidates": [],
        "place_name_candidates": [district],
        "manual_reconstruction": {
            "candidate_event_id": candidate_id,
            "old_event_id": plan["old_event_id"],
            "article_mapping_ids": parse_list(plan["article_mapping_ids_json"]),
            "evidence": plan["evidence"],
            "reviewed_by": _reviewer(plan),
            "review_notes": _review_notes(plan),
        },
    }
    values = {column: "" for column in columns}
    values.update(
        {
            "event_id": f"event_{suffix}",
            "dedup_cluster_id": f"cluster_{suffix}",
            "event_date_ad": plan["event_date"],
            "district": district,
            "province": district_to_province(district),
            "municipality": municipality,
            "event_type": plan["event_type"],
            "hazard_type": plan["hazard_type"],
            "event_granularity": "single",
            "article_role": "first_report",
            "extraction_basis": "manual_post_correction_reconstruction",
            "cluster_size": str(len(set(urls))),
            "sources_json": compact_json(sources),
            "representative_url": representative_url,
            "representative_source": representative["source"],
            "representative_title": representative["title"],
            "trigger": representative["trigger"] or "unknown",
            "deaths": release_value(plan["deaths"]),
            "conf_date": representative["conf_date"],
            "conf_class": representative["conf_class"],
            "specificity_reason": "manual_post_correction_reconstruction",
            "in_nepal": "1",
            "scope_reason": "manual_post_correction_review",
            "location_consistent": "1",
            "location_reason": "manual_post_correction_review",
            "municipality_candidates_json": compact_json(
                [municipality] if municipality else []
            ),
            "ward_candidates_json": "[]",
            "place_name_candidates_json": compact_json([district]),
            "event_payload": compact_json(payload),
        }
    )
    return values


def _log_row(
    action: str,
    event_id: str,
    candidate_id: str,
    layer: str,
    plan: dict[str, str],
    fields: list[str] | None = None,
) -> dict[str, str]:
    return {
        "action": action,
        "event_id": event_id,
        "candidate_id": candidate_id,
        "layer": layer,
        "changed_fields_json": compact_json(fields or []),
        "reviewed_by": _reviewer(plan),
        "review_notes": _review_notes(plan),
    }


def _history_entry(layer: str, plan: dict[str, str], fields: list[str]) -> dict[str, Any]:
    return {
        "layer": layer,
        "queue_id": plan["queue_id"],
        "changed_fields": fields,
        "reviewed_by": _reviewer(plan),
        "review_notes": _review_notes(plan),
    }


def _provenance_rows(
    event_id: str,
    plan: dict[str, str],
    articles: dict[str, dict[str, str]],
    action: str,
) -> list[dict[str, str]]:
    return [
        {
            "event_id": event_id,
            "candidate_event_id": plan["candidate_event_id"],
            "action": action,
            "url": url,
            "source": articles[url]["source"],
            "title": articles[url]["title"],
        }
        for url in parse_list(plan["article_urls_json"])
    ]


def assemble_rows(
    source_rows: list[dict[str, str]],
    plans: dict[str, list[dict[str, str]]],
    articles: dict[str, dict[str, str]],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    if len(source_rows) != EXPECTED_SOURCE_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_SOURCE_ROWS} source rows, found {len(source_rows)}"
        )
    columns = list(source_rows[0])
    source_by_id = {row["event_id"]: deepcopy(row) for row in source_rows}
    if len(source_by_id) != len(source_rows):
        raise ValueError("Source inventory contains duplicate event IDs")

    remove_ids = {row["old_event_id"] for row in plans["remove"]}
    exclusion_ids = {row["event_id"] for row in plans["true_exclusions"]}
    correction_groups = ("true_corrections", "structured_corrections")
    correction_ids = {
        row["event_id"] for key in correction_groups for row in plans[key]
    }
    merge_targets = {row["merge_existing_event_id"] for row in plans["merge"]}
    if (
        remove_ids & (exclusion_ids | correction_ids | merge_targets)
        or exclusion_ids & correction_ids
        or plans["structured_exclusions"]
    ):
        raise ValueError("Manual plan layers overlap or contain unexpected exclusions")
    missing = (remove_ids | exclusion_ids | correction_ids | merge_targets) - set(source_by_id)
    if missing:
        raise ValueError(f"Plan targets are absent from source inventory: {sorted(missing)[:3]}")

    rows = {
        event_id: row for event_id, row in source_by_id.items() if event_id not in remove_ids
    }
    log: list[dict[str, str]] = []
    provenance: list[dict[str, str]] = []
    location_log: list[dict[str, str]] = []

    for plan in plans["remove"]:
        log.append(_log_row("remove_superseded", plan["old_event_id"], "", "identity", plan))

    for plan in plans["identity_excluded"]:
        log.append(
            _log_row(
                "exclude_reconstruction_candidate",
                "",
                plan["candidate_event_id"],
                "identity",
                plan,
            )
        )

    for plan in plans["merge"]:
        target_id = plan["merge_existing_event_id"]
        target = rows[target_id]
        payload = json.loads(target.get("event_payload") or "{}")
        merged_urls = parse_list(plan["article_urls_json"])
        urls = sorted(set(payload.get("urls", [])) | set(merged_urls))
        sources = sorted(
            set(payload.get("sources", []))
            | {articles[url]["source"] for url in merged_urls}
        )
        payload.update({"urls": urls, "sources": sources, "size": len(urls)})
        payload.setdefault("manual_identity_merges", []).append(
            {
                "candidate_event_id": plan["candidate_event_id"],
                "old_event_id": plan["old_event_id"],
                "evidence": plan["evidence"],
                "reviewed_by": _reviewer(plan),
                "review_notes": _review_notes(plan),
            }
        )
        target["event_payload"] = compact_json(payload)
        target["cluster_size"] = str(len(urls))
        target["sources_json"] = compact_json(sources)
        log.append(
            _log_row(
                "merge_into_existing",
                target_id,
                plan["candidate_event_id"],
                "identity",
                plan,
            )
        )
        provenance.extend(
            _provenance_rows(target_id, plan, articles, "merge_into_existing")
        )

    for plan in plans["new"]:
        new_row = _new_event_row(plan, articles, columns, location_log)
        event_id = new_row["event_id"]
        if event_id in rows:
            raise ValueError(f"Generated event ID collision: {event_id}")
        rows[event_id] = new_row
        log.append(
            _log_row(
                "add_reconstructed",
                event_id,
                plan["candidate_event_id"],
                "identity",
                plan,
            )
        )
        provenance.extend(_provenance_rows(event_id, plan, articles, "add_reconstructed"))

    for plan in plans["true_exclusions"]:
        rows.pop(plan["event_id"])
        log.append(
            _log_row(
                "exclude_existing",
                plan["event_id"],
                plan["queue_id"],
                "true_value",
                plan,
            )
        )

    for plan in plans["true_corrections"]:
        row = rows[plan["event_id"]]
        row.update(
            {
                "event_date_ad": plan["final_event_date"],
                "district": plan["final_district"],
                "province": plan["final_province"],
                "municipality": plan["final_municipality"],
                "event_type": plan["final_event_type"],
                "hazard_type": plan["final_hazard_type"],
                "deaths": release_value(plan["final_deaths"]),
            }
        )
        fields = parse_list(plan["changed_fields_json"])
        _append_manual_history(row, _history_entry("true_value", plan, fields))
        log.append(
            _log_row(
                "correct_attributes",
                plan["event_id"],
                plan["queue_id"],
                "true_value",
                plan,
                fields,
            )
        )

    for plan in plans["structured_corrections"]:
        row = rows[plan["event_id"]]
        row.update(
            {
                "event_type": plan["final_event_type"],
                "hazard_type": plan["final_hazard_type"],
                "deaths": release_value(plan["final_deaths"]),
            }
        )
        fields = parse_list(plan["changed_fields_json"])
        _append_manual_history(row, _history_entry("structured_attribute", plan, fields))
        log.append(
            _log_row(
                "correct_attributes",
                plan["event_id"],
                plan["queue_id"],
                "structured_attribute",
                plan,
                fields,
            )
        )

    assembled = sorted(
        rows.values(), key=lambda row: (row["event_date_ad"], row["district"], row["event_id"])
    )
    if len(assembled) != EXPECTED_ROWS:
        raise ValueError(f"Expected {EXPECTED_ROWS} assembled rows, got {len(assembled)}")
    if len({row["event_id"] for row in assembled}) != len(assembled):
        raise ValueError("Assembled inventory contains duplicate event IDs")
    valid_districts = set(all_districts())
    invalid_districts = sorted({row["district"] for row in assembled} - valid_districts)
    if invalid_districts:
        raise ValueError(f"Assembled inventory has invalid districts: {invalid_districts}")
    location_reviewed_ids = {
        f"event_{_candidate_suffix(row['candidate_event_id'])}"
        for row in plans["new"]
    } | {row["event_id"] for row in plans["true_corrections"]}
    for row in assembled:
        if row["event_id"] not in location_reviewed_ids:
            continue
        municipality = row["municipality"]
        if municipality and row["district"] not in municipality_districts(municipality):
            raise ValueError(
                f"{row['event_id']}: municipality {municipality} conflicts with district"
            )
    return assembled, log, provenance, location_log


def write_snapshot(
    path: Path, rows: list[dict[str, str]], release_id: str, csv_hash: str
) -> None:
    columns = list(rows[0])
    definitions = ", ".join(
        f'"{column}" TEXT PRIMARY KEY' if column == "event_id" else f'"{column}" TEXT'
        for column in columns
    )
    placeholders = ",".join("?" for _ in columns)
    with sqlite3.connect(path) as connection:
        connection.execute(f"CREATE TABLE canonical_events ({definitions})")
        connection.executemany(
            f"INSERT INTO canonical_events VALUES ({placeholders})",
            ([row[column] for column in columns] for row in rows),
        )
        connection.execute(
            "CREATE INDEX canonical_events_date_district "
            "ON canonical_events(event_date_ad, district)"
        )
        connection.execute(
            "CREATE TABLE release_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO release_metadata VALUES (?, ?)",
            (
                ("release_id", release_id),
                ("status", "pending_fresh_validation"),
                ("supersedes", SOURCE_RELEASE_ID),
                ("canonical_csv_sha256", csv_hash),
                ("canonical_rows", str(len(rows))),
            ),
        )


def verify_snapshot(path: Path, rows: list[dict[str, str]], csv_hash: str) -> None:
    columns = list(rows[0])
    quoted = ", ".join(f'"{column}"' for column in columns)
    with sqlite3.connect(path) as connection:
        database_rows = connection.execute(
            f"SELECT {quoted} FROM canonical_events "
            "ORDER BY event_date_ad, district, event_id"
        ).fetchall()
        metadata = dict(connection.execute("SELECT key, value FROM release_metadata"))
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    csv_rows = [tuple(row[column] for column in columns) for row in rows]
    if database_rows != csv_rows:
        raise ValueError("SQLite canonical_events content differs from the CSV")
    if metadata["canonical_csv_sha256"] != csv_hash:
        raise ValueError("SQLite metadata does not pin the canonical CSV")
    if integrity != "ok":
        raise ValueError(f"SQLite integrity check failed: {integrity}")


def build_release(
    root: Path, release_id: str, output_dir: Path, *, force: bool = False
) -> Path:
    source_dir = root / "data" / "releases" / SOURCE_RELEASE_ID
    source_csv = source_dir / "canonical_events_final.csv"
    source_manifest = source_dir / "release_manifest.json"
    outputs = root / "data" / "outputs"
    database = root / ARTICLE_DATABASE_RELATIVE
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(f"Release directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    input_hashes = verify_plan_provenance(root, source_csv)
    plans = {key: read_csv(outputs / name) for key, name in PLAN_FILES.items()}
    planned_urls = {
        url
        for key in ("new", "merge")
        for row in plans[key]
        for url in parse_list(row["article_urls_json"])
    }
    articles = load_article_metadata(database, planned_urls)
    rows, application_log, provenance, location_log = assemble_rows(
        read_csv(source_csv), plans, articles
    )

    canonical_path = output_dir / "canonical_events_final.csv"
    write_csv(canonical_path, rows, list(rows[0]))
    canonical_hash = sha256(canonical_path)
    snapshot_path = output_dir / "canonical_inventory.sqlite"
    if snapshot_path.exists():
        snapshot_path.unlink()
    write_snapshot(snapshot_path, rows, release_id, canonical_hash)
    verify_snapshot(snapshot_path, rows, canonical_hash)

    log_path = output_dir / "correction_application_log.csv"
    write_csv(log_path, application_log, list(application_log[0]))
    provenance_path = output_dir / "corrected_event_article_provenance.csv"
    write_csv(provenance_path, provenance, list(provenance[0]))
    location_path = output_dir / "reconstruction_location_normalizations.csv"
    location_columns = [
        "candidate_event_id",
        "raw_district",
        "final_district",
        "raw_municipality",
        "final_municipality",
        "reason",
    ]
    write_csv(location_path, location_log, location_columns)

    report_path = output_dir / "CORRECTED_RELEASE_README.md"
    report_path.write_text(
        "\n".join(
            [
                f"# {README_TITLE}",
                "",
                f"Release: `{release_id}`",
                f"Rows: {len(rows):,}",
                f"Supersedes: `{SOURCE_RELEASE_ID}`",
                "Status: pending fresh independent validation.",
                "",
                f"This candidate applies every validated {README_PLAN_LABEL} manual plan.",
                "It must not inherit accuracy metrics from v0.7 or earlier releases.",
                "Rerun rainfall and external validation only after semantic release",
                "reconciliation, then draw a fresh locked audit before promotion.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    bundled_paths = (
        canonical_path,
        snapshot_path,
        log_path,
        provenance_path,
        location_path,
        report_path,
    )
    files = [
        {"file": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
        for path in bundled_paths
    ]
    lock_payload = compact_json(
        ["release_bundle", release_id, [[item["file"], item["sha256"]] for item in files]]
    )
    dates = [row["event_date_ad"] for row in rows]
    expected_log_rows = 61 + 29 + 11 + 42 + 13 + 31 + 25
    manifest = {
        "release_id": release_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_fresh_validation",
        "supersedes": SOURCE_RELEASE_ID,
        "canonical_summary": {
            "rows": len(rows),
            "unique_event_ids": len({row["event_id"] for row in rows}),
            "date_min": min(dates),
            "date_max": max(dates),
            "districts": len({row["district"] for row in rows}),
            "sha256": canonical_hash,
        },
        "correction_summary": {
            "removed_superseded_events": len(plans["remove"]),
            "new_reconstructed_events": len(plans["new"]),
            "merged_candidates": len(plans["merge"]),
            "excluded_reconstruction_candidates": len(plans["identity_excluded"]),
            "true_value_exclusions": len(plans["true_exclusions"]),
            "true_value_corrections": len(plans["true_corrections"]),
            "structured_attribute_corrections": len(plans["structured_corrections"]),
            "location_normalizations": len(location_log),
            "net_rows_from_source": len(rows) - len(read_csv(source_csv)),
        },
        "inputs": {
            str(source_csv.relative_to(root)): sha256(source_csv),
            str(source_manifest.relative_to(root)): sha256(source_manifest),
            str(database.relative_to(root)): sha256(database),
            str(ASSEMBLER_SCRIPT.relative_to(root)): sha256(ASSEMBLER_SCRIPT),
            **dict(sorted(input_hashes.items())),
        },
        "checks": {
            "expected_2872_rows": len(rows) == EXPECTED_ROWS,
            "unique_event_ids": len({row["event_id"] for row in rows}) == len(rows),
            "all_districts_canonical": all(row["district"] in set(all_districts()) for row in rows),
            "csv_sqlite_content_equal": True,
            "sqlite_integrity_ok": True,
            "all_manual_plan_actions_logged": len(application_log) == expected_log_rows,
            "fresh_locked_validation_complete": False,
        },
        "files": files,
        "bundle_lock_hash": hashlib.sha256(lock_payload.encode("utf-8")).hexdigest(),
        "notes": (
            "Versioned candidate assembled from v0.7 and validated post-correction plans. "
            "Earlier validation metrics do not validate this candidate."
        ),
    }
    (output_dir / "release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--output-dir")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else root / "data" / "releases" / args.release_id
    )
    release_dir = build_release(root, args.release_id, output_dir, force=args.force)
    print(f"Wrote post-correction candidate release to {release_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
