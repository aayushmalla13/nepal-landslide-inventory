#!/usr/bin/env python3
"""Build prioritized review packs for current same-identity dedup collisions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable

from rapidfuzz import fuzz

from landslide_inventory.unify.similarity import TfidfIndex, normalize_for_matching, transliterate_devanagari


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "raw_sqlite" / "landslide_inventory.sqlite"
OUTPUT = ROOT / "data" / "outputs"


@dataclass(frozen=True)
class ArticleEvidence:
    url: str
    source: str
    title: str
    body: str
    route_lang: str
    ward: str
    place: str
    deaths: int | None
    missing: int | None
    injured: int | None


@dataclass(frozen=True)
class ClusterEvidence:
    event_id: str
    cluster_id: str
    district: str
    event_date: str
    municipality: str
    event_type: str
    hazard_type: str
    representative_url: str
    articles: tuple[ArticleEvidence, ...]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def json_list(values: Iterable[object]) -> str:
    return json.dumps(sorted({value for value in values if value not in (None, "")}), ensure_ascii=False)


def load_collision_clusters(database: Path) -> list[ClusterEvidence]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    canonical_rows = connection.execute(
        """
        WITH identities AS (
            SELECT district, event_date_ad, COALESCE(municipality, '') AS municipality
            FROM canonical_events
            GROUP BY district, event_date_ad, COALESCE(municipality, '')
            HAVING COUNT(*) > 1
        )
        SELECT c.*
        FROM canonical_events c
        JOIN identities i
          ON i.district = c.district
         AND i.event_date_ad = c.event_date_ad
         AND i.municipality = COALESCE(c.municipality, '')
        ORDER BY c.district, c.event_date_ad, COALESCE(c.municipality, ''), c.event_id
        """
    ).fetchall()

    clusters: list[ClusterEvidence] = []
    for row in canonical_rows:
        payload = json.loads(row["event_payload"])
        urls = [str(value) for value in payload.get("urls", [])]
        if not urls and payload.get("representative_url"):
            urls = [str(payload["representative_url"])]
        placeholders = ",".join("?" for _ in urls)
        article_rows = connection.execute(
            f"""
            SELECT e.url, e.source, COALESCE(e.title, '') AS title,
                   COALESCE(r.text, '') AS body, COALESCE(e.route_lang, '') AS route_lang,
                   COALESCE(e.ward, '') AS ward, COALESCE(e.place_name_raw, '') AS place,
                   e.deaths, e.missing, e.injured
            FROM article_events e
            LEFT JOIN raw_articles r ON r.url = e.url
            WHERE e.url IN ({placeholders})
            ORDER BY e.url
            """,
            urls,
        ).fetchall() if urls else []
        articles = tuple(
            ArticleEvidence(
                url=str(item["url"]), source=str(item["source"] or ""),
                title=str(item["title"]), body=str(item["body"]),
                route_lang=str(item["route_lang"]), ward=str(item["ward"]),
                place=str(item["place"]), deaths=item["deaths"],
                missing=item["missing"], injured=item["injured"],
            )
            for item in article_rows
        )
        clusters.append(ClusterEvidence(
            event_id=str(row["event_id"]), cluster_id=str(row["dedup_cluster_id"]),
            district=str(row["district"]), event_date=str(row["event_date_ad"]),
            municipality=str(row["municipality"] or ""),
            event_type=str(row["event_type"] or ""),
            hazard_type=str(row["hazard_type"] or ""),
            representative_url=str(payload.get("representative_url") or ""),
            articles=articles,
        ))
    connection.close()
    return clusters


def best_title_similarity(left: ClusterEvidence, right: ClusterEvidence) -> float:
    return max(
        (fuzz.token_set_ratio(a.title, b.title) / 100.0 for a in left.articles for b in right.articles),
        default=0.0,
    )


def best_text_similarity(left: ClusterEvidence, right: ClusterEvidence, tfidf: TfidfIndex) -> float:
    return max(
        (tfidf.cosine(a.body, b.body) for a in left.articles for b in right.articles),
        default=0.0,
    )


def comparable_values(cluster: ClusterEvidence, field: str) -> set[int]:
    return {int(value) for value in (getattr(article, field) for article in cluster.articles) if value is not None}


def casualty_state(left: ClusterEvidence, right: ClusterEvidence) -> tuple[str, list[str]]:
    agreements: list[str] = []
    conflicts: list[str] = []
    for field in ("deaths", "missing", "injured"):
        left_values = comparable_values(left, field)
        right_values = comparable_values(right, field)
        if not left_values or not right_values:
            continue
        if min(abs(a - b) for a in left_values for b in right_values) <= 1:
            agreements.append(field)
        else:
            conflicts.append(field)
    if conflicts:
        return "conflict", conflicts
    if agreements:
        return "agreement", agreements
    return "unavailable", []


def normalized_place(value: str) -> str:
    return transliterate_devanagari(value) or normalize_for_matching(value)


def best_place_similarity(left: ClusterEvidence, right: ClusterEvidence) -> float:
    left_places = [normalized_place(article.place) for article in left.articles if article.place]
    right_places = [normalized_place(article.place) for article in right.articles if article.place]
    return max(
        (fuzz.token_sort_ratio(a, b) / 100.0 for a in left_places for b in right_places),
        default=0.0,
    )


def cluster_summary(cluster: ClusterEvidence) -> dict[str, object]:
    representative = next(
        (article for article in cluster.articles if article.url == cluster.representative_url),
        cluster.articles[0] if cluster.articles else None,
    )
    return {
        "event_id": cluster.event_id,
        "cluster_id": cluster.cluster_id,
        "article_count": len(cluster.articles),
        "representative_title": representative.title if representative else "",
        "representative_url": representative.url if representative else cluster.representative_url,
        "sources_json": json_list(article.source for article in cluster.articles),
        "languages_json": json_list(article.route_lang for article in cluster.articles),
        "wards_json": json_list(article.ward for article in cluster.articles),
        "places_json": json_list(article.place for article in cluster.articles),
        "deaths_json": json_list(comparable_values(cluster, "deaths")),
        "missing_json": json_list(comparable_values(cluster, "missing")),
        "injured_json": json_list(comparable_values(cluster, "injured")),
        "urls_json": json_list(article.url for article in cluster.articles),
    }


def score_pair(left: ClusterEvidence, right: ClusterEvidence, tfidf: TfidfIndex) -> dict[str, object]:
    title_similarity = best_title_similarity(left, right)
    text_similarity = best_text_similarity(left, right, tfidf)
    place_similarity = best_place_similarity(left, right)
    casualty, casualty_fields = casualty_state(left, right)
    left_wards = {article.ward for article in left.articles if article.ward}
    right_wards = {article.ward for article in right.articles if article.ward}
    ward_overlap = sorted(left_wards & right_wards)
    ward_conflict = bool(left_wards and right_wards and not ward_overlap)

    score = 0
    signals: list[str] = []
    conflicts: list[str] = []
    if casualty == "agreement":
        score += 30
        signals.append("casualty_agreement")
    elif casualty == "conflict":
        score -= 35
        conflicts.append("casualty_conflict:" + ",".join(casualty_fields))
    if ward_overlap:
        score += 25
        signals.append("ward_overlap")
    elif ward_conflict:
        score -= 30
        conflicts.append("ward_conflict")
    if place_similarity >= 0.90:
        score += 25
        signals.append("place_similarity_high")
    elif place_similarity >= 0.75:
        score += 15
        signals.append("place_similarity_medium")
    elif place_similarity and place_similarity < 0.40:
        score -= 20
        conflicts.append("place_similarity_low")
    if text_similarity >= 0.65:
        score += 20
        signals.append("text_similarity_high")
    elif text_similarity >= 0.45:
        score += 12
        signals.append("text_similarity_medium")
    elif text_similarity >= 0.30:
        score += 5
        signals.append("text_similarity_weak")
    if title_similarity >= 0.85:
        score += 20
        signals.append("title_similarity_high")
    elif title_similarity >= 0.70:
        score += 12
        signals.append("title_similarity_medium")
    elif title_similarity >= 0.55:
        score += 5
        signals.append("title_similarity_weak")

    strong_signals = sum(name in signals for name in (
        "casualty_agreement", "ward_overlap", "place_similarity_high",
        "text_similarity_high", "title_similarity_high",
    ))
    if conflicts:
        priority = "P3_conflict_or_likely_distinct"
        recommendation = "review_likely_distinct"
    elif score >= 55 and strong_signals >= 2:
        priority = "P1_likely_merge"
        recommendation = "review_likely_merge"
    elif score >= 30:
        priority = "P2_possible_merge"
        recommendation = "review_possible_merge"
    else:
        priority = "P3_weak_evidence"
        recommendation = "review_likely_distinct"
    return {
        "priority": priority,
        "recommendation": recommendation,
        "evidence_score": score,
        "title_similarity": round(title_similarity, 4),
        "text_tfidf_similarity": round(text_similarity, 4),
        "place_similarity": round(place_similarity, 4),
        "casualty_state": casualty,
        "ward_overlap_json": json.dumps(ward_overlap, ensure_ascii=False),
        "signals": ";".join(signals),
        "conflicts": ";".join(conflicts),
    }


def evidence_text(cluster: ClusterEvidence) -> str:
    parts: list[str] = []
    for index, article in enumerate(cluster.articles, start=1):
        parts.append(
            f"ARTICLE {index}\nURL: {article.url}\nSOURCE: {article.source}\n"
            f"TITLE: {article.title}\nWARD: {article.ward}\nPLACE: {article.place}\n"
            f"CASUALTIES: deaths={article.deaths}, missing={article.missing}, injured={article.injured}\n"
            f"TEXT:\n{article.body}"
        )
    return "\n\n---\n\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--batch-number", type=int, default=1)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_number < 1:
        raise ValueError("batch size and number must be positive")

    clusters = load_collision_clusters(args.database)
    grouped: dict[tuple[str, str, str], list[ClusterEvidence]] = {}
    for cluster in clusters:
        grouped.setdefault((cluster.district, cluster.event_date, cluster.municipality), []).append(cluster)
    tfidf = TfidfIndex(article.body for cluster in clusters for article in cluster.articles)

    rows: list[dict[str, object]] = []
    pair_clusters: dict[str, tuple[ClusterEvidence, ClusterEvidence]] = {}
    for identity, identity_clusters in sorted(grouped.items()):
        group_id = stable_id("collision_group", *identity)
        for left, right in combinations(sorted(identity_clusters, key=lambda item: item.event_id), 2):
            pair_id = stable_id("collision_pair", left.event_id, right.event_id)
            left_summary = cluster_summary(left)
            right_summary = cluster_summary(right)
            row = {
                "pair_id": pair_id,
                "group_id": group_id,
                "district": identity[0],
                "event_date": identity[1],
                "municipality": identity[2],
                "group_cluster_count": len(identity_clusters),
                **score_pair(left, right, tfidf),
                **{f"left_{key}": value for key, value in left_summary.items()},
                **{f"right_{key}": value for key, value in right_summary.items()},
                "decision": "",
                "merge_survivor_event_id": "",
                "reviewed_by": "",
                "review_notes": "",
            }
            rows.append(row)
            pair_clusters[pair_id] = (left, right)

    priority_order = {"P1_likely_merge": 0, "P2_possible_merge": 1,
                      "P3_conflict_or_likely_distinct": 2, "P3_weak_evidence": 3}
    rows.sort(key=lambda row: (
        priority_order[str(row["priority"])], -int(row["evidence_score"]),
        str(row["district"]), str(row["event_date"]), str(row["pair_id"]),
    ))
    for index, row in enumerate(rows, start=1):
        row["review_rank"] = index

    start = (args.batch_number - 1) * args.batch_size
    batch = rows[start:start + args.batch_size]
    batch_tag = f"BATCH_{args.batch_number:02d}"
    all_path = OUTPUT / "dedup_collision_review_ALL.csv"
    batch_path = OUTPUT / f"dedup_collision_review_{batch_tag}_LABEL_HERE.csv"
    reading_path = OUTPUT / f"dedup_collision_review_{batch_tag}_READING_PACK.csv"
    manifest_path = OUTPUT / "dedup_collision_review_manifest.json"
    report_path = OUTPUT / "dedup_collision_review_report.md"
    columns = list(rows[0]) if rows else ["pair_id"]
    write_csv(all_path, rows, columns)
    write_csv(batch_path, batch, columns)
    reading_rows = []
    for row in batch:
        left, right = pair_clusters[str(row["pair_id"])]
        reading_rows.append({
            "pair_id": row["pair_id"], "group_id": row["group_id"],
            "priority": row["priority"], "recommendation": row["recommendation"],
            "district": row["district"], "event_date": row["event_date"],
            "municipality": row["municipality"],
            "left_event_id": left.event_id, "right_event_id": right.event_id,
            "left_article_evidence": evidence_text(left),
            "right_article_evidence": evidence_text(right),
        })
    reading_columns = list(reading_rows[0]) if reading_rows else ["pair_id"]
    write_csv(reading_path, reading_rows, reading_columns)

    counts: dict[str, int] = {}
    for row in rows:
        key = str(row["priority"])
        counts[key] = counts.get(key, 0) + 1
    manifest = {
        "database": str(args.database.relative_to(ROOT) if args.database.is_relative_to(ROOT) else args.database),
        "database_sha256": sha256(args.database),
        "collision_groups": len(grouped), "collision_clusters": len(clusters),
        "pair_rows": len(rows), "priority_counts": counts,
        "batch_number": args.batch_number, "batch_size": args.batch_size,
        "batch_rows": len(batch),
        "outputs": {
            all_path.name: sha256(all_path), batch_path.name: sha256(batch_path),
            reading_path.name: sha256(reading_path),
        },
        "status": "review_pack_only_no_merges_applied",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join([
            "# Current dedup collision review", "",
            f"Collision groups: {len(grouped)}", f"Clusters in groups: {len(clusters)}",
            f"Pair rows: {len(rows)}", *(f"{key}: {value}" for key, value in sorted(counts.items())),
            "", f"Current review batch: {args.batch_number} ({len(batch)} rows)",
            "", "No merge has been applied automatically.", "",
        ]), encoding="utf-8",
    )
    print(f"Wrote {len(rows)} pairs to {all_path}")
    print(f"Wrote {len(batch)} review rows to {batch_path}")
    print(f"Wrote {len(reading_rows)} reading rows to {reading_path}")
    print(f"Wrote {manifest_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
