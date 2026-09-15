# Secondary-failure precision gate

## Decision

The blind census of 154 emitted source-level district-date claims failed the
precision gate. Automated secondary recoveries remain excluded from the
database, canonical inventory, rainfall analysis, and every release.

The human review confirmed the district for 108 claims (70.1%), but confirmed
both district and date for only 52 (33.8%). Those 52 source claims represent 48
distinct district-days. They are retained in a separate, provenance-bearing
manual supplement and are not integrated into the canonical inventory.

| Stratum | Reviewed | District confirmed | District and date confirmed | Joint precision |
|---|---:|---:|---:|---:|
| `cross:firm` | 85 | 56 | 34 | 40.0% |
| `cross:soft` | 62 | 45 | 14 | 22.6% |
| `same:firm` | 7 | 7 | 4 | 57.1% |
| **Overall** | **154** | **108** | **52** | **33.8%** |

Among the 108 claims whose district was confirmed, 52 dates were confirmed, 11
were wrong, and 45 remained unclear. Date attribution is therefore the dominant
failure mode.

## Reproduce

```bash
PYTHONPATH=src .venv/bin/python scripts/score_secondary_precision.py
PYTHONPATH=src .venv/bin/pytest tests/test_secondary_precision_score.py -q
```

Outputs:

- `data/outputs/secondary_precision_report.json`
- `data/outputs/secondary_failures_manually_verified.csv`

`secondary_failures.csv` remains a dry-run diagnostic. No code path ingests it
or the manual supplement into the inventory. The supplement confirms those
particular claims; it does not show that the extractor generalises.

## What follows

The extractor has now been redesigned as a deliberately strict second version.
It accepts only explicit AD or BS dates stated in the same evidence sentence,
does not propagate dates between sentences, strips byline-prefixed datelines,
and rejects district aliases used as local feature names such as `Kavre Bhir`.

The strict-v2 dry run recovered 23 source claims representing 21 distinct
district-days. Thirteen district-days are novel relative to the current 1,508
case-day baseline (0.86%). All 13 overlap claims already confirmed in the spent
human review. That is encouraging development evidence, not a new precision
estimate: the current corpus contains no newly emitted claim that is still
unseen by the annotator.

Locked test v8 contains 145 previously unjudged articles: a census of 35 unspent
legacy-extractor candidates, 80 district-rich articles, and 30 ordinary controls.
It has zero overlap with prior evaluation URLs. All 145 rows were labelled, but
every row records `ChatGPT` as its annotator. The result is therefore a model
diagnostic, not an independent human locked-test estimate.

Against the pipeline's existing primary district-days, these labels identify 59
exact supported district-days the pipeline lacks across 52 articles. Strict v2
recovered 0 of 59 (recall 0.0; unweighted Wilson 95% CI 0.000-0.061). Its only
prediction occurred in an article whose event pairs remained unresolved, so
precision is not estimable rather than zero. Independent human adjudication
would still be required for a publishable estimate.

The locked result fails the utility gate. Automated secondary records remain
excluded from the database, canonical inventory, rainfall analysis, and release.

Outputs:

- `data/outputs/secondary_failures_strict_v2.csv`
- `data/outputs/secondary_failures_strict_v2_summary.json`
- `data/outputs/secondary_locked_v8_score.json`
- `data/outputs/secondary_locked_v8_comparison.csv`
