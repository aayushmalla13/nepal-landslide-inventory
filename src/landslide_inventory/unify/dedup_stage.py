"""Safe dedup clustering for typed, single, in-scope article events."""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from ..config import AppConfig
from ..db import connect_sqlite, initialize_sqlite
from ..gazetteer import district_to_province
from ..utils import ensure_directory, stable_hash, utc_now_iso
from .event_typing import ROLE_FIRST_REPORT, classify_event_type
from .reviewed_corrections import apply_reviewed_corrections
from .reviewed_dedup_merges import (
    apply_reviewed_merges,
    load_reviewed_merges,
    merge_overrides_path,
)
from .similarity import (
    CasualtyVector,
    SimilarityBreakdown,
    TfidfIndex,
    merge_rate_by_language_pair,
    structured_similarity,
)

LOGGER = logging.getLogger(__name__)

# Multi-event extraction (docs/MULTIEVENT_EXTRACTION.md).
EXTRACTION_PRIMARY = 'primary'
EXTRACTION_SECONDARY = 'secondary_failure'

# Date bases firm enough for a recovered record to found a canonical event on
# its own. Mirrors multievent.FIRM_DATE_BASES; duplicated rather than imported
# so dedup does not depend on the extractor module, and pinned by a test that
# fails if the two drift apart.
FIRM_DATE_BASES = frozenset({'explicit_bs_date', 'explicit_ad_date'})


@dataclass(frozen=True)
class DedupConfig:
    """Thresholds controlling safe event clustering."""

    candidate_window_days: int
    primary_window_days: int
    max_cluster_span_days: int
    headline_sim_threshold: float
    body_sim_threshold: float
    high_body_sim_threshold: float
    guard_deaths_delta: int
    prefer_same_municipality: bool


@dataclass(frozen=True)
class EventRecord:
    """One typed, in-scope article event eligible for dedup."""

    url: str
    source: str
    title: str | None
    body_text: str
    event_date_ad: str
    district: str
    province: str | None
    municipality: str | None
    ward: str | None
    place_name_raw: str | None
    deaths: int | None
    # Added for cross-language dedup: all language-neutral, all previously
    # available in article_events but never read here (review section 8.2).
    missing: int | None
    injured: int | None
    trigger: str | None
    route_lang: str | None
    event_class: int
    in_nepal: int
    conf_class: float
    conf_date: float
    conf_district: float
    conf_place: float
    conf_fatalities: float
    conf_trigger: float
    event_type: str = 'landslide'
    hazard_type: str = 'landslide'
    event_granularity: str = 'single'
    article_role: str = ROLE_FIRST_REPORT
    # Multi-event extraction. One article may now yield several records, one
    # per district-day it supports. 'primary' is the article-level record the
    # pipeline has always produced; 'secondary_failure' is one recovered from a
    # further sentence, carrying that sentence as its evidence.
    extraction_basis: str = EXTRACTION_PRIMARY
    evidence_sentence: str | None = None
    date_basis: str | None = None

    @property
    def event_date(self) -> date:
        """Return the parsed event date."""

        return date.fromisoformat(self.event_date_ad)

    @property
    def record_key(self) -> str:
        """Return the identity of this *record*, which is no longer its URL.

        Dedup keyed union-find on ``url``, which was sound while each article
        produced exactly one event. Once an article can yield several
        district-days, a URL key silently collapses them into one node and
        every recovered district-day disappears into whichever cluster the
        article's primary record joined.
        """

        return f'{self.url}#{self.district}@{self.event_date_ad}'

    @property
    def is_secondary(self) -> bool:
        """Whether this record was recovered from a further sentence."""

        return self.extraction_basis != EXTRACTION_PRIMARY

    @property
    def confidence_score(self) -> float:
        """Return a deterministic aggregate confidence score."""

        return (
            self.conf_class
            + self.conf_date
            + self.conf_district
            + self.conf_place
            + self.conf_fatalities
            + self.conf_trigger
        )


@dataclass(frozen=True)
class PairSimilarity:
    """Similarity metrics for one candidate pair."""

    headline_sim: float
    body_sim: float
    day_diff: int


