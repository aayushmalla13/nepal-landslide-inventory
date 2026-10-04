# v0.9 final locked validation result

## Decision

**Retain candidate status. Do not promote v0.9.**

The completed 150-row independent probability sample validates against its
locked template and was scored with thresholds frozen before labels existed.
Four of six prespecified promotion checks fail.

| Metric | Weighted estimate | 95% CI | Promotion check |
|---|---:|---:|---:|
| Event-existence precision | 0.811 | 0.752-0.869 | Fail |
| Usable-record precision | 0.370 | 0.293-0.453 | Fail |
| Single-event accuracy | 0.678 | 0.594-0.762 | Fail |
| District accuracy | 0.891 | 0.833-0.944 | Pass |
| Date accuracy | 0.748 | 0.658-0.832 | Fail |
| Event-existence unclear fraction | 0.000 | - | Pass |

Supporting metrics are municipality accuracy 0.921, event-type accuracy 0.781,
hazard-type accuracy 0.869, exact-death accuracy 0.839, and duplicate-merge
accuracy 0.605.

## Interpretation

This is not a narrow threshold miss. The sample contains 26 confirmed
non-events, 38 multi-event failures among confirmed events, and 26 decisive
date errors. A small confirmation audit cannot resolve these deficits.

False events include preparedness plans, forecasts and warnings, aggregate
relief or disaster statistics, political metaphor, foreign hazards,
retrospective reporting, and unrelated articles. Weighted event-existence
precision is especially weak for Deshsanchar and Rajdhani, while single-event
and date failures remain distributed across otherwise stronger sources.

District and municipality extraction are now comparatively strong. The main
remaining problems are upstream event specificity, temporal role, source-
article qualification, and physical-event decomposition.

## Paper readiness

The current candidate is not ready to support claims of a high-precision
national landslide inventory or final rainfall and BIPAD inference. It can
support a transparent methods or error-analysis paper only if the failed
validation is reported as a central limitation and v0.9 is not presented as a
validated final dataset.

For a strong inventory paper, build another candidate using general source-
parser and event-construction fixes, not another round of sample-specific manual
patches. Then draw one new independent probability audit from the rebuilt
inventory using the same frozen decision rule.

## Reproducibility

- Locked manifest: `data/outputs/v09_final_validation_manifest.json`
- Completed labels: `data/outputs/v09_final_validation_COMPLETED.csv`
- Score: `data/outputs/v09_final_validation_score.json`
- Report: `data/outputs/v09_final_validation_report.md`
- Draw script: `scripts/draw_v09_final_validation.py`
- Scorer: `scripts/score_v09_final_validation.py`

The score pins the completed labels and locked manifest by SHA-256. The v0.9
release remains an immutable candidate bundle; its manifest must not be edited
after the audit draw because the draw pins that exact pre-label state.
