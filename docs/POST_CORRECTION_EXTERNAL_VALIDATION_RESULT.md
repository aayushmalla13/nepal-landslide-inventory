# Post-correction external validation result

## Outcome

The six-layer BIPAD agreement analysis has been rerun against the exact locked
v0.8 post-correction inventory candidate and frozen as:

- Release: `nepal_landslide_external_validation_v0.1.0_20260923`
- Inventory: `nepal_landslide_inventory_v0.8.0_candidate_20260923`
- Inventory SHA-256:
  `0822515b56693af22daf2e3cc6e63b178eb41fefa46a8b607a47d6da9efdcd07`
- Normalized BIPAD snapshot SHA-256:
  `0f8ffe6210e78560a23d4b07fee5c61ccfa73e7ca389f05415553d89ed81f2dc`
- Bundle lock:
  `cfdb4fa1961b0c4635da722a3903867f176e7f9c3ae9d0c6c5793b48a8463324`
- Status: `analysis_complete_inventory_candidate_pending_validation`

The common comparison window is 2015-01-01 through 2026-08-08, the final date
in the stored BIPAD collection. The external source was not recollected, which
keeps the government comparison input fixed while the candidate inventory is
changed.

## Comparison frame

- 2,868 eligible canonical news events
- 5,345 in-window BIPAD rows
- 4,095 harmonized BIPAD incident clusters
- 4,309 Tier A/B/C candidate pairs
- 579 BIPAD clusters with a strong Tier A/B candidate
- 1,115 BIPAD clusters with only a weak Tier C candidate
- 2,401 BIPAD clusters with no candidate
- 2,265 canonical news events without a strong Tier A/B candidate

Four of the 2,872 candidate rows fall outside the common comparison frame or
are excluded to prevent circular use of BIPAD-assisted discovery.

## Agreement

Tier A requires the strongest municipality/date support. Its observed news-side
overlap is 0.1510, compared with 0.0613 under 100 date permutations;
chance-corrected overlap is 0.0897 with empirical p=0.0099. Tier B observed
overlap is 0.0774 versus 0.0623 expected by chance, for chance-corrected overlap
of 0.0151 and empirical p=0.0099. Tier C observed overlap is below its
permutation expectation and remains a search lead rather than validation.

Relative to the earlier v0.6 comparison, Tier A observed overlap increased from
0.1441 to 0.1510, Tier A chance-corrected overlap from 0.0859 to 0.0897, and
strongly linked BIPAD clusters from 561 to 579. These are modest improvements,
not evidence that either source is complete.

District-year counts have Spearman rho 0.3254; district-month counts have rho
-0.1244. The negative monthly correlation emphasizes that reporting intensity,
source coverage and different observation units dominate fine temporal count
agreement.

## Interpretation

BIPAD is incomplete, uses a different administrative reporting unit, and may
partly depend on media reports. It is not ground truth. Precision and recall
against BIPAD are therefore not reported and must not be derived from these
outputs. The capture-recapture estimate is retained only as exploratory,
assumption-sensitive evidence.

The release contains the exact normalized BIPAD input snapshot, candidate-pair
table, unmatched tables, COOLR inventory summary, machine-readable agreement,
and compact report. Both input hashes and every artifact are checksummed.

## Next gate

Draw and score a fresh locked independent validation sample from the v0.8
candidate. Do not reuse the prior post-correction validation rows and do not
promote the inventory, rainfall analysis, or external result until that gate is
complete.
