# Rising Nepal Manual Policy Pass

Generated during the post-refresh manual review pass.

This note classifies the remaining `rising-nepal` disagreements into policy buckets so we do not keep re-fixing the same rows in code.

## Decisions

### `https://risingnepaldaily.com/news/11980`

- Title: `Two buried to death in landslide in Sankhuwasabha`
- Decision: `manual_label_issue`
- Why:
  - The article explicitly places the event at `Nundhaki of Chainpur Municipality-1 in Sankhuwasabha district`.
  - The manual municipality `Chaudandigadhi Municipality` is the victim's home municipality in Udayapur, not the event site.
  - The article explicitly says the victims were buried while working in road construction and calls it a `dry landslide`, so `anthropogenic` is the stronger trigger than `unknown`.
  - The article lead is dated `Kimathanka, June 1`, so the event date should be `2022-06-01`, not `2022-06-22`.
- Policy rule:
  - Prefer the event site municipality over the victim's home municipality.
  - For road-construction slope failures, `anthropogenic` is acceptable when the article directly links the collapse to the work site.

### `https://risingnepaldaily.com/news/12383`

- Title: `Landslide obstructs North-South Road in Sankhuwasabha`
- Decision: `policy_ambiguous_but_accept_manual`
- Why:
  - The article is a road-obstruction report with no deaths, injuries, or missing persons.
  - Under the current project policy, that is usually `Class 2`.
  - The manual sample marks it as `Class 1`, likely because the road to `Bhotkhola Rural Municipality` is emphasized.
  - The event site is actually described at `Sammatar of Makalu Rural Municipality-3`; `Bhotkhola` is the destination corridor, not the slope-failure point.
- Policy rule:
  - For road-obstruction-only articles, keep `Class 2`.
  - When one municipality is the destination and another is the actual obstruction point, prefer the actual obstruction point, or leave municipality blank if the row is corridor-level.

### `https://risingnepaldaily.com/news/13198`

- Title: `Landslide obstructs Palpa-Butwal road`
- Decision: `manual_label_issue`
- Why:
  - The manual municipality value is `Palpa`, which is district-like, not municipality-like.
  - The article is corridor-level and does not state one municipality cleanly.
  - The manual district is blank, but the article clearly places the row in Palpa district.
- Policy rule:
  - If the manual municipality value is not actually a municipality, treat it as an annotation issue.
  - District may still be filled even when municipality is left blank on corridor-level road rows.

### `https://risingnepaldaily.com/news/13422`

- Title: `Bodies of two missing in Panchthar landslide recovered`
- Decision: `policy_ambiguous_but_accept_manual`
- Why:
  - This is a recovery/follow-up piece, but it clearly states the original event and total deaths.
  - Keeping `Class 1`, event date `2022-07-01`, and deaths `3` is consistent with the project's current follow-up policy.
- Policy rule:
  - Recovery articles may still be `Class 1` when they clearly restate the original casualty event.

### `https://risingnepaldaily.com/news/13509`

- Title: `Landslide obstructs mid-hill highway`
- Decision: `extractor_bug`
- Why:
  - The article is clearly centered on Baglung, including `Baglung-Ghodabandhe section` and `Baglung Municipality`.
  - `Rolpa` appears only as a downstream destination for stranded vehicles.
  - Predicting district `Rolpa` is wrong under the current policy.
- Policy rule:
  - For road articles, destination districts should not override the named event district.

### `https://risingnepaldaily.com/news/60497`

- Title: `26 goats perish after flash flood, mudslide buries shed in Humla`
- Decision: `manual_label_issue`
- Why:
  - The article reports only livestock deaths and property damage, with no human casualty.
  - Under the project policy this is `Class 2`, not `Class 1`.
- Policy rule:
  - Animal loss and property damage alone do not make a row `Class 1`.

### `https://risingnepaldaily.com/news/69074`

- Title: `Four die after being buried in a mudslide in Sarlahi`
- Decision: `policy_ambiguous_but_accept_manual`
- Why:
  - The event location is clearly `Haripurwa Municipality, Sarlahi`.
  - The article explicitly says the victims were collecting soil and that a mound collapsed while digging on the river bank.
  - `anthropogenic` is consistent with the stated mechanism.
- Policy rule:
  - If soil-digging or collection is the immediate cause of collapse, `anthropogenic` is acceptable even when the article uses `mudslide`.

### `https://risingnepaldaily.com/news/69059`

- Title: `Road obstructed at Tuinkhola due to mudslides`
- Decision: `policy_ambiguous_but_accept_manual`
- Why:
  - The article is a standard road-obstruction event in `Ichchhakamana Rural Municipality-5`.
  - It belongs in the inventory as `Class 2` with municipality filled.
  - Remaining disagreement is only that the refreshed sample still lacks the date field display.
- Policy rule:
  - Keep corridor-level road-obstruction rows when one clear failure point is stated.

### `https://risingnepaldaily.com/news/77713`

- Title: `One killed in landslide, excavator operator goes missing`
- Decision: `policy_ambiguous_but_accept_manual`
- Why:
  - This is a specific casualty event during road expansion.
  - `Class 1` is correct, and `anthropogenic` is also defensible because the article ties the event to road expansion work.
- Policy rule:
  - Construction-site landslides during road expansion can be treated as `anthropogenic`.

### Out-of-country and cumulative rows

- `10143`, `13416`, `30871`, `77748`
- Decision: `policy_ambiguous_but_accept_model`
- Why:
  - These are already correctly excluded as `Class 3`.
  - Trigger blanks on excluded rows should be treated as low-priority display issues, not extraction blockers.

## Reviewer decision update

The three rows below were manually re-read against the source articles and were intentionally kept as-is in `manual_verification_sample.csv` by the reviewer. That means they should currently be treated as accepted manual truth for evaluation, even where this policy note identifies a possible alternative interpretation.

- `11980`: reviewed and kept as labeled in the manual CSV
- `13198`: reviewed and kept as labeled in the manual CSV
- `60497`: reviewed and kept as labeled in the manual CSV

When this note and the reviewed CSV disagree, the reviewed CSV should take precedence unless the labeling policy is explicitly revised later.

## Summary

### Reviewed and retained in manual truth

- `11980`: manually re-read and kept as currently labeled in the reviewed CSV
- `13198`: manually re-read and kept as currently labeled in the reviewed CSV
- `60497`: manually re-read and kept as currently labeled in the reviewed CSV

### Policy differences to keep in mind

- `12383`: manual `Class 1` is not aligned with the current road-obstruction policy, but it should remain unchanged unless the labeling policy is revised

### Keep as engineering fixes if we continue tuning

- `13509`: district should stay `Baglung`, not `Rolpa`
- blank date display on some otherwise-correct rows should be checked separately from policy

### Stable rules confirmed by this pass

- Event site beats victim home location.
- Livestock-only rows stay `Class 2`.
- Corridor road rows remain `Class 2` unless there is direct human casualty.
- Out-of-country and nationwide summary rows stay `Class 3`.
