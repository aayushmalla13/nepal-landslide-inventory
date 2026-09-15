# Manuscript declarations

**Date:** 2026-09-03 · **Status:** drafted where a defensible default exists;
five fields need Aayush and are marked **`[NEEDS YOU]`**.

Everything below is written to drop into the manuscript once the marked fields
are filled. Journal-specific wording notes are in §8.

---

## 1. Authors and affiliations — **`[NEEDS YOU]`**

Fill this table and I will format it for whichever journal you pick.

| # | Full name (as it should appear) | Affiliation(s) | ORCID | Email |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |

**Corresponding author:** `[NEEDS YOU]` — name and email. Journals increasingly
require an institutional address rather than a personal one; if you only have
`mallaaayush59@gmail.com`, check your target journal's policy before submitting.

If you are the sole author, say so and I will drop the contributions table in §2
in favour of a single sentence.

## 2. Author contributions — **`[NEEDS YOU]`**, but here is the CRediT mapping

CRediT is the taxonomy most journals now require. Based on what exists in this
repository, the work actually done breaks down as follows. Assign initials to
each row; a role can have several people and a person can hold several roles.

| CRediT role | What it covers in this project | Initials |
|---|---|---|
| Conceptualization | the research question: whether media-reported landslides can support a district-day rainfall threshold analysis | |
| Data curation | the news corpus, the gazetteer, the correction history, the release bundles | |
| Methodology | matched district-day case–control design, two exposure definitions, temporal split, conditional models | |
| Software | the pipeline, extractors, analysis code, tests | |
| Formal analysis | threshold estimation, validation, sensitivity analyses | |
| Validation | the locked test sets and manual labelling | |
| Writing – original draft | | |
| Writing – review & editing | | |
| Supervision | | |
| Funding acquisition | | |

**A note you should decide on deliberately.** A substantial share of the
software, analysis and drafting in this repository was produced by an AI
assistant working under your direction. Most journals now have an explicit
policy: AI tools **cannot be listed as authors**, because authorship entails
accountability, but their use **must be disclosed**. The standard place is a
short statement in the methods or acknowledgements. Suggested wording, which you
should edit to match what you consider accurate:

> During the preparation of this work the author(s) used an AI assistant
> (Anthropic Claude and OpenAI ChatGPT/Codex) for software implementation,
> statistical analysis code, labeling assistance, and drafting. The author(s) reviewed and verified the outputs and take full
> responsibility for the content of the publication.

Check your target journal's exact requirement — Springer, Elsevier and Copernicus
all word this slightly differently, and some require it in a named section rather
than the acknowledgements.

## 3. Funding — **`[NEEDS YOU]`**

One of:

- `This research received no external funding.`
- `This work was supported by [funder], grant number [xxx].`

If any part was done as coursework or a thesis, say so — some journals require
that disclosure.

## 4. Competing interests — drafted

> The authors declare no competing interests.

Change this only if an author has a financial or advisory relationship with a
disaster-management agency, insurer, or any organisation with an interest in
landslide thresholds in Nepal.

## 5. Ethics approval — drafted, please confirm

> This study did not involve human participants, human tissue, or personally
> identifiable data collected by the authors, and did not require ethics
> approval. It analyses publicly published news reports and publicly available
> gridded rainfall data.

**My reasoning, so you can check it rather than take it on trust.** The study
uses (a) news articles already published by their outlets, and (b) CHIRPS, a
public satellite rainfall product. No one was recruited, contacted, or observed.
The inventory records event locations and casualty *counts*, not the identities
of the people involved.

One genuine wrinkle worth knowing about: the articles themselves name victims,
and the stored full text therefore contains personal data about deceased people
and their families. Two consequences:

1. It reinforces the §6 recommendation not to redistribute article full text.
2. If your institution operates under GDPR or a similar regime, "publicly
   available" is not automatically a lawful basis for processing. Most
   institutions treat published journalism as fine for research, but this is
   exactly the kind of thing a research office answers in one email. **Please
   confirm with yours rather than relying on my reading.**

## 6. Data and code availability — drafted, please confirm the redistribution line

