# External validation linked to inventory v0.6.0

Generated on 2026-09-15 against
`data/outputs/canonical_events_final.csv`, SHA-256
`3b335babbfcbe0b50d2aad9023e08e55a2ca6e8e0881729615df33e2c9b9d0e8`.
The common observation cutoff is 2026-08-08.

## Comparison frame

| Quantity | Count |
|---|---:|
| Eligible canonical news events | 2,880 |
| BIPAD rows | 5,345 |
| Harmonized BIPAD incident clusters | 4,095 |
| BIPAD clusters with a strong Tier A/B candidate | 561 |
| BIPAD clusters with only a weak Tier C candidate | 1,150 |
| BIPAD clusters with no candidate | 2,384 |
| Canonical events without a strong Tier A/B candidate | 2,310 |
| COOLR inventory groups / polygon features | 1 / 796 |

Five of the 2,885 released canonical rows are outside the common comparison
frame or excluded to prevent circular use of BIPAD-assisted discovery.

## Agreement interpretation

Tier A links require the strongest date and place support. Their observed
news-side overlap is 0.1441, compared with 0.0582 under 100 date permutations
(chance-corrected 0.0859; empirical p=0.0099). Tier B overlap is 0.0698 versus
0.0559 expected by chance. Tier C district-level links are below their
permutation expectation and are retained only as search leads.

BIPAD is incomplete, uses a different reporting unit, and may partly depend on
media reports. It is therefore not ground truth. Precision and recall against
BIPAD are not reported. The capture-recapture result in the machine-readable
output is exploratory and assumption-sensitive rather than a headline result.

## Auditable outputs

- `data/outputs/external_agreement.json`
- `data/outputs/external_bipad_match_candidates.csv`
- `data/outputs/external_match_report.md`
- `data/outputs/external_search_seeds.csv`
- `data/outputs/external_unmatched_news.csv`
- `data/outputs/external_coolr_inventories.csv`

The JSON and compact report record the canonical input path and SHA-256. This
prevents a mutable working-database snapshot from silently changing the
comparison population.
