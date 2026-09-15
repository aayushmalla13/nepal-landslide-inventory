# Spot-checking my first pass on the secondary-extraction precision pack

I labelled all 154 rows. **You check 30 of them.** If we agree, the number
stands; if we don't, it doesn't, and the whole pack needs a human pass.

Expect 30–40 minutes.

## Why a spot-check rather than trusting my pass

I wrote the extractor's rules. Labelling its output is marking my own work, and
the bias runs one way: I already know the nine trap families I built it to
avoid, so I am primed to see them — and primed to forgive anything the rules
were designed to accept. **A high precision result from me is not evidence.**

The result was not high, which is the one thing that makes my pass worth
anything. But you should still check, because the errors that matter are the
ones I was blind to, and I cannot sample my own blind spots.

## Files

| File | What it is |
|---|---|
| `secondary_precision_SPOTCHECK.csv` | 30 rows, blank — what you fill in |
| `secondary_precision_SPOTCHECK_reading_pack.csv` | the full article text, same row order |

**Do not open** `secondary_precision_MODELPASS.csv` or
`..._SPOTCHECK_modelkey.csv` until you are finished. Both contain my answers.
Reading them first turns your labels into agreement with me rather than a check
on me.

The 30 are deliberately **half rows I called `yes` and half I called `no`**, so
you can catch me in both directions — being too generous and too harsh. That is
not a random sample of the 154, so the agreement rate is not itself the
precision; it is a test of whether my precision figure can be believed.

## The question

For each row, exactly one claim:

> **A landslide happened in *claimed_district* on *claimed_date*.**

- `failure_really_happened_there` — `yes` / `no` / `unclear`
- `date_is_right` — `yes` / `no` / `unclear`, and only when the first is `yes`.
  Leave blank otherwise.

Start from `evidence_sentence`; read enough of the article around it to judge.
`article_district` / `article_date` are the pipeline's record of the article's
*main* event — context, not part of the claim.

## What I found, so you know the shapes to look for

Of the 154: **103 district-correct (68%)**, and **76 both district and date
correct (49%)**. Half the claims are wrong. The wrong ones fall into clear
families:

| Why the district was wrong | Example |
|---|---|
| the victim's home district | "Panna Shahi **of** Hima RM, Jumla" — rescued from a landslide in Kalikot |
| the dateline | `BAITADI, July 4:` on a Bajhang landslide |
| a road, power line or office name | "Kusma–Baglung 33kV line"; "Road Division Office Jumla" |
| travel origin or destination | a jeep that came *from* Arghakhanchi; traffic turned back at Nagdhunga |
| a municipality name that exists twice | Tripurasundari RM is in both Dhading and Sindhupalchok |
| not a landslide at all | a house **fire** near Galeshwar; a tunnel collapse |
| a statement or roundup | a minister on crisis districts; a fiscal-year toll |

And one date family worth its own line: **ten rows are the same Araniko Highway
blockage** reported in the daily police bulletin on ten different days. The
landslide is real and in Sindhupalchok; it did not happen ten times.

If you disagree with me on any of these, say so plainly in `notes` — that is the
most useful thing you can write.

## When you are done

Save as **`secondary_precision_SPOTCHECK_COMPLETED.csv`** in the same folder.
Don't reorder or rename rows or columns; save as CSV UTF-8.

I will score agreement against my pass and report it either way, including the
rows where you overruled me.

## What each outcome means

- **We agree on ~27+ of 30** — my pass is usable. Precision is ~50–68%, the
  extractor adds roughly 5–7% to the case set, and the decision is whether that
  is worth a release.
- **We disagree on more than a few** — my pass is not usable and the 154 need a
  human labelling in full, or the extractor is abandoned. Either is a fine
  outcome; it costs nothing already published.