> The derived landslide inventory, all analysis code, configuration, input
> checksums, tests, joined case–control tables, threshold metrics, conditional
> model estimates, resampled validation results and machine-readable analysis
> reports are contained in the frozen release bundles
> `nepal_landslide_inventory_v0.6.0_v7_20260915` and
> `nepal_landslide_rainfall_v0.8.0_20260915`, each with a recorded bundle
> checksum. Earlier releases are retained unchanged as historical baselines.
> Rainfall data are from UCSB CHIRPS v2.0 Final, obtained through the NASA SERVIR
> ClimateSERV API; the acquisition script is included. The inventory records the
> source URL, retrieval hash and extracted fields for every article. **Full
> article text is not redistributed**, as it remains the copyright of the
> publishing outlets; it can be retrieved from the recorded URLs.

**The decision you are confirming.** Publishing URLs, hashes and every derived
field makes the work reproducible: anyone can re-fetch the articles and re-run
the pipeline. Publishing the article *text* would make it reproducible even for
articles later taken offline — which is a real scientific benefit — but it
republishes third-party copyrighted material at scale, and it republishes
victims' names. My recommendation is URLs-and-hashes only. Say if you want the
alternative and I will write the caveat instead.

A middle option exists if you want it: deposit the full text under restricted
access at a repository such as Zenodo, released to named researchers on request.
That preserves long-term reproducibility without public redistribution. It costs
you one form.

## 7. Gazetteer source licence — **`[NEEDS YOU]`**, one decision

From `MISSING_DATA_RECOVERY.md` §6. The municipality gazetteer is built from two
sources:

| Source | Licence | Status |
|---|---|---|
| `mesaugat/geoJSON-Nepal` (747 polygons) | MIT | fine to redistribute |
| `bibekoli/local-levels-of-nepal-dataset` (bilingual names) | **no LICENSE file** | unresolved |

The facts themselves — the names of Nepal's 753 local units and which district
each sits in — are government administrative facts and not copyrightable in
substance, and the MIT-licensed source independently attests about 94% of them.
So the risk is low. But "low" is not "resolved", and the derived gazetteer ships
inside the release bundle.

Pick one:

- **(a)** You confirm the source's terms, e.g. by asking the repository owner to
  add a licence. Cheapest if they respond.
- **(b)** I regenerate the Nepali names from an official Government of Nepal or
  UN OCHA release instead, and drop the unlicensed source entirely. Costs me a
  few hours and removes the question permanently. **This is what I recommend**,
  because it also makes the gazetteer citable to an authoritative source rather
  than to a GitHub repository, which is better for the paper regardless.
- **(c)** Ship as is and note the provenance. I would not do this.

## 8. Target journal — **`[NEEDS YOU]`**, with a recommendation

This decides length, structure, reference style and how much methodological
detail stays in the main text versus a supplement. My reading of the four
realistic options:

| Journal | Fit | Consider because | Watch out for |
|---|---|---|---|
| **NHESS** (Copernicus) | **best fit** | open access, open peer review, strong regional-hazard tradition, explicitly welcomes methodological transparency and data/code availability — which is this paper's main strength | article processing charge; the open review means your reproducibility story is on public display, which here is an advantage |
| *Landslides* (Springer) | good | the field's flagship; high visibility among landslide specialists | favours physical/geotechnical work; a media-derived inventory may face reviewers who distrust the data source. The honest reporting-bias treatment helps but you should expect that fight |
| *Natural Hazards* (Springer) | good | broad scope, comfortable with statistical and inventory papers | less specialist readership |
| *IJDRR* (Elsevier) | moderate | strong on risk-reduction framing | would want more on operational application, which this paper deliberately declines to claim |

**I recommend NHESS.** The paper's distinctive contribution is not the threshold
number — which the analysis itself now shows is unstable to inventory revision —
it is the *method*: a fully reproducible, versioned, media-derived inventory with
an honest account of reporting bias, a matched design, and a held-out temporal
test. NHESS's open review and data-availability culture rewards exactly that.
The 45.4 → 51.6 mm shift, which would be an awkward paragraph elsewhere, is a
genuinely interesting finding there.

Tell me a journal and I will restructure the draft to its guide for authors,
including reference style and section limits.

---

## What I need back

Copy this block, fill it, send it. Everything else above is already drafted.

```
1. Authors (name | affiliation | ORCID | email), in order:
2. Corresponding author:
3. CRediT initials per role (or "sole author"):
4. AI-use disclosure wording: [accept as drafted / edit as follows]
5. Funding:
6. Ethics: [confirmed as drafted / institution says the following]
7. Data availability: [URLs+hashes only / also deposit full text under restricted access]
8. Gazetteer licence: [a / b / c]
9. Target journal:
```