def build_dedup_config(config: AppConfig) -> DedupConfig:
    """Read dedup thresholds from config."""

    values = dict(config.raw['dedup'])
    return DedupConfig(
        candidate_window_days=int(values['candidate_window_days']),
        primary_window_days=int(values['primary_window_days']),
        max_cluster_span_days=int(values.get('max_cluster_span_days', 1)),
        headline_sim_threshold=float(values['headline_sim_threshold']),
        body_sim_threshold=float(values['body_sim_threshold']),
        high_body_sim_threshold=float(values['high_body_sim_threshold']),
        guard_deaths_delta=int(values['guard_deaths_delta']),
        prefer_same_municipality=bool(values.get('prefer_same_municipality', True)),
    )


def run_dedup_stage(config: AppConfig) -> int:
    """Cluster typed, single, in-scope article events into canonical events."""

    initialize_sqlite(config.sqlite_path)
    apply_reviewed_corrections(config)
    dedup_config = build_dedup_config(config)
    events = load_dedup_events(config.sqlite_path)
    # IDF is computed over the eligible corpus so monsoon boilerplate ("rescue
    # teams", "police said", "district") is down-weighted rather than treated
    # as evidence of a match.
    tfidf = TfidfIndex(event.body_text for event in events)
    clusters, merge_rates = cluster_events(events, dedup_config, tfidf)
    override_path = merge_overrides_path(config)
    overrides = load_reviewed_merges(override_path) if override_path else []
    clusters, preferred_ids, reviewed_merge_count = apply_reviewed_merges(
        clusters, overrides
    )
    cluster_ids, identity_collisions = assign_cluster_ids(clusters, preferred_ids)
    persisted_at = utc_now_iso()

    for pair, counts in merge_rates.items():
        rate = counts['merged'] / counts['candidates'] if counts['candidates'] else 0.0
        LOGGER.info(
            'dedup merge rate %-7s %4d/%-6d (%.1f%%)',
            pair, counts['merged'], counts['candidates'], 100.0 * rate,
        )
    cross = merge_rates.get('en-np', {})
    if cross.get('candidates') and cross.get('merged', 0) == 0:
        # Review section 8.2: "If en-np merges stay near zero after the fix, the
        # fix did not work." Surfaced automatically rather than left to memory.
        LOGGER.warning(
            'No en-np merges across %d cross-language candidate pairs -- '
            'cross-language dedup is not working.', cross['candidates'],
        )

    if identity_collisions:
        # Identity collisions are review candidates, not automatic duplicates:
        # several physical failures can occur in one municipality on one day.
        LOGGER.warning(
            '%d clusters share a (district, date, municipality) identity with '
            'another cluster -- unresolved collision candidates; ids disambiguated with a suffix',
            identity_collisions,
        )
    if reviewed_merge_count:
        LOGGER.info(
            'Applied %d reviewed dedup merge components from %s',
            reviewed_merge_count,
            override_path,
        )

    with connect_sqlite(config.sqlite_path) as connection:
        reset_dedup_outputs(connection)
        for index, cluster in enumerate(clusters):
            summary = build_cluster_summary(cluster, persisted_at, cluster_ids[index])
            connection.execute(
                """
                INSERT INTO cluster_summary (
                    cluster_id, district, date_min, date_max, size,
                    record_count, secondary_record_count, sources, urls, inserted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary['cluster_id'],
                    summary['district'],
                    summary['date_min'],
                    summary['date_max'],
                    summary['size'],
                    summary['record_count'],
                    summary['secondary_record_count'],
                    summary['sources'],
                    summary['urls'],
                    summary['inserted_at'],
                ),
            )
            canonical = build_canonical_event(cluster, persisted_at, cluster_ids[index])
            connection.execute(
                """
                INSERT INTO canonical_events (
                    event_id, dedup_cluster_id, event_date_ad, district, province,
                    municipality, municipality_candidates_json, ward_candidates_json,
                    place_name_candidates_json, event_payload, inserted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    dedup_cluster_id = excluded.dedup_cluster_id,
                    event_date_ad = excluded.event_date_ad,
                    district = excluded.district,
                    province = excluded.province,
                    municipality = excluded.municipality,
                    municipality_candidates_json = excluded.municipality_candidates_json,
                    ward_candidates_json = excluded.ward_candidates_json,
                    place_name_candidates_json = excluded.place_name_candidates_json,
                    event_payload = excluded.event_payload,
                    inserted_at = excluded.inserted_at
                """,
                (
                    canonical['event_id'],
                    canonical['dedup_cluster_id'],
                    canonical['event_date_ad'],
                    canonical['district'],
                    canonical['province'],
                    canonical['municipality'],
                    canonical['municipality_candidates_json'],
                    canonical['ward_candidates_json'],
                    canonical['place_name_candidates_json'],
                    canonical['event_payload'],
                    canonical['inserted_at'],
                ),
            )
            for event in cluster:
                connection.execute(
                    'UPDATE article_events SET dedup_cluster_id = ? WHERE url = ?',
                    (summary['cluster_id'], event.url),
                )
        connection.commit()

    export_cluster_summary_csv(
        config.resolve_path('outputs_dir') / 'cluster_summary.csv',
        clusters, persisted_at, cluster_ids,
    )
    export_canonical_events_csv(
        config.resolve_path('outputs_dir') / 'canonical_events.csv',
        clusters, persisted_at, cluster_ids,
    )
    return len(clusters)


def load_dedup_events(database_path: Path) -> list[EventRecord]:
    """Load headline-eligible single Nepal events for dedup.

    ``class`` is an extraction-confidence bucket, not an event ontology. Class
    2 contains many real road-obstruction reports and concrete follow-ups, so
    eligibility is decided by canonical hazard/granularity/role typing instead.
    """

    with connect_sqlite(database_path) as connection:
        rows = connection.execute(
            """
            SELECT e.url, e.source, e.title, COALESCE(r.text, '') AS body_text,
                   e.event_date_ad, e.district, e.province, e.municipality,
                   e.ward, e.place_name_raw, e.deaths, e.missing, e.injured,
                   e.trigger, e.route_lang, e.class, e.in_nepal,
                   COALESCE(e.conf_class, 0.0) AS conf_class,
                   COALESCE(e.conf_date, 0.0) AS conf_date,
                   COALESCE(e.conf_district, 0.0) AS conf_district,
                   COALESCE(e.conf_place, 0.0) AS conf_place,
                   COALESCE(e.conf_fatalities, 0.0) AS conf_fatalities,
                   COALESCE(e.conf_trigger, 0.0) AS conf_trigger
            FROM article_events e
            LEFT JOIN raw_articles r ON r.url = e.url
            LEFT JOIN reviewed_article_corrections correction ON correction.url = e.url
            WHERE e.class IN (1, 2)
              AND COALESCE(e.specificity_ok, 0) = 1
              AND COALESCE(e.in_nepal, 0) = 1
              AND COALESCE(correction.exclude_from_canonical, 0) = 0
              AND e.event_date_ad IS NOT NULL
              AND e.district IS NOT NULL
            ORDER BY e.district ASC, e.event_date_ad ASC, COALESCE(e.municipality, '') ASC, e.url ASC
            """
        ).fetchall()

    events: list[EventRecord] = []
    for row in rows:
        typing = classify_event_type(
            row['title'], row['body_text'], row['deaths'], row['missing'], row['injured']
        )
        if not typing.in_headline_counts:
            continue
        events.append(EventRecord(
            url=str(row['url']),
            source=str(row['source']),
            title=row['title'],
            body_text=str(row['body_text'] or ''),
            event_date_ad=str(row['event_date_ad']),
            district=str(row['district']),
            province=row['province'],
            municipality=row['municipality'],
            ward=row['ward'],
            place_name_raw=row['place_name_raw'],
            deaths=int(row['deaths']) if row['deaths'] is not None else None,
            missing=int(row['missing']) if row['missing'] is not None else None,
            injured=int(row['injured']) if row['injured'] is not None else None,
            trigger=row['trigger'],
            route_lang=row['route_lang'],
            event_class=int(row['class']),
            in_nepal=int(row['in_nepal']),
            conf_class=float(row['conf_class']),
            conf_date=float(row['conf_date']),
            conf_district=float(row['conf_district']),
            conf_place=float(row['conf_place']),
            conf_fatalities=float(row['conf_fatalities']),
            conf_trigger=float(row['conf_trigger']),
            event_type=typing.event_type,
            hazard_type=typing.hazard_type,
            event_granularity=typing.event_granularity,
            article_role=typing.article_role,
        ))
    return events


def structured_pair_similarity(left: EventRecord, right: EventRecord, tfidf: TfidfIndex | None):
    """Language-neutral score for one candidate pair. See unify/similarity.py."""

    return structured_similarity(
        left_municipality=left.municipality, right_municipality=right.municipality,
        left_ward=left.ward, right_ward=right.ward,
        left_casualties=CasualtyVector(left.deaths, left.missing, left.injured),
        right_casualties=CasualtyVector(right.deaths, right.missing, right.injured),
        left_trigger=left.trigger, right_trigger=right.trigger,
        left_place=left.place_name_raw, right_place=right.place_name_raw,
        left_text=left.body_text, right_text=right.body_text,
        left_lang=left.route_lang, right_lang=right.route_lang,
        tfidf=tfidf,
    )


def cluster_events(
    events: list[EventRecord],
    config: DedupConfig,
    tfidf: TfidfIndex | None = None,
) -> tuple[list[list[EventRecord]], dict[str, dict[str, int]]]:
    """Cluster candidate events using deterministic union-find.

    Two merge paths, unioned:

    1. The original string-similarity path (rapidfuzz over title/body). Kept
       as-is because its thresholds are tuned, even if tuned on the test set,
       and changing them would confound this fix with a retuning.

    2. The structured, language-neutral path added for review section 8.2.
       Devanagari and Latin share no tokens, so path 1 scores every
       cross-language pair at ~0 and they can never merge -- 1,031 of 1,112
       clusters were singletons. Path 2 compares gazetteer-normalised
       municipality, casualty vectors and transliterated place names instead,
       none of which depend on script.

    Fully replacing path 1 with TF-IDF cosine (review section 8.2) is deferred:
    it needs weights fitted on a dev set, and the locked test set is unlabelled.

    Also returns merge counts by language pair, which is the acceptance test:
    if en-np merges stay near zero, the fix did not work.
    """

    if not events:
        return [], {}

    parents = {event.record_key: event.record_key for event in events}
    date_spans = {
        event.record_key: (event.event_date, event.event_date)
        for event in events
    }
    grouped_by_district: dict[str, list[EventRecord]] = {}
    for event in events:
        grouped_by_district.setdefault(event.district, []).append(event)

    observed: list[tuple[str, str, bool]] = []
    for district in sorted(grouped_by_district):
        district_events = sorted(grouped_by_district[district], key=event_sort_key)
        for index, left in enumerate(district_events):
            for right in district_events[index + 1 :]:
                day_diff = abs((right.event_date - left.event_date).days)
                if day_diff > config.candidate_window_days:
                    break
                # An article cannot corroborate itself. Two records from one
                # URL are, by construction, two *distinct occasions* the
                # extractor separated; merging them back would both undo that
                # separation and inflate the cluster size, which is read
                # downstream as "how many independent reports support this
                # event". Their body text is identical, so the similarity path
                # would merge them every time if allowed to try.
                if left.url == right.url:
                    observed.append((left.route_lang or '?', right.route_lang or '?', False))
                    continue
                similarity = compute_similarity(left, right)
                merged = should_merge(left, right, similarity, config)
                # Path 2 applies ONLY to cross-language pairs. That restriction
                # is deliberate and worth stating: path 1 is *structurally*
                # blind across scripts -- Devanagari and Latin share no tokens,
                # so it scores every such pair at ~0 no matter how obviously
                # they match. Within a language it can see fine; whether it
                # sees *well* is a separate question that needs weights fitted
                # on a labelled dev set.
                #
                # Applying these unfitted weights to same-language pairs would
                # confound a structural fix with an untested retuning, and
                # would over-merge in ways nothing can currently measure. On
                # the existing test fixture it merges two Dhading reports with
                # identical dates and death counts that the tuned path keeps
                # apart -- plausibly correct, but "plausibly" is not a
                # standard this project can afford right now.
                if not merged:
                    structured = structured_pair_similarity(left, right, tfidf)
                    if (left.route_lang or '?') != (right.route_lang or '?'):
                        merged = cross_language_corroborated_merge(
                            left, right, structured
                        )
                    elif same_day_corroborated_merge(left, right, structured):
                        merged = True
                if merged:
                    merged = union_within_date_span(
                        parents,
                        date_spans,
                        left.record_key,
                        right.record_key,
                        config.max_cluster_span_days,
                    )
                observed.append((left.route_lang or '?', right.route_lang or '?', merged))

    grouped: dict[str, list[EventRecord]] = {}
    for event in events:
        grouped.setdefault(find(parents, event.record_key), []).append(event)

    clusters = sorted(
        [sorted(cluster, key=event_sort_key) for cluster in grouped.values()],
        key=lambda cluster: event_sort_key(cluster[0]),
    )
    return clusters, merge_rate_by_language_pair(observed)


def compute_similarity(left: EventRecord, right: EventRecord) -> PairSimilarity:
    """Compute normalized title/body similarity for one candidate pair."""

    headline_sim = fuzz.token_set_ratio(left.title or '', right.title or '') / 100.0
    body_sim = 0.0
    if left.body_text and right.body_text:
        body_sim = fuzz.token_set_ratio(left.body_text[:2000], right.body_text[:2000]) / 100.0
    return PairSimilarity(
        headline_sim=headline_sim,
        body_sim=body_sim,
        day_diff=abs((right.event_date - left.event_date).days),
    )


def should_merge(left: EventRecord, right: EventRecord, similarity: PairSimilarity, config: DedupConfig) -> bool:
    """Return whether two candidate rows should be clustered together."""

    if casualty_vectors_conflict(left, right, config.guard_deaths_delta):
        return False

    # A similar report on another day is often a new failure on the same road
    # or in the same monsoon-affected municipality. Text alone is not enough
    # to bridge dates; require a language-neutral fact or exceptionally close
    # prose. This also prevents recurring source boilerplate from chaining
    # unrelated failures together.
    if similarity.day_diff > 0 and not cross_date_corroboration(
        left, right, similarity, config
    ):
        return False

    headline_threshold = config.headline_sim_threshold
    body_threshold = config.body_sim_threshold
    if similarity.day_diff > config.primary_window_days:
        headline_threshold = min(0.99, headline_threshold + 0.05)
        body_threshold = min(0.99, body_threshold + 0.04)

    if left.municipality and right.municipality and left.municipality != right.municipality:
        if similarity.headline_sim < 0.92 and similarity.body_sim < config.high_body_sim_threshold:
            return False

    if bool(left.municipality) != bool(right.municipality):
        stricter_headline = max(0.90, headline_threshold + 0.06)
        if similarity.headline_sim < stricter_headline and similarity.body_sim < config.high_body_sim_threshold:
            return False

    similarity_ok = (
        similarity.headline_sim >= headline_threshold
        or similarity.body_sim >= body_threshold
    )
    if not similarity_ok:
        return False

    municipality_guard = True
    if config.prefer_same_municipality and left.municipality and right.municipality:
        municipality_guard = left.municipality == right.municipality
    deaths_guard = deaths_within_delta(left.deaths, right.deaths, config.guard_deaths_delta)
    body_guard = similarity.body_sim >= config.high_body_sim_threshold
    return municipality_guard or deaths_guard or body_guard


def casualty_vectors_conflict(left: EventRecord, right: EventRecord, delta: int) -> bool:
    """Return whether any comparable casualty field contradicts the other."""

    for field in ('deaths', 'missing', 'injured'):
        left_value = getattr(left, field)
        right_value = getattr(right, field)
        if left_value is not None and right_value is not None:
            if abs(left_value - right_value) > delta:
                return True
    return False


def cross_date_corroboration(
    left: EventRecord,
    right: EventRecord,
    similarity: PairSimilarity,
    config: DedupConfig,
) -> bool:
    """Require factual support before linking reports assigned different dates."""

    same_municipality = bool(
        left.municipality
        and right.municipality
        and left.municipality == right.municipality
    )
    if not same_municipality:
        return similarity.body_sim >= 0.99

    same_ward = bool(left.ward and right.ward and left.ward == right.ward)
    casualty_match = any(
        left_value is not None
        and right_value is not None
        and abs(left_value - right_value) <= config.guard_deaths_delta
        for left_value, right_value in (
            (left.deaths, right.deaths),
            (left.missing, right.missing),
            (left.injured, right.injured),
        )
    )
    return (
        same_ward
        or casualty_match
        or similarity.headline_sim >= 0.92
        or similarity.body_sim >= config.high_body_sim_threshold
    )


def same_day_corroborated_merge(
    left: EventRecord,
    right: EventRecord,
    structured: SimilarityBreakdown,
) -> bool:
    """Recover conservative same-language misses using independent facts.

    Identity alone is deliberately insufficient: two failures can occur in one
    municipality on one day. A recovery therefore needs a named municipality
    plus either casualty/ward agreement, or both a near-exact place match and
    substantial TF-IDF text overlap.
    """

    if left.event_date != right.event_date or structured.conflict is not None:
        return False
    if not left.municipality or left.municipality != right.municipality:
        return False

    administrative_or_casualty = (
        structured.ward == 1.0 or structured.casualties == 1.0
    )
    if administrative_or_casualty:
        return (
            structured.score >= 0.85
            and (structured.place_translit >= 0.75 or structured.text >= 0.30)
        )
    return (
        structured.score >= 0.90
        and structured.place_translit >= 0.90
        and structured.text >= 0.55
    )


def cross_language_corroborated_merge(
    left: EventRecord,
    right: EventRecord,
    structured: SimilarityBreakdown,
) -> bool:
    """Merge cross-script reports only when two factual signals agree."""

    if not structured.should_merge:
        return False

    administrative_or_casualty = (
        structured.ward == 1.0 or structured.casualties == 1.0
    )
    same_municipality_and_place = (
        structured.municipality == 1.0
        and structured.place_translit >= 0.75
    )
    if left.event_date == right.event_date:
        return (
            structured.score >= 0.85
            and (administrative_or_casualty or same_municipality_and_place)
        )

    # Across dates, municipality/place agreement can simply identify a
    # recurrent road location. Require a casualty or ward match instead.
    return structured.score >= 0.85 and administrative_or_casualty


def deaths_within_delta(left: int | None, right: int | None, delta: int) -> bool:
    """Return whether both death counts are present and close enough."""

    if left is None or right is None:
        return False
    return abs(left - right) <= delta


def build_cluster_summary(cluster: list[EventRecord], inserted_at: str, cluster_id: str | None = None) -> dict[str, Any]:
    """Build one cluster_summary row."""

    urls = sorted({event.url for event in cluster})
    sources = sorted({event.source for event in cluster})
    dates = sorted(event.event_date_ad for event in cluster)
    return {
        # Must use the caller-assigned id when given: build_cluster_id alone is
        # not unique (see assign_cluster_ids), and cluster_summary.cluster_id
        # carries a UNIQUE constraint.
        'cluster_id': cluster_id or build_cluster_id(cluster),
        'district': cluster[0].district,
        'date_min': dates[0],
        'date_max': dates[-1],
        # Distinct ARTICLES, not records. `size` is read as "how many
        # independent reports support this event", and one article splitting
        # into several district-days must not read as several reports. While
        # every article produced exactly one record these were identical, so
        # this changes nothing for a primary-only run.
        'size': len(urls),
        'record_count': len(cluster),
        'secondary_record_count': sum(1 for event in cluster if event.is_secondary),
        'sources': json.dumps(sources, ensure_ascii=False, sort_keys=True),
        'urls': json.dumps(urls, ensure_ascii=False, sort_keys=True),
        'inserted_at': inserted_at,
    }


def cluster_is_secondary_only(cluster: list[EventRecord]) -> bool:
    """Whether every record in this cluster was recovered, none reported directly.

    These are the district-days most likely to be wrong: no article named this
    district-day as its subject, and the evidence is one sentence in an article
    about somewhere or somewhen else. They are flagged so any analysis can
    exclude them wholesale, and gated by :func:`secondary_only_cluster_admitted`.
    """

    return bool(cluster) and all(event.is_secondary for event in cluster)


def secondary_only_cluster_admitted(cluster: list[EventRecord]) -> bool:
    """Whether a cluster resting solely on recovered records may become an event.

    A recovered record whose date came from a relative cue -- 'last night',
    'today' -- is not enough on its own. Those cues are how a reporter refers to
    the event already being reported, so a district-day resting on one is the
    single most likely way a fabricated event enters a release. A firm anchor
    (an explicit date, or a named weekday) is required.
    """

    if not cluster_is_secondary_only(cluster):
        return True
    return any((event.date_basis or '') in FIRM_DATE_BASES for event in cluster)


def build_canonical_event(cluster: list[EventRecord], inserted_at: str, cluster_id: str | None = None) -> dict[str, Any]:
    """Build one canonical_events row from a cluster."""

    representative = choose_representative(cluster)
    cluster_id = cluster_id or build_cluster_id(cluster)
    municipalities = sorted({event.municipality for event in cluster if event.municipality})
    wards = sorted({event.ward for event in cluster if event.ward})
    place_names = sorted({event.place_name_raw for event in cluster if event.place_name_raw})
    urls = sorted({event.url for event in cluster})
    payload = {
        'urls': urls,
        'sources': sorted({event.source for event in cluster}),
        'size': len(urls),
        'record_count': len(cluster),
        'representative_url': representative.url,
        'municipality_candidates': municipalities,
        'ward_candidates': wards,
        'place_name_candidates': place_names,
        'extraction_basis': representative.extraction_basis,
        'secondary_only': cluster_is_secondary_only(cluster),
        'evidence_sentences': sorted(
            {event.evidence_sentence for event in cluster if event.evidence_sentence}
        ),
    }
    return {
        'event_id': f"event_{stable_hash('canonical', cluster_id)[:16]}",
        'dedup_cluster_id': cluster_id,
        'event_date_ad': representative.event_date_ad,
        'district': representative.district,
        'province': representative.province or district_to_province(representative.district),
        'municipality': representative.municipality,
        'municipality_candidates_json': json.dumps(municipalities, ensure_ascii=False, sort_keys=True),
        'ward_candidates_json': json.dumps(wards, ensure_ascii=False, sort_keys=True),
        'place_name_candidates_json': json.dumps(place_names, ensure_ascii=False, sort_keys=True),
        'event_payload': json.dumps(payload, ensure_ascii=False, sort_keys=True),
        'inserted_at': inserted_at,
    }


def choose_representative(cluster: list[EventRecord]) -> EventRecord:
    """Choose a deterministic representative article for a cluster."""

    return sorted(
        cluster,
        key=lambda event: (
            # A directly reported record always represents the event over one
            # recovered from a passing sentence, however confident the latter
            # looks: the recovered record's municipality, casualties and
            # trigger belong to the article's own subject, not to this
            # district-day.
            event.is_secondary,
            event.article_role != ROLE_FIRST_REPORT,
            -event.confidence_score,
            event.event_date_ad,
            event.municipality or '',
            event.url,
        ),
    )[0]


def build_cluster_id(cluster: list[EventRecord]) -> str:
    """Return a content-stable cluster identifier.

    Hashes the event's *identity* -- district, canonical date, municipality --
    not its member URL set (review section 8.2).

    Why this matters: hashing the URL set means every ``cluster_id``, and
    therefore every ``event_id``, changes whenever coverage changes. Add a
    source, re-fetch a failed article, or merge one extra duplicate, and the
    identifiers of *unrelated* events churn. That breaks any longitudinal audit
    and makes a DOI'd dataset version impossible to reconcile with the next one
    -- a reader cannot ask "is event X still in the v2 inventory?".

    Under this scheme, an event keeps its identity as long as it happened in
    the same place on the same day, which is what identity should mean here.
    Adding the ekantipur report of a landslide already covered by setopati now
    grows the cluster instead of renaming the event.

    Collision note: two clusters sharing (district, date, municipality) produce
    the same identity. These are review candidates rather than assumed missed
    merges because several physical failures can occur in one municipality on
    one day. ``assign_cluster_ids`` reports and safely disambiguates them.

    Collisions are disambiguated with a deterministic suffix so the identifier
    stays unique. Identifiers for non-colliding clusters -- the large majority --
    remain content-stable across coverage changes, which is the point.
    """

    canonical_date = min(event.event_date_ad for event in cluster)
    districts = sorted({event.district for event in cluster})
    municipalities = sorted({event.municipality for event in cluster if event.municipality})
    identity = (
        districts[0] if districts else '',
        canonical_date,
        municipalities[0] if municipalities else '',
    )
    return f"cluster_{stable_hash('dedup_v2', identity)[:16]}"


def assign_cluster_ids(
    clusters: list[list[EventRecord]],
    preferred_ids: dict[int, str] | None = None,
) -> tuple[dict[int, str], int]:
    """Map each cluster index to a unique id, disambiguating collisions.

    Returns the mapping and the number of extra clusters sharing an identity.
    The count is a review diagnostic, not an error count: some are missed
    merges and others are genuinely distinct same-place, same-day failures.

    Disambiguation is by position in a deterministic ordering (earliest member
    URL), so a given run always produces the same ids.
    """

    preferred_ids = preferred_ids or {}
    if len(set(preferred_ids.values())) != len(preferred_ids):
        raise ValueError('Preferred cluster IDs must be unique')
    reserved = set(preferred_ids.values())
    seen: dict[str, int] = {}
    assignments: dict[int, str] = {}
    collisions = 0
    ordered = sorted(
        range(len(clusters)),
        key=lambda index: min(event.url for event in clusters[index]),
    )
    for index in ordered:
        base = build_cluster_id(clusters[index])
        if index in preferred_ids:
            preferred = preferred_ids[index]
            # A reviewed merge can add better municipality evidence and thus
            # change the computed identity base. Retaining the nominated
            # survivor is the point of this explicit override; uniqueness is
            # enforced above and unreviewed clusters still use the base ID.
            assignments[index] = preferred
            seen[base] = seen.get(base, 0) + 1
            continue
        occurrence = seen.get(base, 0)
        candidate = base if occurrence == 0 else f'{base}_{occurrence}'
        while candidate in reserved or candidate in assignments.values():
            occurrence += 1
            candidate = f'{base}_{occurrence}'
        seen[base] = occurrence + 1
        assignments[index] = candidate
    identity_counts: dict[str, int] = {}
    for cluster in clusters:
        base = build_cluster_id(cluster)
        identity_counts[base] = identity_counts.get(base, 0) + 1
    collisions = sum(count - 1 for count in identity_counts.values())
    return assignments, collisions


def export_cluster_summary_csv(
    path: Path,
    clusters: list[list[EventRecord]],
    inserted_at: str,
    cluster_ids: dict[int, str] | None = None,
) -> None:
    """Export cluster summary rows to CSV."""

    ensure_directory(path.parent)
    ids = cluster_ids or assign_cluster_ids(clusters)[0]
    rows = [build_cluster_summary(c, inserted_at, ids[i]) for i, c in enumerate(clusters)]
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                'cluster_id',
                'district',
                'date_min',
                'date_max',
                'size',
                'record_count',
                'secondary_record_count',
                'sources',
                'urls',
                'inserted_at',
            ],
        )
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item['cluster_id']):
            writer.writerow(row)


def export_canonical_events_csv(
    path: Path,
    clusters: list[list[EventRecord]],
    inserted_at: str,
    cluster_ids: dict[int, str] | None = None,
) -> None:
    """Export canonical event rows to CSV."""

    ensure_directory(path.parent)
    ids = cluster_ids or assign_cluster_ids(clusters)[0]
    rows = [build_canonical_event(c, inserted_at, ids[i]) for i, c in enumerate(clusters)]
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                'event_id', 'dedup_cluster_id', 'event_date_ad', 'district', 'province', 'municipality',
                'municipality_candidates_json', 'ward_candidates_json', 'place_name_candidates_json',
                'event_payload', 'inserted_at',
            ],
        )
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item['event_id']):
            writer.writerow(row)


def reset_dedup_outputs(connection: sqlite3.Connection) -> None:
    """Clear prior dedup outputs before rebuilding them deterministically."""

    connection.execute('UPDATE article_events SET dedup_cluster_id = NULL')
    connection.execute('DELETE FROM cluster_summary')
    connection.execute('DELETE FROM canonical_events')


def find(parents: dict[str, str], item: str) -> str:
    """Find a union-find root with path compression."""

    root = parents[item]
    if root != item:
        root = find(parents, root)
        parents[item] = root
    return root


def union(parents: dict[str, str], left: str, right: str) -> None:
    """Union two union-find sets deterministically."""

    left_root = find(parents, left)
    right_root = find(parents, right)
    if left_root == right_root:
        return
    parent, child = sorted((left_root, right_root))
    parents[child] = parent


def union_within_date_span(
    parents: dict[str, str],
    date_spans: dict[str, tuple[date, date]],
    left: str,
    right: str,
    max_span_days: int,
) -> bool:
    """Union two sets only when the resulting cluster stays temporally bounded."""

    left_root = find(parents, left)
    right_root = find(parents, right)
    if left_root == right_root:
        return True
    date_min = min(date_spans[left_root][0], date_spans[right_root][0])
    date_max = max(date_spans[left_root][1], date_spans[right_root][1])
    if (date_max - date_min).days > max_span_days:
        return False
    parent, child = sorted((left_root, right_root))
    parents[child] = parent
    date_spans[parent] = (date_min, date_max)
    del date_spans[child]
    return True


def event_sort_key(event: EventRecord) -> tuple[str, str, str, str]:
    """Return a stable sort key for event records."""

    return (event.district, event.event_date_ad, event.municipality or '', event.url)
