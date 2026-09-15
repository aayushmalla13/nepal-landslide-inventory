# What is blocked on you, in priority order

**Date:** 2026-09-03

Five items. Only the first two need real time; the rest are minutes or a
credential. Everything else in the project is either done or unblocked.

---

## 1. Label locked test set v7 — 395 rows

**Unblocks:** a new inventory release, and any reportable extraction-accuracy
number in the manuscript.

**Why it is needed.** The gazetteer rebuild and the three district-evidence
corrections are classifier changes. `docs/FINAL_RELEASE.md` states the rule:
*"Any classifier change after this release requires a new locked test version."*
Locked v6 measured the previous extractor, so its numbers can no longer be
quoted for the current one. Until v7 is labelled, the project has a better
extractor with no measured accuracy — which is exactly the situation the rule
exists to prevent.

**Files.** Two, side by side. You never need to open a URL:

| File | What it is |
|---|---|
| `data/outputs/locked_test_set_v7_LABEL_HERE.csv` | the only file you edit |
| `data/outputs/locked_test_set_v7_reading_pack.csv` | the stored article text, keyed by the same `row_id` |

`data/outputs/locked_test_set_v7_predictions.csv` exists. **Do not open it.**
The whole value of a locked set is that it is labelled blind.

**Do not touch** `row_id`, `url`, `source`, `year`, `route_lang`, `title` or
`snippet` — the scoring stage verifies they still match the blank reference and
will refuse the file if they changed. Excel's UTF-8 byte-order mark is accepted.

### Columns to fill

Work in this order and stop early wherever the answer makes the rest moot.

| Column | Allowed values | Note |
|---|---|---|
| `is_landslide_event_true` | `yes` `no` `unclear` | a landslide, debris flow, rockfall or slope failure that actually happened |
| `in_nepal_true` | `yes` `no` `unclear` | |
| `hazard_type_true` | `landslide` `debris_flow` `rockfall` `avalanche` `flood` `other_hazard` `not_a_hazard` `unclear` | |
| `event_granularity_true` | `single` `multi` `roundup` `not_applicable` `unclear` | `roundup` = province-wide, nationwide or cumulative summary |
| `article_role_true` | `first_report` `follow_up` `retrospective` `forecast_or_risk` `metaphor_or_nonevent` `unclear` | "Nepse falls in a landslide of 108 points" is `metaphor_or_nonevent` |
| `district_true` | a district name, or blank | **the event location** — see below |
| `municipality_true` | a local-unit name, or blank | blank when the article spans several sites |
| `date_true` | `YYYY-MM-DD`, or blank | the **event** date, not the publication date |
| `deaths_true` | an integer, or blank | blank, never `0`, when it is not a death event |
| `trigger_true` | `rainfall` `anthropogenic` `earthquake` `unknown` | |
| `annotator` | your initials | |
| `notes` | free text | anything you found ambiguous |

If `is_landslide_event_true` is `no`, fill `hazard_type_true` (usually
`not_a_hazard`) and `article_role_true`, then leave the event fields blank and
move on. A large share of the 395 rows are like this and take a few seconds
each.

### The rule that matters most

`docs/manual_label_policy.md` already says it, and it is exactly what the three
code fixes now implement:

> Label the specific event described by the article, not the victim's home
> location, rescue origin, publisher dateline, or later administrative
> commentary.

Three concrete traps, all of which the pipeline used to fall into:

* **Dateline.** `"SURKHET, Aug 30: … five houses … in Kalikot district"` is a
  **Kalikot** event. The dateline is the bureau that filed it.
* **Home address.** `"The deceased has been identified as Namrata Karki of
  Chandrpur Municipality-1, Rautahat"` in a story about a landslide at
  Gosainkunda is a **Rasuwa** event. Chandrapur is where she lived.
* **Road names.** `"Narayangadh–Muglin road"`, `"दाङ–सल्यान सडक"` — the district
  is where the slope failed, which is often neither endpoint. If the article
  does not say, leave `district_true` blank rather than guessing. A blank is
  honest and is scored as such; a guess silently corrupts the measurement.

**Rough effort:** roughly 3–5 hours if done in one pass. It is genuinely the
long pole. If you want to split it, do it by `row_id` range and keep one
annotator per range so `annotator` stays meaningful.

### When you are done

```bash
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run --stage check_labels  --config config.yaml
PYTHONPATH=src .venv/bin/python -m landslide_inventory.run --stage score_locked  --config config.yaml
```

`check_labels` validates the vocabularies and the protected columns before
anything is scored, so run it first and fix what it reports. Then send me
`locked_test_set_v7_labels_final.csv` and `locked_test_set_v7_score.json` and I
will cut inventory v0.5.0 and update the manuscript's validation section.

