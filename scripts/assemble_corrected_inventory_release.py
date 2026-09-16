#!/usr/bin/env python3
"""Assemble the validated manual plans into a versioned candidate release.

The source v0.6.0 release remains immutable. This builder applies the identity,
true-value, and structured-attribute plans in that order, writes a standalone
CSV and SQLite snapshot, and labels the result as pending a fresh locked audit.
"""

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

DEFAULT_RELEASE_ID = "nepal_landslide_inventory_v0.7.0_candidate_20260916"
SOURCE_RELEASE_ID = "nepal_landslide_inventory_v0.6.0_v7_20260915"
EXPECTED_ROWS = 2904
PLAN_FILES = {
    "remove": "canonical_event_identity_plan_REMOVE_OLD_EVENTS.csv",
    "new": "canonical_event_identity_plan_NEW_EVENTS.csv",
    "merge": "canonical_event_identity_plan_MERGES.csv",
    "identity_excluded": "canonical_event_identity_plan_EXCLUDED_CANDIDATES.csv",
    "true_corrections": "canonical_event_true_value_plan_CORRECTIONS.csv",
    "true_exclusions": "canonical_event_true_value_plan_EXCLUSIONS.csv",
    "structured_corrections": "canonical_event_structured_attribute_plan_CORRECTIONS.csv",
    "structured_exclusions": "canonical_event_structured_attribute_plan_EXCLUSIONS.csv",
}
PLAN_MANIFESTS = (
    "canonical_event_identity_plan_manifest.json",
    "canonical_event_true_value_plan_manifest.json",
    "canonical_event_structured_attribute_plan_manifest.json",
)


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
    return "" if raw in ("", "not_reported") else raw


def verify_plan_provenance(root: Path, frozen_csv: Path) -> dict[str, str]:
    outputs = root / "data" / "outputs"
    observed: dict[str, str] = {}
    for name in PLAN_MANIFESTS:
        path = outputs / name
        manifest = json.loads(path.read_text(encoding="utf-8"))
        observed[str(path.relative_to(root))] = sha256(path)
        for output_name, expected in manifest.get("outputs", {}).items():
            output_path = outputs / output_name
            actual = sha256(output_path)
            if actual != expected:
                raise ValueError(f"Plan output checksum mismatch: {output_name}")
            observed[str(output_path.relative_to(root))] = actual
        frozen_entries = {
            key: value
            for key, value in manifest.get("inputs", {}).items()
            if key.endswith("canonical_events_final.csv")
        }
        if len(frozen_entries) != 1 or next(iter(frozen_entries.values())) != sha256(frozen_csv):
            raise ValueError(f"{name} is not pinned to the configured frozen inventory")
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
    metadata = {row["url"]: {key: str(row[key] or "") for key in row.keys()} for row in rows}
    missing = sorted(urls - set(metadata))
    if missing:
        raise ValueError(f"Article metadata missing for {len(missing)} planned URLs: {missing[:3]}")
    return metadata


def _append_manual_history(row: dict[str, str], entry: dict[str, Any]) -> None:
    payload = json.loads(row.get("event_payload") or "{}")
    payload.setdefault("manual_release_actions", []).append(entry)
    row["event_payload"] = compact_json(payload)


def _new_event_row(
    plan: dict[str, str],
    template: dict[str, str],
    articles: dict[str, dict[str, str]],
    province_by_district: dict[str, str],
    columns: list[str],
) -> dict[str, str]:
    candidate_id = plan["candidate_event_id"]
    suffix = candidate_id.removeprefix("candidate_")
    urls = parse_list(plan["article_urls_json"])
    if not urls:
        raise ValueError(f"New event {candidate_id} has no source articles")
    representative_url = urls[0]
    representative = articles[representative_url]
    sources = sorted({articles[url]["source"] for url in urls})
    municipality = plan["municipality"]
    payload = {
        "urls": sorted(urls),
        "sources": sources,
        "size": len(set(urls)),
        "representative_url": representative_url,
        "municipality_candidates": [municipality] if municipality else [],
        "ward_candidates": [],
        "place_name_candidates": [plan["district"]],
        "manual_reconstruction": {
            "candidate_event_id": candidate_id,
            "old_event_id": plan["old_event_id"],
            "article_mapping_ids": parse_list(plan["article_mapping_ids_json"]),
            "evidence": plan["evidence"],
            "reviewed_by": plan["reviewed_by"],
            "review_notes": plan["review_notes"],
        },
    }
    values = {column: "" for column in columns}
    values.update(
        {
            "event_id": f"event_{suffix}",
            "dedup_cluster_id": f"cluster_{suffix}",
            "event_date_ad": plan["event_date"],
            "district": plan["district"],
            "province": province_by_district.get(plan["district"], ""),
            "municipality": municipality,
            "event_type": plan["event_type"],
            "hazard_type": plan["hazard_type"],
            "event_granularity": "single",
            "article_role": "first_report",
            "extraction_basis": "manual_audit_reconstruction",
            "cluster_size": str(len(set(urls))),
            "sources_json": compact_json(sources),
            "representative_url": representative_url,
            "representative_source": representative["source"],
            "representative_title": representative["title"],
            "trigger": template.get("trigger") or "unknown",
            "deaths": release_value(plan["deaths"]),
            "specificity_reason": "manual_audit_reconstruction",
            "in_nepal": "1",
            "scope_reason": "manual_audit",
            "location_consistent": "1",
            "location_reason": "manual_audit",
            "municipality_candidates_json": compact_json([municipality] if municipality else []),
            "ward_candidates_json": "[]",
            "place_name_candidates_json": compact_json([plan["district"]]),
            "event_payload": compact_json(payload),
        }
    )
    return values


