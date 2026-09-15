# How to fill `granularity_development_LABEL_HERE.csv`

120 rows. Expect 2–3 hours. The one question being asked is:

> **How many distinct landslide events does this article report?**

Everything below serves that question.

---

## Before you start

Open two files side by side:

| File | What it is |
|---|---|
| `data/outputs/granularity_development_LABEL_HERE.csv` | what you fill in |
| `data/outputs/granularity_development_reading_pack.csv` | the full article text, same `row_id` order |

You never need to open a URL. Row IDs run `gran-0001` to `gran-0120`.

**Do not open** `granularity_development_predictions.csv`. It holds the
pipeline's own answers, and this set exists to judge those answers
independently. Reading it first would turn your labels into agreement with the
machine rather than a check on it.

**Label from the article, in the order below.** Decide whether an event happened
before deciding how many.

---

## The five columns

| Column | Values |
|---|---|
| `is_landslide_event_true` | `yes` / `no` / `unclear` |
| `in_nepal_true` | `yes` / `no` / `unclear` |
| `event_granularity_true` | `single` / `multi` / `roundup` / `not_applicable` / `unclear` |
| `annotator` | your initials |
| `notes` | free text — only where it helps, especially on hard calls |

Fill all three judgement columns on **every** row, including foreign events and
non-events. Blank means "not done"; there is no case here where a blank is the
right answer.

---

## Step 1 — `is_landslide_event_true`

Did a landslide-family failure **actually happen**, as reported by this article?

- `yes` — a landslide, debris flow, mudslide or rockfall occurred.
- `no` — nothing occurred. Risk warnings, forecasts, "settlements at risk",
  prevention or budget stories, and metaphorical use ("a landslide victory").
- `unclear` — the article is genuinely ambiguous about whether a failure occurred.

Anywhere in the world counts as `yes`. Location is the next column's job.

## Step 2 — `in_nepal_true`

Did it happen inside Nepal? `yes` / `no` / `unclear`.

Foreign landslides — India, China, Indonesia, Pakistan — get
`is_landslide_event_true = yes` and `in_nepal_true = no`. Nepali outlets report
a lot of these and they matter as negatives.

## Step 3 — `event_granularity_true` — the actual question

**`not_applicable`** — no failure occurred, so there is nothing to count.
Use this whenever `is_landslide_event_true = no`. A risk warning has no event
count; neither does a metaphor or an unrelated news story.

**`single`** — the article reports **one** landslide occurrence as its subject.
One slope failed, at one place, on one occasion. Casualties can be many; a
single failure that kills eleven people is still `single`.

**`multi`** — the article reports **several distinct failures** as its subject:
different slopes, different places, or clearly separate occasions, each treated
as an event in its own right.

> *"Landslides blocked roads in three districts overnight"*
> *"पहिरोले पृथ्वी राजमार्ग र नारायणघाट–मुग्लिन सडक अवरुद्ध"* (two separate highways)

**`roundup`** — the article's subject is a **running total or an aggregate**
rather than any particular failure. Seasonal or national tallies, ministry
bulletins, "death toll reaches N", province-wide damage summaries.

> *"Monsoon death toll rises to 50"*
> *"बाढीपहिरोबाट यसवर्ष २३९ जनाको मृत्यु"*

The test that separates `multi` from `roundup`: **could you point at the
individual events?** If the article describes several failures you could list
separately, it is `multi`. If it reports a number that sums over an unstated set
of failures, it is `roundup`.

**`unclear`** — use sparingly, and say why in `notes`. It is excluded from
scoring, so it is a real answer, not a way to skip a hard row.

---

## The judgement calls I need you to decide deliberately

These are the cases where the project currently has no consistent convention.
**Pick your reading, write it in `notes` on the first such row you meet, and
apply it consistently for all 120.** Consistency matters more here than which
way you go — an inconsistent convention cannot be learned by any classifier, and
these cases are common enough to move the numbers on their own.

**A. Road corridor blocked by a landslide.**
*"Landslide obstructs Karnali Highway"*, *"पहिरोले कालीगण्डकी सडक अवरुद्ध"*.
The headline is one blockage, but the body often lists several unstable spots
along the same corridor. Two defensible readings:

- *one blockage reported = `single`* (the article's unit of observation is the
  obstruction), or
- *several failures along the corridor = `multi`*.

