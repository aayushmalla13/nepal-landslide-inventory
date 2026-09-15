# External source ingestion

The external-source layer collects observations that can improve discovery,
triangulation, and later recall analysis. It does **not** insert them into
`raw_articles` or `canonical_events`. This avoids circular evaluation—for
example, BIPAD cannot both generate an event and independently validate that
same news inventory event.

## Commands

Probe every configured source without storing records:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage external_probe --config config.yaml
```

Run one disabled-by-default source explicitly:

```bash
LS_EXTERNAL_SOURCE=bipad PYTHONPATH=src .venv/bin/python \
  -m landslide_inventory.run --stage external_collect --config config.yaml
```

Several sources can be selected with a comma-separated value. To make a source
part of every external collection run, set its `enabled` value to `true`.

Export the isolated table:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage external_export --config config.yaml
```

The result is `data/outputs/external_records.csv`. The SQLite table retains the
provider's raw historical coverage, while this export is automatically bounded
to the configured 2015–2026 study window; undated evidence is retained. Every source run is recorded
in `external_source_runs`; normalized records are idempotently upserted into
`external_records` using a deterministic ID.

For Box-synced workspaces, the live SQLite database can be kept outside Box by
setting `LS_SQLITE_PATH`. Use `scripts/run_local_db.sh` to run stages with that
database consistently.

Compare BIPAD with the canonical news inventory and group COOLR correctly:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage external_match --config config.yaml
```

This stage uses the latest available BIPAD incident date as the common
comparison cutoff. It writes:

- `external_match_report.md`: compact input and candidate-overlap summary.
- `external_agreement.json`: six-layer harmonisation, tiered overlap,
  chance-corrected, capture-recapture, aggregate, and unmatched-sample report.
- `external_bipad_match_candidates.csv`: all Tier A/B/C candidate pairs.
- `external_search_seeds.csv`: BIPAD clusters without a strong A/B link,
  ordered with unmatched fatal incidents first. Tier C remains a weak lead.
- `external_unmatched_news.csv`: canonical news events without an A/B link.
- `external_coolr_inventories.csv`: scientific inventory groups and feature
  counts; COOLR polygons are not counted as independent reported incidents.

Search a bounded number of the fatal unmatched seeds for dated news-index
candidates:

```bash
LS_EXTERNAL_SEED_LIMIT=10 PYTHONPATH=src .venv/bin/python \
  -m landslide_inventory.run --stage external_discover --config config.yaml
```

The stage searches municipality and district fallbacks and writes
`external_news_candidates.csv` plus `external_seed_discovery_report.md`.
Google News wrapper links and titles are candidates only. They remain in
`external_news_candidates`, outside `raw_articles`, until the publisher URL is
resolved and the article content is reviewed. This prevents index false
positives and keeps BIPAD-assisted discoveries identifiable for exclusion from
BIPAD agreement analysis. `LS_EXTERNAL_SEED_LIMIT` overrides the configured
batch size without editing YAML.

Candidate review statuses are intentionally evidence-specific:

- `relevant_event`: publisher content describes the seeded date/place event;
  this is the only class eligible for later assisted ingestion.
- `relevant_district`: useful district-level corroboration or a multi-event
  roundup, but not enough to promote as that municipality event.
- `needs_resolution`: the index title looks relevant, but the publisher URL or
  full content is not yet verified.
- `irrelevant`: the publisher content does not describe the seeded event.

After editing `external_news_candidates.csv`, synchronize the review decisions
back into SQLite before ingestion:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage external_review_sync --config config.yaml
```

The sync stage validates candidate IDs and statuses and updates only
`review_status`, `resolved_url`, and `review_notes`. It does not overwrite
ingestion status fields.

Never convert `relevant_district` into an event-specific label. Any eventually
ingested `relevant_event` article must retain an `external_seed_bipad` discovery
method and must be excluded from BIPAD agreement calculations to avoid circular
validation.