def assemble_rows(
    frozen_rows: list[dict[str, str]],
    plans: dict[str, list[dict[str, str]]],
    articles: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    if not frozen_rows:
        raise ValueError("Frozen inventory is empty")
    columns = list(frozen_rows[0])
    frozen_by_id = {row["event_id"]: deepcopy(row) for row in frozen_rows}
    if len(frozen_by_id) != len(frozen_rows):
        raise ValueError("Frozen inventory contains duplicate event IDs")
    province_by_district = {
        row["district"]: row["province"]
        for row in frozen_rows
        if row["district"] and row["province"]
    }

    remove_ids = {row["old_event_id"] for row in plans["remove"]}
    exclusion_ids = {row["event_id"] for row in plans["true_exclusions"]}
    correction_ids = {
        row["event_id"]
        for key in ("true_corrections", "structured_corrections")
        for row in plans[key]
    }
    if remove_ids & exclusion_ids or remove_ids & correction_ids or exclusion_ids & correction_ids:
        raise ValueError("Manual plan layers overlap")
    missing = (remove_ids | exclusion_ids | correction_ids) - set(frozen_by_id)
    if missing:
        raise ValueError(
            f"Plan targets are absent from the frozen inventory: {sorted(missing)[:3]}"
        )

    rows = {event_id: row for event_id, row in frozen_by_id.items() if event_id not in remove_ids}
    log: list[dict[str, str]] = []
    provenance: list[dict[str, str]] = []
    for plan in plans["remove"]:
        log.append(_log_row("remove_superseded", plan["old_event_id"], "", "identity", plan))

    for plan in plans["merge"]:
        target_id = plan["merge_target_event_id"]
        if target_id not in rows:
            raise ValueError(f"Merge target is absent after removals: {target_id}")
        target = rows[target_id]
        payload = json.loads(target.get("event_payload") or "{}")
        merged_urls = parse_list(plan["article_urls_json"])
        urls = sorted(set(payload.get("urls", [])) | set(merged_urls))
        sources = sorted(
            set(payload.get("sources", []))
            | {articles[url]["source"] for url in merged_urls}
        )
        payload["urls"] = urls
        payload["sources"] = sources
        payload["size"] = len(urls)
        payload.setdefault("manual_identity_merges", []).append(
            {
                "candidate_event_id": plan["candidate_event_id"],
                "old_event_id": plan["old_event_id"],
                "evidence": plan["evidence"],
                "reviewed_by": plan["reviewed_by"],
            }
        )
        target["event_payload"] = compact_json(payload)
        target["cluster_size"] = str(len(urls))
        target["sources_json"] = compact_json(sources)
        log.append(
            _log_row("merge_into_existing", target_id, plan["candidate_event_id"], "identity", plan)
        )
        provenance.extend(_provenance_rows(target_id, plan, articles, "merge_into_existing"))

    new_ids: set[str] = set()
    for plan in plans["new"]:
        template = frozen_by_id[plan["old_event_id"]]
        new_row = _new_event_row(plan, template, articles, province_by_district, columns)
        event_id = new_row["event_id"]
        if event_id in rows or event_id in new_ids:
            raise ValueError(f"Generated event ID collision: {event_id}")
        rows[event_id] = new_row
        new_ids.add(event_id)
        log.append(
            _log_row("add_reconstructed", event_id, plan["candidate_event_id"], "identity", plan)
        )
        provenance.extend(_provenance_rows(event_id, plan, articles, "add_reconstructed"))

    for plan in plans["true_exclusions"]:
        rows.pop(plan["event_id"])
        log.append(
            _log_row(
                "exclude_existing", plan["event_id"], plan["candidate_id"], "true_value", plan
            )
        )

    for plan in plans["true_corrections"]:
        row = rows[plan["event_id"]]
        final_values = {
            "event_date_ad": plan["final_event_date"],
            "district": plan["final_district"],
            "municipality": plan["final_municipality"],
            "event_type": plan["final_event_type"],
            "hazard_type": plan["final_hazard_type"],
            "deaths": release_value(plan["final_deaths"]),
            "province": plan["final_province"],
        }
        row.update(final_values)
        fields = parse_list(plan["changed_fields_json"])
        _append_manual_history(row, _history_entry("true_value", plan, fields))
        log.append(
            _log_row(
                "correct_attributes",
                plan["event_id"],
                plan["candidate_id"],
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
                plan["candidate_id"],
                "structured_attribute",
                plan,
                fields,
            )
        )

    assembled = sorted(
        rows.values(), key=lambda row: (row["event_date_ad"], row["district"], row["event_id"])
    )
    if len(assembled) != EXPECTED_ROWS:
        raise ValueError(f"Expected {EXPECTED_ROWS} rows after all plans, got {len(assembled)}")
    if len({row["event_id"] for row in assembled}) != len(assembled):
        raise ValueError("Corrected inventory contains duplicate event IDs")
    return assembled, log, provenance


def _history_entry(layer: str, plan: dict[str, str], fields: list[str]) -> dict[str, Any]:
    return {
        "layer": layer,
        "candidate_id": plan["candidate_id"],
        "changed_fields": fields,
        "reviewed_by": plan["reviewed_by"],
        "review_notes": plan["review_notes"],
    }


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
        "reviewed_by": plan.get("reviewed_by", ""),
        "review_notes": plan.get("review_notes") or plan.get("reason", ""),
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


def write_snapshot(path: Path, rows: list[dict[str, str]], release_id: str, csv_hash: str) -> None:
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
            "CREATE TABLE release_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO release_metadata VALUES (?, ?)",
            (
                ("release_id", release_id),
                ("status", "pending_post_correction_validation"),
                ("supersedes", SOURCE_RELEASE_ID),
                ("canonical_csv_sha256", csv_hash),
                ("canonical_rows", str(len(rows))),
            ),
        )


