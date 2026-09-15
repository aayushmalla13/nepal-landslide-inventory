# Nepal Landslide Inventory Using Automated Web Data Mining

## Results

### Canonical inventory

The v0.4.0 release contains 3,114 canonical landslide-related events
identified from 10,203 collected articles during 7 March 2015–9 August 2026.
The inventory represents 76 of Nepal's 77 districts and 17 news
sources. Of the canonical records, 603 are typed as road-obstruction records;
no records are classified as multi-event aggregates after deduplication.

| Measure | Value |
|---|---:|
| Canonical events | 3,114 |
| Study period | 2015-03-07 to 2026-08-09 |
| Districts represented | 76 |
| Representative sources | 17 |
| Road-obstruction subtype | 603 |
| Multi-event aggregates | 0 |

### Historical e-paper expansion

Historical e-paper recovery contributed 736 issue-level records. Review of
those issues identified 89 event-specific article candidates, of which 88 were
successfully ingested and processed through the standard date normalization,
language routing, extraction, specificity, location, deduplication, and event
typing stages. E-paper issues were treated as evidence containers rather than
events.

### Held-out validation

On the independently drawn, human-labelled locked-v7 test set,
population-weighted article-level headline classification achieved a precision
of 0.626 (95% CI 0.552–0.701), recall of 0.759 (0.682–0.843), and F1 of 0.686
(0.624–0.750).

| Measure | Estimate | 95% CI |
|---|---:|---:|
| Precision | 0.626 | 0.552–0.701 |
| Recall | 0.759 | 0.682–0.843 |
| F1 | 0.686 | 0.624–0.750 |
| District exact accuracy | 0.828 | Not applicable |
| District coverage | 0.922 | Not applicable |
| Event-date exact accuracy | 0.824 | Not applicable |
| Event-date coverage | 0.976 | Not applicable |

Among true headline articles with district truth, exact district accuracy was
0.828 and nonblank district coverage was 0.922 (n=127). Event-date exact
accuracy was 0.824 with 0.976 nonblank coverage (n=83).

Locked v7 was scored once and is now spent. It is the first human-labelled
locked evaluation in the project. The earlier locked-v6 estimates (precision
0.742, recall 0.822) were produced from model-generated labels and are retained
only as a historical diagnostic, not as the paper's primary validation. The
five reviewed post-validation corrections are release-quality controls and do
not alter either frozen evaluation.

To measure annotation reliability, a second independent human annotator labelled
a blind, decision-by-language-stratified subset of 120 locked-v7 articles.
Agreement on the derived headline decision was 0.850 (Cohen's kappa 0.656), and
event-granularity agreement was 0.783 (kappa 0.706). Agreement was lower for
hazard subtype (0.717; kappa 0.544). Where both raters supplied an extraction
value, exact agreement was 0.981 for district (52/53) and 0.941 for event date
(32/34). These are pre-adjudication agreement estimates; the frozen v7 labels
were not revised after comparison.

## Data availability

The reproducible release bundle is
`nepal_landslide_inventory_v0.4.0_v6_20260810`. Its manifest records the file
hashes and bundle lock. The live SQLite working database is stored outside the
Box-synced project directory; the release CSV, validation artifacts, reports,
and manifest remain in the project bundle.

## Limitations

The inventory is a media-derived record and should not be interpreted as a
complete census of all landslides. News coverage varies by location, language,
severity, and year. External government, scientific, road, archive, and
e-paper records are used for discovery and triangulation; they are not silently
merged into the canonical inventory. Full double annotation was not performed;
inter-rater reliability was measured on a stratified 120-row subset.