---

## 2. Label the place-backfill review pack — 72 rows

**Unblocks:** municipality and ward backfill entering the inventory, and with it
the sub-district analysis.

**File:** `data/outputs/place_backfill_review_pack.csv`. It is self-contained —
every row carries the matched text snippet as evidence, so no reading pack is
needed.

Fill two columns with `correct` / `wrong` / `unclear`:

* `municipality_verdict` — is the proposed municipality the **event** location?
* `ward_verdict` — is the proposed ward attached to that municipality? Leave
  blank where no ward was proposed.

Also fill `reviewer`, and `note` where a row is interesting.

**This pack got much smaller and changed shape since I last mentioned it.** The
improved extractor now resolves municipality directly for 1,612 more articles,
so the backfill's remaining job is mostly wards: 94 municipality fills and 1,714
ward fills, against 750 and 1,682 before. Regenerating the pack against the
current inventory dropped it from 120 rows to 72.

**Rough effort:** 30–45 minutes.

---

## 3. Declarations for the manuscript

Purely informational; I cannot invent any of it. Reply in plain text.

* **Authors** — full names, in order, with affiliations, and ORCIDs if you have
  them.
* **Corresponding author** — name and email.
* **Contributions** — who did what, in CRediT terms if you know them
  (conceptualisation, data curation, methodology, software, writing).
* **Funding** — grant numbers, or "no external funding".
* **Competing interests** — or "none declared".
* **Ethics** — my reading is that no approval is required: the study uses
  published news articles and public rainfall grids, with no human subjects and
  no personal data retained beyond what the publishers printed. Confirm, or tell
  me your institution's position.
* **Data availability** — what may be published. The releases are
  self-contained and hashed, but the news article **full text** is third-party
  copyrighted. My recommendation is to publish URLs, hashes, extracted fields
  and all derived tables, and *not* the article text. Say if you disagree.
* **Target journal** — this drives length, structure and reference style.
  Reasonable fits: *Natural Hazards and Earth System Sciences* (open, EGU,
  strong on regional hazard studies), *Landslides*, *Natural Hazards*,
  *International Journal of Disaster Risk Reduction*. Tell me one and I will
  restructure the draft to its requirements.

There is also one licensing question, from `MISSING_DATA_RECOVERY.md` §6: the
bilingual local-unit source repository carries no LICENSE file. Before the
derived gazetteer is redistributed publicly, either confirm that source's terms
or say the word and I will regenerate the Nepali names from an official
government or OCHA release instead.

---

## 4. A NASA Earthdata account — 5 minutes

**Unblocks:** the IMERG cross-comparison, which answers the manuscript's fourth
limitation: that every result rests on a single rainfall product.

1. Register free at <https://urs.earthdata.nasa.gov>.
2. Authorise the application **"NASA GESDISC DATA ARCHIVE"**.
3. Send me the username, and set the password in a `~/.netrc` entry on whichever
   machine will do the download.

This is the only item in the project that needs a credential I have no path to.
Details in `docs/EXTERNAL_DATA_BLOCKED.md` §2.

---

## 5. Run two downloads from an unrestricted network — mostly unattended

My analysis environment can only reach GitHub and PyPI, which is why the
gazetteer rebuild worked and these did not. Both scripts already exist and are
resumable; you just need to start them somewhere with normal internet.

**a. Extend CHIRPS past 30 June 2026** — recovers 84 otherwise-eligible events
currently excluded for lack of rainfall data.

```bash
PYTHONPATH=src .venv/bin/python scripts/download_chirps_climateserv.py
```

One caveat that matters scientifically: CHIRPS *Final* lags about a month, so
the recent tail is only available as *Prelim*, which uses fewer stations. Do not
let it append silently — I will treat any Prelim days as a labelled sensitivity
analysis, never as part of the primary series. Just tell me which days came from
which product.

**b. Municipality-scale rainfall** — the boundary side is already solved (747
polygons vendored and checksum-pinned). This needs the same downloader pointed
at municipality polygons instead of district polygons, which is roughly ten
times the requests, so expect a long resumable run. Say the word and I will
write that variant; it is a small change to an existing script.

---

## What is *not* blocked on you

For completeness, so you know I am not idle while you label:

* Casualty backfill (921 deaths, 444 missing, 616 injured recoverable) is scoped
  but unbuilt — it needs a labelled development set for negation handling, which
  I can draw and label patterns against without you.
* Terrain and elevation effect modification needs a DEM download (free API key,
  no account approval), which fits in item 5.
* Prospective validation is blocked only by elapsed time.
* Manuscript tables, figures and the v0.3.0 comparison text are current and need
  nothing from you except the declarations in item 3.
