# Is the cutpoint a property of Nepali landslides, or of CHIRPS?

Hand-maintained. The measurement comparison it builds on is generated:
`docs/RAINFALL_PRODUCT_COMPARISON.md` (from `scripts/compare_rainfall_products.py`).

---

## The standing limitation

Every result in this study through v0.5.0 rests on one rainfall product, UCSB
CHIRPS v2.0 Final. The manuscript carries this as a limitation because it has to:
a cutpoint estimated on one gridded product may describe the landslides or may
describe the product. A reviewer is entitled to ask which, and until now the
honest answer was that the study could not tell.

NASA IMERG Final Run v07 answers it. It is an independent satellite product
built from different instruments and a different algorithm, and it covers the
same districts and the same days.

## The design, and the trap it avoids

Two things vary between the CHIRPS and IMERG series as they sit on disk:

1. the product, and
2. the period — CHIRPS runs to 2026-07-31; IMERG Final publishes with several
   months' latency and ends at 2025-09-30.

Comparing the IMERG run against the v0.5.0 CHIRPS baseline would vary both at
once. The extra ten months are not a random sample of the record: they contain a
full monsoon and are the period in which the inventory is densest. Any
difference such a comparison produced would be uninterpretable — and it would
look like a product effect.

So the design holds period fixed:

| Run | Product | Period | Role |
| --- | --- | --- | --- |
| v0.5.0 baseline | CHIRPS | 2015-01-01 – 2026-07-31 | published result, unchanged |
| CHIRPS-truncated | CHIRPS | 2015-01-01 – **2025-09-30** | the control |
| IMERG | IMERG | 2015-01-01 – **2025-09-30** | the test |

The comparison that answers the question is **IMERG vs CHIRPS-truncated**. The
v0.5.0 baseline appears only to show what truncation alone costs, which is a
separate and much less interesting quantity.

## The measurement comparison, first

Computed on the 302,302 district-days present in both series (3,926 days x 77
districts, 2015-01-01 to 2025-09-30). Full detail in
`docs/RAINFALL_PRODUCT_COMPARISON.md`.

| Exposure | mean CHIRPS | mean IMERG | IMERG/CHIRPS | Spearman |
| --- | ---: | ---: | ---: | ---: |
| daily | 4.20 | 4.84 | 1.153 | 0.617 |
| R3 | 12.59 | 14.51 | 1.153 | 0.730 |
| R5 | 20.99 | 24.18 | 1.152 | 0.782 |
| R7 | 29.40 | 33.86 | 1.152 | 0.802 |

On exceeding 51.6 mm at R5 the two products agree on 89.7% of district-days,
Cohen's kappa 0.607. CHIRPS calls 15.09% of district-days above the cutpoint,
IMERG 16.01%.

The striking feature is the stability of the ratio: 1.153, 1.153, 1.152, 1.152.
Over Nepal, on these days, IMERG is close to a **uniform 15% wetter** version of
CHIRPS rather than a differently-shaped field. Rank agreement rises with window
length (0.62 daily to 0.80 at R7), which is what one expects when two products
disagree about the timing and placement of individual storms but agree about
accumulated totals — and the analysis depends on accumulations, not on daily
values.

## A prediction, recorded before the threshold was re-estimated

*Written 2026-09-04, after the measurement comparison above and **before**
running the analysis stage on IMERG. Recorded here so that what follows is a
test rather than a description of whatever came out.*

- **If the cutpoint is a scale artefact of the product**, the IMERG cutpoint
  should land near 51.6 x 1.152 = **59.4 mm**, with discrimination (AUC)
  essentially unchanged. That outcome supports the finding and says the
  *number* is product-specific — which is exactly what an operational user
  needs to be told.
- **If discrimination itself is product-dependent**, AUC will differ materially
  between the two runs on the identical period, and the ratio of the two
  cutpoints will depart from 1.152.
- **If neither holds** — a cutpoint near 59 mm but a materially different AUC,
  or an equal AUC but a cutpoint far from 59 mm — then the products differ in
  tail behaviour rather than in scale, and the manuscript must say so rather
  than reporting whichever half is convenient.

<!-- RESULT-BELOW -->

## Result: the prediction was wrong, and wrong in an informative way

Both limbs of the prediction failed.

### 1. Discrimination is not equal. IMERG is materially better.

Because the two runs share one case-control design — the same events, the same
drawn control district-days, the same seed, the same strata, with only the
rainfall values differing — the comparison can be **paired**. Each bootstrap
iteration resamples districts once and scores *both* products on that same
resample, so the design's own sampling variability cancels instead of being
carried into both intervals. Reading two marginal intervals and noting that they
overlap would have been much weaker, and would have missed this.

Paired, district-clustered, 1,000 iterations, seed 20260904
(`scripts/paired_product_auc.py`):

| Exposure | Split | AUC CHIRPS | AUC IMERG | Difference | 95% CI | Excludes 0 |
| --- | --- | ---: | ---: | ---: | :---: | :---: |
| R1 | development | 0.614 | 0.677 | **+0.063** | [+0.042, +0.083] | yes |
| R1 | temporal test | 0.631 | 0.682 | **+0.052** | [+0.024, +0.077] | yes |
| R3 | development | 0.643 | 0.705 | **+0.062** | [+0.044, +0.076] | yes |
| R3 | temporal test | 0.668 | 0.702 | **+0.034** | [+0.015, +0.054] | yes |
| R5 | development | 0.646 | 0.698 | **+0.052** | [+0.036, +0.067] | yes |
| R5 | temporal test | 0.658 | 0.693 | **+0.035** | [+0.018, +0.057] | yes |
| R7 | development | 0.636 | 0.688 | **+0.052** | [+0.035, +0.067] | yes |
| R7 | temporal test | 0.657 | 0.696 | **+0.040** | [+0.021, +0.062] | yes |

