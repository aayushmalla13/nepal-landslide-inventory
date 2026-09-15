# Annotation Rubric — authoritative

**This document supersedes the class definitions in `LABELING_GUIDE.md` and
`docs/manual_label_policy.md`.** Both remain useful for field-level conventions
(district, date, trigger), and those sections are unchanged. Only the *class*
definition moves here.

---

## Why the old rubrics conflicted, and why neither wins

`LABELING_GUIDE.md` said Class 1 requires: a real landslide event, in Nepal, a
**resolvable district**, and a **usable date**. Casualties not required.

`docs/manual_label_policy.md` said Class 1 requires: a specific Nepal event
**with confirmed deaths, injuries or missing persons**.

Annotators labelled against one, the code implements the other, and 793 of the
1,174 Class-1 rows had zero casualties — so a meaningful share of the 0.516
precision figure was definitional disagreement, not model error, and there was
no way to tell how much (review §3.3).

Picking a winner would have been arbitrary. The deeper problem is the one review
§3.2 identifies: **`class` conflates three unrelated questions** —

1. is this a landslide event?
2. did the event have human impact?
3. did *we* successfully extract a district and a date?

Question 3 is about the pipeline, not the world. A perfectly reported fatal
landslide in a district our gazetteer missed becomes "not an event", which makes
Class-1 precision a mixture of two quantities and uninterpretable.

## The resolution: label orthogonal facts, derive the classes

Annotators record **independent facts about the article**. Never a class number.
Each historical class definition then becomes a *view* computed at scoring time,
so both can be reported from the same labels and compared directly.

### Fields the annotator fills

| field | values | question |
|---|---|---|
| `is_landslide_event_true` | yes / no / unclear | Does this article report a landslide that actually happened? |
| `in_nepal_true` | yes / no / unclear | Did it happen inside Nepal? |
| `hazard_type_true` | landslide / debris_flow / rockfall / avalanche / flood / other_hazard / not_a_hazard / unclear | Which hazard? |
| `event_granularity_true` | single / multi / roundup / not_applicable / unclear | One event, several distinct events, or a running total? |
| `article_role_true` | first_report / follow_up / retrospective / forecast_or_risk / metaphor_or_nonevent / unclear | What kind of article is it? |
| `district_true` | district name, or blank | Where did it happen? Blank if the article does not say. |
| `municipality_true` | name, or blank | |
| `date_true` | YYYY-MM-DD, or blank | Event date, not publication date. |
| `deaths_true` | integer, or blank | Deaths **from this event**, not a seasonal total. |
| `trigger_true` | rainfall / earthquake / anthropogenic / unknown | |

**Blank means "the article does not say".** It never means "I could not be
bothered". `unclear` means "the article is ambiguous". These are different and
both are informative.

### Derived class views (computed, never annotated)

```
class_guide  = 1 if is_landslide_event=yes and in_nepal=yes
                    and district_true and date_true
               2 if is_landslide_event=yes and in_nepal=yes
               3 otherwise

class_policy = 1 if is_landslide_event=yes and in_nepal=yes
                    and (deaths_true or injured_true or missing_true)
               2 if is_landslide_event=yes and in_nepal=yes
               3 otherwise

headline     = is_landslide_event=yes and in_nepal=yes
                    and hazard_type in {landslide, debris_flow, rockfall}
                    and event_granularity = single
```

`headline` is the definition the current pipeline implements and the one the
paper should report. The other two exist so the older numbers remain
comparable.

### Locked-set scoring implementation

The scorer applies the definition above literally: only `single` is a positive
granularity. `multi`, `roundup`, and `not_applicable` are negatives, while
`unclear` is excluded. A pipeline prediction is positive only when the article
was retained as Class 1 or Class 2 **and** the inventory's event-typing rules
classify it as a landslide-family event rather than a road-only obstruction,
aggregate report, avalanche, flood, or other hazard.

District and event-date extraction are reported separately among true headline
articles for which the corresponding truth field is available. They are not
prerequisites for event-detection truth. Weighted precision, recall, and F1 use
the locked inclusion weights; uncertainty is estimated by a deterministic
within-stratum weighted bootstrap over the decision-by-language sampling
strata.

---

## The four judgements that actually matter

Everything above reduces to four decisions. Get these right and the rest
follows.

**1. Is it an event, or a statement about events?**
"Landslide kills three in Sindhupalchok" is an event.
"Floods, landslides claim 1000 plus lives in five years" is a running total —
`event_granularity = roundup`. This distinction was worth 4,879 phantom deaths
in the inventory, so it is the single highest-value call you make.

**2. Is it a landslide?**
हिमपहिरो / हिउँपहिरो is an **avalanche**, not a landslide, even though the word
contains पहिरो. बाढी (flood) alone is not a landslide. Mark the hazard honestly;
the pipeline's job is to be corrected by you, not confirmed.

**3. Where did it actually happen?**
The event site — not the dateline the story was filed from (usually Kathmandu),
not where the injured were flown to (usually Kathmandu), not the victim's home
district, not the district administration office. If the article genuinely does
not say, leave it **blank**. A blank is measurable; a guess is not.

**4. Whose deaths are these?**
The count for *this* event. If the article says "three died here; 90 have died
nationwide this monsoon", the answer is 3.

---

## Working rules

- **Label from the article, not from the pipeline.** The predictions live in a
  separate file and are joined only at scoring time. If you find yourself
  wondering what the model said, that is the anchoring effect the blind design
  exists to prevent.
- **`unclear` is a real answer.** An honest `unclear` rate is a finding about
  news reporting. Forced guesses corrupt the estimate silently.
- **Do not skip rows you find hard.** Hard rows are where precision is decided.
  If a row is genuinely undecidable after two minutes, mark every field
  `unclear`, note why, and move on.
- **No event means no event location.** If an article is about an exhibition,
  meeting, institution, or person in a named place but no hazard occurred,
  do not copy that place into district/municipality. Leave event-specific
  location, date, casualty, and trigger fields blank; still fill all five
  controlled judgements and the annotator ID.
- **Never revise a label after seeing a metric.** That is what burned the
  previous 200-row set.

## Rows you will see that are not events

The sample is drawn from *all* collected articles, including ones the pipeline
threw away (review §5.1) — that is the point, since it is the only way to
measure false negatives. So expect share-market metaphors, election coverage,
government relief announcements, foreign landslides, and HTTP error pages. Label
them honestly as non-events; each one is information about a different filter.

---

## Provenance

Decision taken 2026-08-06 while resolving the review's §3.3 finding. The
orthogonal fields were already specified in
`validation/locked_test_set.TRUTH_VOCABULARIES` when the test set was drawn, so
this document describes the design that is already frozen into the sample rather
than changing it.
