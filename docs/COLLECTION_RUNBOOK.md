# Collection runbook — fixing the data gaps

**Run these on your own machine.** The development sandbox cannot reach any
Nepali news site, so every step here needs your network.

---

## The problem, in one table

Articles collected per source-year. `·` means **nothing at all**.

| source | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| myrepublica | 97 | 119 | 90 | 115 | 82 | 102 | 79 | 79 | 83 | 156 | 10 | · |
| setopati | · | · | 65 | 65 | 85 | 240 | 223 | 151 | 166 | 331 | 153 | 4 |
| himalayan-times | 142 | 209 | 121 | 81 | 66 | 132 | 61 | 29 | 20 | 89 | · | · |
| online-khabar | · | · | · | · | · | · | · | · | 50 | 177 | 88 | 21 |
| ekantipur | · | · | · | · | 1 | 1 | · | · | 1 | · | 11 | 228 |
| ratopati | · | · | · | · | · | · | · | · | · | · | 68 | 174 |
| kathmandu-post | · | · | · | · | 1 | · | 2 | · | · | · | · | 57 |
| rising-nepal | · | · | · | · | · | · | · | 32 | · | 6 | · | 1 |

**For 2015–2019 this is a two-source inventory**, not eight. eKantipur and the
Kathmandu Post — two of Nepal's largest outlets — contribute essentially nothing
before 2025. That is why 2024 has 4.5× the articles of 2016: coverage, not
landslide activity.

## Why, exactly

The gap follows the discovery method precisely:

| method | sources | earliest article |
|---|---|---|
| tag pagination | myrepublica, setopati | 2012, 2017 |
| **Google News RSS** | himalayan-times, ekantipur, kathmandu-post, rising-nepal | 2015*, 2019, 2019, 2022 |

**Google News RSS `site:` queries return only recent items and never backfill
archives.** Every source relying on it is missing most of its history. This is
review §9.11, now confirmed in the data.

\* himalayan-times reaches 2015 but 615 of its 992 rows are HTTP 429 error
pages, so its real coverage is far thinner than it looks.

---

## Step 1 — recover the 615 rate-limited articles

**Already fixed in code.** `scrape/fetcher.py` used to return immediately on any
`HTTPError`, so a 429 was accepted as the site's answer and its error page was
stored as the article body. It now retries with exponential backoff, honours
`Retry-After`, and — critically — **stores no text when a fetch ultimately
fails**, so a failed row can never again be mistaken for an article.

Slow the crawl down before re-running, or you will be rate-limited again:

```yaml
# config.yaml
runtime:
  rate_limit_seconds: 3.0    # was 1.0
  retries: 5                 # was 3
```

Then re-fetch only the failed rows:

```bash
python -m landslide_inventory.run --stage collect --config config.yaml
python -m landslide_inventory.run --stage article_quality --config config.yaml
```

`article_quality` should show the `http_429` count falling from 615 toward zero.
Expect roughly **+600 usable articles**, concentrated in himalayan-times
2015–2020 — the years that most need them.

## Step 2 — find working archive entry points

Google News RSS cannot be fixed; it has to be replaced with per-site tag or
archive pagination, as myrepublica and setopati already use.

Tag URLs change and cannot be guessed reliably, so verify before committing:

```bash
python scripts/verify_entry_points.py
```

It probes candidate URLs for each broken source and reports whether each returns
200, contains article links, and paginates. A URL is `USABLE` only if it lists
10+ distinct article links.

If a candidate fails, open the site, find its landslide tag page by hand, and
check that one:

```bash
python scripts/verify_entry_points.py --url https://ekantipur.com/tag/<slug>
```

Then paste the emitted YAML into `config.yaml` under that source's
`entry_points`, and **delete its `googlenews` entry** so archive pagination
becomes the primary path.

Sites to check by hand, in value order:

1. **ekantipur** — largest Nepali-language daily, ~9 years missing. Biggest win.
2. **kathmandu-post** — largest English daily, ~11 years missing.
3. **online-khabar** — nothing before 2023; its trend pagination stopped early,
   so check whether deeper pages exist.
4. **ratopati** — nothing before 2025, same question.
5. **rising-nepal** — smallest; do it last.

## Step 3 — collect, then re-run the pipeline

```bash
python -m landslide_inventory.run --stage collect --config config.yaml
python -m landslide_inventory.run --stage normalize_dates --config config.yaml
python -m landslide_inventory.run --stage lang --config config.yaml
python -m landslide_inventory.run --stage extract --config config.yaml
python -m landslide_inventory.run --stage event_specificity --config config.yaml
python -m landslide_inventory.run --stage location_consistency --config config.yaml
python -m landslide_inventory.run --stage filter_scope --config config.yaml
python -m landslide_inventory.run --stage dedup --config config.yaml
python -m landslide_inventory.run --stage event_typing --config config.yaml
python -m landslide_inventory.run --stage export_final --config config.yaml
```

**Snapshot the database first.** `extract` is destructive to a degree that is
only partly recoverable:

```bash
cp data/raw_sqlite/landslide_inventory.sqlite \
   data/raw_sqlite/landslide_inventory.snapshot_$(date +%Y%m%d)_pre_recollect.sqlite
```

## Step 4 — draw a fresh test set

The v1 locked set has been scored twice and is spent. New articles also change
the sampling frame, so the old sample no longer represents the corpus.

Bump `DESIGN_VERSION` to `'v2'` in `validation/locked_test_set.py`, then:

```bash
python -m landslide_inventory.run --stage locked_test_set --config config.yaml
```

The stage refuses to overwrite an existing manifest, so v1 stays intact for
comparison.

---

## What to expect

| | now | after |
|---|--:|--:|
| raw articles | 4,453 | plausibly 8,000–12,000 |
| usable (200 + text) | 3,670 | +600 from the 429 recovery alone |
| 2015–2019 sources | effectively 2 | 4–6 |
| headline events | 772 | unknown, but the year curve should flatten |

**The most important outcome is not the count.** It is whether the 2024/2016
ratio falls from 4.5× toward something defensible. If it does, the temporal
distribution becomes reportable. If it does not, the skew is real and belongs in
the limitations section — either way you learn something worth writing down.

## What this does not fix

Collection cannot recover an article a site never published or has since
removed. Some 2015–2016 archive depth is simply gone. Report the recovered
coverage honestly and model reporting effort as an exposure offset (§4.4)
rather than assuming the remaining curve is landslide activity.
