# v0.2 older-source collection expansion

Date: 2026-08-10

This is a working v0.2 candidate, not a replacement for the sealed v0.1.0/v3
release. v0.1 remains reproducible from its release bundle and pre-expansion
snapshot.

## What was added

Three Nepali-language archives were productionized:

| source | discovery method | collected | publication years | usable |
|---|---|---:|---|---:|
| Nagarik | year-filtered search with offset pagination | 731 | 2015–2026 | 731 |
| Deshsanchar | WordPress full-text search, oldest-first | 170 | 2017–2019 | 169 |
| Rajdhani | WordPress full-text search, oldest-first | 154 | 2020 | 154 |

The collection is intentionally a historical tranche. Nagarik completed its
bounded year search. Deshsanchar and Rajdhani were stopped after useful older
coverage was saved; their deeper queues are resumable.

The collectors use structural search-result cards rather than keywords in the
URL. This matters because Deshsanchar URLs are numeric/date-based and Rajdhani
URLs are opaque `/id/<number>` paths. Full-text search results are kept even
when the headline itself does not repeat `पहिरो`; navigation, ticker, category,
and share links are excluded.

## Before and after

| measure | sealed v0.1 | working v0.2 | change |
|---|---:|---:|---:|
| raw articles | 4,893 | 5,948 | +1,055 |
| canonical events | 1,614 | 2,008 | +394 |
| headline landslide-family events | 1,271 | 1,586 | +315 |
| road-obstruction reports | 343 | 422 | +79 |

Headline events by year changed as follows:

| year | v0.1 | v0.2 | change |
|---|---:|---:|---:|
| 2015 | 59 | 77 | +18 |
| 2016 | 97 | 110 | +13 |
| 2017 | 83 | 99 | +16 |
| 2018 | 82 | 131 | +49 |
| 2019 | 69 | 85 | +16 |
| 2020 | 170 | 234 | +64 |
| 2021 | 100 | 116 | +16 |
| 2022 | 99 | 116 | +17 |
| 2023 | 96 | 119 | +23 |
| 2024 | 219 | 246 | +27 |
| 2025 | 114 | 151 | +37 |
| 2026 | 83 | 102 | +19 |

The 2024/2016 headline ratio is now 2.2, compared with 2.3 in the sealed v0.1
working database. The added sources increase every year rather than erasing the
remaining reporting skew, which must still be treated as a coverage limitation.

## Independent external comparison

The refreshed common-cutoff comparison contains 2,004 news events, 5,345 BIPAD
rows harmonized into 4,092 incident clusters, and 796 COOLR polygon features.
There are 305 BIPAD clusters with a strong Tier A/B candidate link, 1,136 with
only weak Tier C candidates, and 2,651 with no candidate. BIPAD remains an
independent incomplete observation system, not ground truth; these are overlap
statistics, not precision or recall.

## Validation state

Locked v3 validates the sealed v0.1 population only. Locked v4 was drawn after
the expansion with seed 20260811:

- 381 sampled rows from 4,345 eligible articles;
- 1,600 unique prior-evaluation URLs excluded;
- zero overlap with prior evaluation;
- 105 rows from the three new sources;
- lock hash `884e23f1727f...`.

The working v0.2 inventory must not be released with v3 metrics. Label and
score v4 first.

## Completed deeper archive pass

After v4 was scored, its database was preserved and both resumable archive
queues were completed to their configured URL caps. This added another 1,676
raw articles and produced the final expanded candidate:

| measure | pre-deep v4 population | final candidate | change |
|---|---:|---:|---:|
| raw articles | 5,948 | 7,624 | +1,676 |
| Deshsanchar articles | 170 | 1,200 | +1,030 |
| Rajdhani articles | 154 | 800 | +646 |
| canonical events | 2,008 | 2,387 | +379 |
| headline landslide-family events | 1,586 | 1,912 | +326 |
| road-obstruction reports | 422 | 475 | +53 |

Normalized Deshsanchar coverage now spans 2017–2022 and Rajdhani spans
2020–2024. Locked v5 was drawn from the rebuilt population with seed 20260812:
383 rows from 5,640 eligible articles, zero prior-evaluation overlap, and lock
hash `90e6b24c226e...`. Locked v4 remains the pre-deep checkpoint and must not
be reported as validation of the final 7,624-article population.

## Final additional-source pass

Prospected sixteen additional national outlets. Only two passed both criteria:
a publicly accessible route with demonstrated historical coverage and a
semantic result set that actually respects the landslide query. English
OnlineKhabar provides a public WordPress search API; Nepali Times provides a
complete public sitemap whose hazard-keyword URLs can be bounded safely.

| measure | pre-pass v5 population | final v6 population | change |
|---|---:|---:|---:|
| raw articles | 7,624 | 8,235 | +611 |
| canonical events | 2,387 | 2,498 | +111 |
| headline landslide-family events | 1,912 | 2,026 | +114 |
| road-obstruction reports | 475 | 472 | -3 |

English OnlineKhabar added 600 successfully parsed articles spanning 2019–2026
and contributes to 212 canonical clusters. Nepali Times added 12 successfully
parsed, direct-keyword articles (three canonical clusters); they include 2014–
2016 material, retained in raw provenance while the canonical export remains
within the study period. Khabarhub English and Lokantar were rejected after
direct verification showed that their apparent query pagination served ordinary
homepage/archive content instead of search results.

Locked v6, seed 20260814, sampled 388 rows from 5,869 eligible articles after
2,363 prior-evaluation URLs in the frame were excluded. Prior-evaluation
overlap is zero and the lock hash begins `dec172a52d22`. It is the only test set
that can validate the final population.
