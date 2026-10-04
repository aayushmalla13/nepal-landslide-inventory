# Post-correction rainfall result

## Outcome

The unchanged rainfall-analysis design has been rerun against the locked v0.8
post-correction inventory candidate and frozen as:

- Release: `nepal_landslide_rainfall_v0.9.0_20260923`
- Inventory: `nepal_landslide_inventory_v0.8.0_candidate_20260923`
- Inventory SHA-256:
  `0822515b56693af22daf2e3cc6e63b178eb41fefa46a8b607a47d6da9efdcd07`
- Bundle lock:
  `d1baf10abc90973ce16cd73238c6111e608e97dd4c46c0f15c1cb9e968c90845`
- Status: `analysis_complete_inventory_candidate_pending_validation`

The CHIRPS input remains complete for all 77 districts from 2015-01-01 through
2026-07-31. Eighteen otherwise eligible events after the rainfall endpoint were
excluded rather than assigned zero rainfall.

## Main result

The corrected inventory contributes 1,453 primary case-days and 6,059 matched
controls. The selected windows and cutpoints are unchanged from rainfall v0.8:

- Concurrent primary: R5, 51.6 mm; temporal-test AUC 0.677 (95% CI
  0.644-0.705), sensitivity 0.458, specificity 0.776.
- Strictly antecedent co-primary: R3, 23.7 mm; temporal-test AUC 0.651 (95% CI
  0.617-0.678), sensitivity 0.511, specificity 0.722.
- All-years conditional odds ratio: 1.233 per 10 mm for concurrent R5 (95% CI
  1.198-1.269).

Relative to rainfall v0.8, primary case-days decreased from 1,508 to 1,453.
Concurrent temporal-test AUC changed from 0.675 to 0.677 and antecedent AUC from
0.649 to 0.651. The reviewed inventory corrections therefore did not materially
change the rainfall association.

## Integrity sensitivity

The case-integrity audit flagged 60 case-days (4.13%) as logical violations or
possible contamination, including 13 dates after article publication. The audit
is diagnostic and changed no inventory or release record.

Removing only the 13 violations, or all 60 excludable case-days together with
their matched controls, left every R1/R3/R5/R7 all-years cutpoint unchanged.
AUC shifts ranged from +0.0015 to +0.0042. The complete findings, exclusion list
and sensitivity output are checksummed members of the v0.9 release.

## Verification and next gate

All release digests and bundle locks pass strict verification, and mutable
rainfall outputs match v0.9. The linked inventory remains pending fresh locked
validation, so neither inventory v0.8 nor rainfall v0.9 is promoted.

Next, rerun external validation against the exact v0.8 inventory candidate,
then draw and score a fresh independent validation sample before any promotion.
