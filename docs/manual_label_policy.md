# Manual Label Policy

This document records the labeling rules that should stay stable across manual verification rounds. The purpose is to separate extractor defects from policy or annotation choices.

## Core Principle

Label the specific event described by the article, not the victim's home location, rescue origin, publisher dateline, or later administrative commentary.

## Class Rules

- `Class 1`: A specific Nepal event with confirmed human deaths, injuries, or missing persons.
- `Class 2`: A specific Nepal event without direct human casualty, or a follow-up / cumulative article that still clearly refers to a concrete event.
- `Class 3`: Not a Nepal event row for the inventory. This includes out-of-country incidents, nationwide or province-wide roundups, political response pieces, relief-only statements, and context-only summaries.

## District And Municipality Rules

- Use the event location, not the home district or home municipality of the victim.
- If the article names a specific failure point or event site, prefer that site over other locations mentioned later.
- For road-obstruction articles:
  - fill municipality when one clear obstruction point is identified and mapped to a municipality.
  - leave municipality blank when the article spans multiple obstruction points or multiple municipalities without one dominant event site.
- If the manual value is district-like rather than municipality-like, treat that as an annotation issue rather than an extraction bug.

## Date Rules

- Prefer the event date, not the publication date, when the event date is explicitly stated or can be cleanly derived from relative wording.
- Same-day wording such as `today`, `आज`, `this morning`, `today morning`, or an explicit dateline like `June 10` should anchor the event date to that article date.
- For relative wording such as `last night`, `गएराति`, `Friday night`, or `Saturday afternoon`, backshift from the article's dated lead or publish date only when the reference is clear.
- In follow-up or recovery articles, use the original event date only when the article states it explicitly or ties it unambiguously to a relative weekday.

## Deaths Rules

- Count only confirmed human deaths for the event described by the article.
- Use blank rather than `0` in manual labels when the row is not a death event or when the article is not being treated as a concrete casualty event.
- Animal deaths, livestock loss, or property damage do not make a row `Class 1`.

## Trigger Rules

- `rainfall`: Use only when rain is explicitly tied to the landslide or road blockage.
- `anthropogenic`: Use for excavation, soil digging, road expansion, construction, or similar human activity that directly caused the collapse.
- `unknown`: Use when the article describes the landslide but does not clearly attribute the cause to rainfall, earthquake, or human activity.
- Out-of-country or class-3 rows may still carry a trigger in the manual file, but trigger disagreement on excluded rows should be treated as low priority.

## Follow-Up And Recovery Rules

- Relief, recovery, mitigation, compensation, inspection, and resettlement pieces are usually `Class 2` unless the article itself is functioning as a clear specific casualty report.
- Keep original event fields in follow-up rows only when the article clearly states them.

## Roundup Rules

- District-wide or municipality-wide articles covering multiple separate incidents may stay `Class 2`.
- Province-wide, nationwide, or cumulative disaster summary articles should be `Class 3`.

## Policy-Review Workflow

For any remaining disagreement:

1. Decide whether the article is describing one specific event or a roundup/follow-up.
2. Identify the event location, not the victim home location.
3. Decide whether the municipality is explicit, inferable from a single event site, or too ambiguous to fill.
4. Decide whether the article gives an event date or only a publication / update date.
5. Mark the disagreement as one of:
   - `extractor_bug`
   - `manual_label_issue`
   - `policy_ambiguous_but_accept_manual`
   - `policy_ambiguous_but_accept_model`
## Reviewer Override

- If an article has been re-read manually and the reviewer decides to keep the CSV label unchanged, the reviewed CSV is the source of truth for scoring.
- Policy notes are guidance for consistency and future review, but they do not override a deliberate manual verification decision unless the labeling policy is explicitly revised.
