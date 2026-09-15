# How to fill `secondary_precision_LABEL_HERE.csv`

154 rows. Expect 2–3 hours. Every row makes one claim, and you are deciding
whether the article supports it:

> **A landslide happened in *this district* on *this date*.**

That is the whole question. Not how many landslides, not how serious — just
whether that claim is true, according to that article.

---

## Why this pack exists

The pipeline reports one event per article. A lot of articles report more than
one, so a new extractor pulls **additional** district-days out of the extra
sentences. It currently finds 154 that the inventory does not already have.

Everything measured so far says those 154 are good, and I do not believe it. The
measurement was made against the 47 articles the extractor's rules were written
from, so it mostly proves the rules match my own reading. When I read a random
handful of the 154 by hand, roughly **four in ten** looked right.

So this pack is the real test. If precision comes back high, the recovered
district-days go into a new inventory release. If it comes back around 40%, they
do not, and the extractor either gets rebuilt or gets abandoned. **A "no" answer
here is a completely fine outcome** — it is cheaper to find out now than after
these records are in a published dataset.

Please do not try to be generous. A wrong record here becomes a landslide that
never happened, in a dataset about rainfall thresholds, where nothing downstream
can tell it from a real one.

---

## Before you start

Open two files side by side:

| File | What it is |
|---|---|
| `data/outputs/secondary_precision_LABEL_HERE.csv` | what you fill in |
| `data/outputs/secondary_precision_reading_pack.csv` | the full article text, same `row_id` order |

Row IDs run `sec-0001` to `sec-0154`. You never need to open a URL.

**Do not open** `secondary_precision_strata.csv`. It records how confident the
extractor was and why, and knowing that would steer your answer.

---

## What each row gives you

| Column | Meaning |
|---|---|
| `claimed_district` | the district the extractor says had a landslide |
| `claimed_date` | the date it says that landslide happened |
| `article_district` / `article_date` | what the pipeline recorded as the article's *main* event — context only, not part of the claim |
| `evidence_sentence` | the one sentence the claim was built from |

Start from `evidence_sentence`, then read enough of the article around it to
judge. The sentence is what the machine saw; the article is the truth.

---

## The two columns you fill

### `failure_really_happened_there` — `yes` / `no` / `unclear`

Did a landslide (or debris flow, mudslide, rockfall) actually occur **in
`claimed_district`**, according to this article?

Say **`no`** when the district is named for some other reason. These are the
failure modes I already know about, and there are probably others:

| The district is… | Example |
|---|---|
| where a victim was **from** | "Panna Shahi **of** Hima RM, Jumla, was rescued injured" — she was rescued elsewhere |
| the **dateline** — where the story was filed | "Surkhet, April 7" on a Dailekh event |
| part of a **road's name** | "the Jumla road section", "the Hetauda–Kathmandu highway" |
| where traffic was **coming from or going to** | "vehicles coming from Kathmandu were halted" |
| where casualties were **taken** | "sent to the district hospital, Jajarkot" |
| one of a **list of districts** in a national tally | "48 districts worst affected by this monsoon" |
| somewhere a **team went to assess damage** | "a team went to Taplejung, Panchthar and Sankhuwasabha" |
| only a **flood**, not a landslide | "blocked by the flood of Baisakh 12" |
| a road being **reopened**, not blocked | "fully restored from 7:45 this morning" |

Say **`yes`** when the article really does place a failure in that district —
usually by naming a municipality, ward or settlement inside it.

Use **`unclear`** when you genuinely cannot tell, and say why in `notes`. It is
excluded from scoring, so it is a real answer, not a way to skip a hard row.

### `date_is_right` — `yes` / `no` / `unclear`

Only meaningful when the first column is `yes`. Leave it blank when the first
answer is `no`.

Did that landslide happen on `claimed_date`? Dates come from phrases like
"Tuesday", "last night", "on June 14", "वैशाख १२ गते", resolved against the
publication date, so they can be off by a day or land in the wrong year
entirely.

**The case that matters most.** If the claimed district is the *same* as
`article_district`, the claim is that the article reports a **second, separate**
landslide there on a different day. Very often it is really the *same* landslide
described again — a follow-up death toll, a road still blocked. If it is the same
event as `article_date`, that is `date_is_right = no`, and please write "same
event" in `notes`. Those rows are the ones I most expect to be wrong.

---

## Worked examples

| Evidence sentence | claimed | happened there? | date right? | why |
|---|---|---|---|---|
| "कान्तिलोकपथ अन्तर्गत ललितपुरको भट्टेडाँडामा आज बिहान पहिरो जाँदा" | Lalitpur | `yes` | `yes` | a named place inside Lalitpur, dated this morning |
| "मनाङको चामे गाउँपालिकास्थित कोत्रेमा गएको पहिराको कारण" | Manang | `yes` | `yes` | Chame RM is in Manang |
| "जुम्ला सडकको कालिकोट खण्ड पनि पहिरोले अवरुद्ध" | Jumla | `no` | *(blank)* | "Jumla road" is the road's name; the failure is in Kalikot |
| "हिमा गाउँपालिका जुम्लाकी पन्ना शाहीलाई घाइते अवस्थामा उद्धार" | Jumla | `no` | *(blank)* | Jumla is where she was from |
| "The landslide has affected locals in Tatopani and Bahrabise Municipality." | Sindhupalchok (same as article) | `yes` | `no` | real, but it is the article's own landslide — note "same event" |
| "९ असार २०७४ को राति इच्छाकामना गाउँपालिका–६ कालिखोलामा पहिरो" | Chitwan | `yes` | `no` | the text says 2074 BS (2017); the claimed date is 2024 |

---

## When you are done

Save as **`secondary_precision_COMPLETED.csv`** in the same folder, leaving the
original untouched.

- Do not reorder, rename or delete rows or columns — `row_id` order is how the
  file joins back to the records.
- Save as CSV UTF-8 so the Devanagari survives. A byte-order mark is fine.

I will validate structure and vocabulary before scoring, and tell you what I find
either way.

**If you would rather not spend three hours on this**, say so and I will treat
the extractor as unproven and leave the recovered records out of the inventory.
That is a legitimate outcome: the v0.6.0 analysis stands on its own, and this
work is an addition to it, not a correction of it.