def build_release(root: Path, release_id: str, output_dir: Path, *, force: bool = False) -> Path:
    source_dir = root / "data" / "releases" / SOURCE_RELEASE_ID
    frozen_csv = source_dir / "canonical_events_final.csv"
    outputs = root / "data" / "outputs"
    database = root / "data" / "raw_sqlite" / "landslide_inventory.sqlite"
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(f"Release directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    input_hashes = verify_plan_provenance(root, frozen_csv)
    plans = {key: read_csv(outputs / name) for key, name in PLAN_FILES.items()}
    planned_urls = {
        url
        for key in ("new", "merge")
        for row in plans[key]
        for url in parse_list(row["article_urls_json"])
    }
    articles = load_article_metadata(database, planned_urls)
    rows, application_log, provenance = assemble_rows(read_csv(frozen_csv), plans, articles)

    canonical_path = output_dir / "canonical_events_final.csv"
    write_csv(canonical_path, rows, list(rows[0]))
    canonical_hash = sha256(canonical_path)
    log_path = output_dir / "correction_application_log.csv"
    write_csv(log_path, application_log, list(application_log[0]))
    provenance_path = output_dir / "corrected_event_article_provenance.csv"
    write_csv(provenance_path, provenance, list(provenance[0]))
    snapshot_path = output_dir / "canonical_inventory.sqlite"
    if snapshot_path.exists():
        snapshot_path.unlink()
    write_snapshot(snapshot_path, rows, release_id, canonical_hash)

    report_path = output_dir / "CORRECTED_RELEASE_README.md"
    report_path.write_text(
        "\n".join(
            [
                "# Corrected inventory candidate release",
                "",
                f"Release: `{release_id}`",
                f"Rows: {len(rows):,}",
                f"Supersedes: `{SOURCE_RELEASE_ID}`",
                "Status: pending post-correction validation.",
                "",
                "This candidate applies every validated manual correction plan.",
                "It must not inherit the frozen v7 accuracy metrics. Run a fresh",
                "locked audit before promoting this bundle to a final paper release.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    files = []
    for path in (canonical_path, snapshot_path, log_path, provenance_path, report_path):
        files.append({"file": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    lock_payload = compact_json(
        ["release_bundle", release_id, [[item["file"], item["sha256"]] for item in files]]
    )
    dates = [row["event_date_ad"] for row in rows if row["event_date_ad"]]
    manifest = {
        "release_id": release_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_post_correction_validation",
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
            "true_value_exclusions": len(plans["true_exclusions"]),
            "true_value_corrections": len(plans["true_corrections"]),
            "structured_attribute_corrections": len(plans["structured_corrections"]),
            "net_rows_from_frozen": len(rows) - len(read_csv(frozen_csv)),
        },
        "inputs": {
            str(frozen_csv.relative_to(root)): sha256(frozen_csv),
            str(database.relative_to(root)): sha256(database),
            **dict(sorted(input_hashes.items())),
        },
        "checks": {
            "expected_2904_rows": len(rows) == EXPECTED_ROWS,
            "unique_event_ids": len({row["event_id"] for row in rows}) == len(rows),
            "all_manual_plans_applied": len(application_log) == 55 + 85 + 12 + 11 + 26 + 27,
            "fresh_locked_validation_complete": False,
        },
        "files": files,
        "bundle_lock_hash": hashlib.sha256(lock_payload.encode("utf-8")).hexdigest(),
        "notes": (
            "Versioned candidate release assembled from the frozen v0.6.0 inventory and "
            "validated manual plans. Frozen v7 metrics do not validate this corrected release."
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
    print(f"Wrote corrected candidate release to {release_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