Eight comparisons, every one favouring IMERG, every interval excluding zero, in
both the development split and the held-out temporal test. This is not a
borderline result.

The likely reason is physical rather than statistical. CHIRPS is built on
thermal-infrared cloud-top temperature blended with gauge data, and Nepal's
high-altitude gauge network is sparse; IMERG's passive-microwave retrievals see
precipitation structure more directly. Over the Himalayan front, where
orographic rain is exactly the signal a landslide threshold needs, IMERG appears
to carry more of it.

### 2. The cutpoint did not move by the products' scale factor.

Predicted: IMERG cutpoint ≈ CHIRPS x 1.152 at every window. Observed:

| Window | CHIRPS | IMERG | Ratio | Predicted |
| --- | ---: | ---: | ---: | ---: |
| R1 | 15.95 mm | 8.51 mm | 0.53 | 1.15 |
| R3 | 31.65 mm | 28.27 mm | 0.89 | 1.15 |
| R5 | 51.60 mm | 39.07 mm | 0.76 | 1.15 |
| R7 | 75.95 mm | 88.39 mm | 1.16 | 1.15 |

Only R7 lands near the prediction. The others scatter from 0.53 to 1.16 with no
pattern. The two runs also select different windows in development: CHIRPS
selects R5, IMERG selects R3 (28.3 mm).

The two products agree closely in bulk — a stable 1.152 ratio of means at every
window and Spearman 0.78 at R5 — and that bulk agreement simply does not
propagate to the Youden cutpoint. It should not have been expected to: the
cutpoint depends on the joint distribution of case and control exposures in the
neighbourhood of the optimum, not on the mean of the field.

### 3. The finding that matters most: AUC is stable, the cutpoint is not

An unplanned experiment made this sharp. Midway through this work a defect was
found in the control sampler (see below) and fixed; the fix redraws the control
sample while changing nothing else. Under that redraw:

| | before fix | after fix |
| --- | ---: | ---: |
| IMERG R5 AUC (development) | 0.6973 | 0.6981 |
| IMERG R5 **cutpoint** | 62.79 mm | **39.07 mm** |

The same data, the same product, the same period, a different control draw: AUC
moved by 0.0008, the cutpoint by 38%. Discrimination is a stable property of the
rainfall–landslide relationship. The Youden cutpoint is a fragile statistic of a
particular sample, and this is now demonstrated directly rather than argued.

That is the strongest evidence in the study against quoting any single number as
an operational threshold — stronger than the inventory-revision sensitivity
already in the manuscript, because here nothing about the science changed at all.

## What this does and does not settle

**Settled.** The rainfall–landslide association is not an artefact of CHIRPS. It
is present in an independent satellite product built from different instruments,
over the same districts and days, with the same design — and is in fact somewhat
stronger there. The single-product limitation can be retired.

**Not settled, and now better quantified.** The specific value of the cutpoint is
product-dependent and sample-fragile. 51.6 mm is a CHIRPS-specific, sample-specific
figure. Reported alongside it should be the IMERG value at the same window
(39.1 mm at R5) and the fact that neither is stable to a redraw of matched
controls.

**A caveat that cannot be removed from this comparison.** CHIRPS district means
are ClimateSERV's area-weighted server-side mean; IMERG district means here are
unweighted means of 0.1-degree cell centres inside each district. The two runs
therefore differ in aggregation as well as in product, and the AUC gap is an
upper bound on the product effect alone. Bhaktapur (one grid cell) and Kathmandu
(three) have almost no IMERG spatial support and should be caveated in any
per-district reading.

## The control-sampler defect this analysis uncovered

This comparison was designed to hold period fixed by truncating CHIRPS to the
IMERG record. That truncation drops 181 events, all of them after 2025-09-30,
which share no year, no stratum and no candidate day with the 2015–2022
development split. The development controls should have been untouched.

They were not. Only 532 of 3,587 survived, and the development-fitted cutpoint
moved from 51.6 mm to 45.3 mm.

The cause was a single `random.Random(seed)` stream shared across all cases,
shuffling each case's candidate pool in turn: removing any event shifts the
stream and redraws the controls for every case after it. Every sensitivity
analysis that adds or removes events was therefore partly measuring a redrawn
control sample rather than the thing it varied.

Each case now draws from its own stream, keyed by a SHA-256 of the seed and the
case's record id, so its controls depend on that case, its own candidate pool and
the seed, and on nothing else. `tests/test_control_sampling_independence.py`
pins the property.

Two checks confirm the fix:

* On the **full** event list, redrawing every control (682 of 6,164 shared with
  v0.5.0) left the primary cutpoint **identical** at 51.5999 mm and moved the
  temporal-test AUC from 0.670 to 0.675.
* On the **truncated** series, the control run now reproduces the full-record
  development cutpoint **exactly** (51.5999 mm at R5), which is what a
  truncation of only post-2025 days should have done all along.

The second check is what makes the product comparison above interpretable.

## Reproducing this

```bash
PYTHONPATH=src python3 scripts/compare_rainfall_products.py   # measurement comparison
PYTHONPATH=src python3 scripts/run_product_sensitivity.py     # both matched runs
PYTHONPATH=src python3 scripts/paired_product_auc.py          # paired AUC difference
```

Outputs: `data/outputs/rainfall_product_comparison.json`,
`rainfall_product_sensitivity.json`, `rainfall_product_paired_auc.json`, and the
two run directories under `data/sensitivity/product/`. The derived run configs
are generated from `config.yaml` with only the rainfall path, product label and
output directory overridden; `tests/test_product_sensitivity.py` asserts that no
other analysis key differs, so a settings drift cannot be reported as a product
effect.