I am deliberately not telling you which the pipeline does, because I want your
answer, not agreement with it. In v7 this pattern was labelled both ways on
different rows, which is why it is called out here.

**B. Reopening and re-blocking of the same corridor.**
*"Narayangadh–Muglin road reopens after landslide"*, then days later
*"Narayangadh–Muglin section blocked again"*. Is each article one event, or does
the recurrence make it several? Decide once.

**C. Combined flood-and-landslide monsoon disasters.**
*"Floods and landslides kill 33 in Karnali Province"*. These are usually
`roundup` if the subject is a toll, and `multi` if the article walks through
distinct incidents — but say what you did in `notes` the first time.

**D. Foreign multi-fatality events.** Label granularity normally. They are
negatives for other reasons, so the granularity call costs nothing, but a
consistent label keeps the counts clean.

---

## Worked examples

| Article | event? | Nepal? | granularity | why |
|---|---|---|---|---|
| "Landslide buries house in Sindhupalchok, 4 dead" | yes | yes | `single` | one failure, one site |
| "Landslides hit five villages in Doti after night rain" | yes | yes | `multi` | several distinct failures |
| "Monsoon toll reaches 78 dead, 17,000 displaced" | yes | yes | `roundup` | a running total |
| "288 families at high risk of landslide in Nuwakot" | no | yes | `not_applicable` | risk, not an event |
| "At least 21 killed in Darjeeling landslides" | yes | no | `multi` | plural failures, India |
| "Ruling party wins in a landslide" | no | yes | `not_applicable` | metaphor |

---

## When you are done

Save as **`granularity_development_COMPLETED.csv`** in the same folder, next to
the original. Keep the original file untouched.

Two things to preserve, because Excel likes to break both:

- Do not reorder, rename or delete rows or columns. `row_id` order is how the
  file joins to the text and to the pipeline's predictions.
- Save as CSV UTF-8, so the Devanagari survives. (A byte-order mark is fine —
  the last two files had one and it was handled.)

I will validate structure and vocabulary before scoring anything, and I will
tell you what I find either way.

---

# Addendum: the class-1 pack (`granularity_class1_LABEL_HERE.csv`)

100 rows. **Same rules, same five columns, same conventions you already set** —
apply A, B, C and D exactly as you did on the first 120. Consistency between the
two packs is what makes them usable together.

Files: `granularity_class1_LABEL_HERE.csv` and
`granularity_class1_reading_pack.csv`. Save as
**`granularity_class1_COMPLETED.csv`**. Again, do not open
`granularity_class1_predictions.csv`.

**How to be sure you have the right file open.** The two packs are easy to mix
up, so they are now told apart at a glance:

| | rows | row ids |
|---|---:|---|
| first pack (done) | 120 | `gran-0001` … `gran-0120` |
| **class-1 pack (this one)** | **100** | **`c1-0001` … `c1-0100`** |

If the file you are editing says `gran-0001` at the top, it is the finished
first pack — close it and open `granularity_class1_LABEL_HERE.csv` instead.

## What is different, and why it matters

Every article here is one the pipeline **kept in the inventory** as a class-1
event. This is the exact population where locked test v7's false positives live:
v7 showed that 78% of them were articles you would call `multi` or `roundup`, and
the first pack could not reach that population — class 1 is 100% predicted
`single` by construction, so it contained only 17 class-1 rows out of 120.

Two practical consequences for you:

- **`not_applicable` should be rare here.** These articles already passed the
  scope and specificity filters. If you find yourself using it often, that is
  itself a finding worth a note — it would mean non-events are surviving into
  the inventory, which is a different and more serious problem than granularity.
- **Foreign events should be rare too**, for the same reason. Label them
  normally if they appear.

The interesting question on almost every row will be the one that matters:
**is this kept "event" actually one failure, or several?**

## One thing to know about the sample

It is deliberately **enriched**: half the rows were chosen because a multi-event
phrase appears somewhere in the body, which is roughly 18% of the kept
inventory. So expect noticeably more `multi` here than in a random sample of the
inventory — that is by design, so there is enough material to learn from. Each
row carries an inclusion weight in the predictions file, and the scoring undoes
the enrichment, so the reported inventory-level rates stay honest.

Do not let that change how you label any individual row. Judge each article on
its own text, exactly as before.