After review, ingest only publisher-resolved `relevant_event` rows:

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run \
  --stage external_ingest --config config.yaml
```

The stage refuses every other review status, requires an HTTP-successful article
parse of at least 200 characters, and records ingestion status/errors back on
the candidate row. Inserted articles are tagged `external_seed_bipad` so both
BIPAD agreement and locked-test sampling can exclude them.

For e-paper issues, create an issue-level review queue first:

```bash
PYTHONPATH=src .venv/bin/python scripts/epaper_review_queue.py
```

This writes `data/outputs/epaper_review_queue.csv`. Each row is one complete
issue with bounded keyword snippets. Reviewers should identify an individual
article and fill `review_status` (`relevant_event`, `relevant_district`,
`needs_resolution`, or `irrelevant`) plus `article_url` and event fields where
available. An issue row is never itself a canonical event.

## Implemented adapters

| Adapter | Intended source | Output semantics | Access note |
|---|---|---|---|
| `bipad` | BIPAD incident API | Government incident | Public API; tolerant mapping handles nested API fields |
| `html_documents` | legacy DRR Portal | Government archive document | HTML/PDF listing traversal |
| `ndrrma_bulletins` | NDRRMA daily bulletins | Government bulletin | HTML/PDF; PDF text extracted when `pypdf` is available |
| `nepal_police`, `armed_police` | Nepal Police and APF | Official response report | Preserves the report wording and raw payload |
| `road_notices` | Nepal Police road notices | Road-obstruction notice | Discovery evidence, not automatically a landslide event |
| `kantipur_epaper` | Kantipur/Kathmandu Post e-paper | Dated news-archive issue | Set `KANTIPUR_EPAPER_COOKIE` when the site requires a session |
| `wayback_cdx` | Internet Archive | Archived-URL metadata or fetched capture text | Set `fetch_bodies: true` for bounded HTML retrieval |
| `common_crawl` | Common Crawl index | Crawl metadata or WARC-range text | Uses the current collection unless an index is pinned; body retrieval is bounded |
| `media_cloud` | Media Cloud Search API | Indexed story | Set `MEDIACLOUD_API_KEY`; paging honors its default two-requests/minute limit |
| `coolr` / `arcgis` | NASA COOLR FeatureServer | Scientific landslide observation | Configuration limits the query to Nepal |
| `reliefweb` | ReliefWeb reports API | Humanitarian situation report | Set approved `RELIEFWEB_APPNAME` |
| `desinventar` | DesInventar export | Historical disaster-loss record | Download/export CSV locally, then set `input_path` |
| `rss` | Verified official RSS/Atom source | Official alert/feed item | The placeholder URL must be replaced before use |

The generic `generic_json`, `drr_portal`, `delimited_export`, and
`html_documents` adapters can support additional official endpoints without a
new database schema.

## Data policy

- `source_family` makes government, scientific, humanitarian, archive, media,
  and news-archive records distinguishable.
- `incident_date_raw` retains the source string. `incident_date_ad` is populated
  only when normalization succeeds; numeric Bikram Sambat dates are converted.
- Missing casualty values remain null. They are never changed to zero.
- Archive capture dates and publication dates are not treated as incident dates.
- E-paper issues without extractable text remain issue-level archive metadata;
  they are not promoted to hazard events.
- `raw_json`, retrieval time, retrieval medium, content hash, source record ID,
  and source URL preserve auditability.
- External records must be linked to canonical news events in a separate,
  explicit matching/validation analysis. No implicit merge is performed.

## Configuration and credentials

All adapters are present in `config.yaml` and `config.example.yaml`, and are
disabled by default to prevent an ordinary pipeline run from launching a large
network crawl. Secrets are never read from YAML values; only the named
environment variables are resolved at runtime.

Before a large archive collection, reduce the date/domain scope and run the
probe stage. Respect the provider's terms, access controls, robots policy, and
rate limits. The default external rate limit is deliberately separate from the
news collector's slower outlet-specific setting.
