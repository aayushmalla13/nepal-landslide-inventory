# Do this next — exact steps

Every command runs from the project folder, in Terminal:

```bash
cd ~/Library/CloudStorage/Box-Box/nepal_landslide_inventory
```

Your `Makefile` handles the virtualenv, so use `make run STAGE=x` rather than
calling Python directly. Total hands-on time is about 90 minutes, plus a few
hours of unattended crawling.

---

## Step 0 — safety net (2 minutes)

Back up the database. `extract` overwrites fields in place and only some of that
is recoverable.

```bash
cp data/raw_sqlite/landslide_inventory.sqlite \
   data/raw_sqlite/landslide_inventory.snapshot_$(date +%Y%m%d)_pre_recollect.sqlite

git status          # should say "working tree clean"
make test           # should say 470 passed
```

If `make test` fails, stop and tell me. Don't collect on a broken tree.

---

## Step 1 — recover the 615 rate-limited articles (~1 hour, unattended)

These are real himalayan-times articles that were never actually downloaded.
The fetcher fix is already in; it just needs a politer crawl rate.

**1a.** Open `config.yaml` and change two numbers under `runtime:`

```yaml
runtime:
  rate_limit_seconds: 3.0    # was 1.0
  retries: 5                 # was 3
```

**1b.** Check where you stand now, so you can compare afterwards:

```bash
make run STAGE=article_quality
```

Note the `http_429` number. It should say **615**.

**1c.** Re-collect. This is the slow one — leave it running:

```bash
make run STAGE=collect
```

**1d.** Check what came back:

```bash
make run STAGE=article_quality
```

**Success looks like:** `http_429` well below 615, ideally near zero.
**If it's still 615:** the site is blocking harder. Raise `rate_limit_seconds`
to 8.0 and try again, or run it overnight.

---

## Step 2 — find the missing archives (~45 minutes, hands-on)

This is the big one. Four sources have almost no history because Google News RSS
never backfills archives.

**2a.** Probe the candidate URLs I've guessed:

```bash
PYTHONPATH=src .venv/bin/python scripts/verify_entry_points.py
```

It prints a line per candidate. `OK` means usable.

**2b.** For anything that failed, find the real URL by hand. Open the site in
your browser, search for a landslide story, click its tag/category link, and
copy that URL. Then check it:

```bash
PYTHONPATH=src .venv/bin/python scripts/verify_entry_points.py \
  --url "https://ekantipur.com/tag/WHATEVER-YOU-FOUND"
```

Do these in order — this is value order, not alphabetical:

| # | site | what's missing | where to look |
|---|---|---|---|
| 1 | ekantipur.com | ~9 years | Nepal's biggest Nepali daily. Find the पहिरो tag. **Biggest single win in the project.** |
| 2 | kathmandupost.com | ~11 years | Biggest English daily. Look for /tag/landslide |
| 3 | onlinekhabar.com | pre-2023 | Trend pages work but stop early — check if /page/30 exists |
| 4 | ratopati.com | pre-2025 | Same question, tag/797 |
| 5 | risingnepaldaily.com | almost all | Smallest. Do last or skip. |

**2c.** For each URL that comes back `USABLE`, the script prints YAML. Paste it
into `config.yaml` under that source's `entry_points`, and **delete that
source's `googlenews` entry** so the archive becomes the primary path.

Before:
```yaml
- slug: ekantipur
  entry_points:
  - kind: googlenews          # DELETE THIS BLOCK
    url: https://news.google.com/rss/search?q=site:ekantipur.com+...
    pagination: rss
```

After:
```yaml
- slug: ekantipur
  entry_points:
  - kind: tag                 # PASTE WHAT THE SCRIPT PRINTED
    url: https://ekantipur.com/tag/whatever-you-found
    pagination: page
```

**2d.** Collect again:

```bash
make run STAGE=collect
```

**If you can only do one site, do eKantipur.**

---

## Step 3 — rebuild the inventory (~10 minutes)

Run these in order. Each depends on the one before.

```bash
make run STAGE=normalize_dates
make run STAGE=lang
make run STAGE=extract              # slowest, ~2 min
make run STAGE=event_specificity
make run STAGE=location_consistency
make run STAGE=filter_scope
make run STAGE=dedup
make run STAGE=event_typing
make run STAGE=export_final
```

Watch two lines:

- `event_typing` prints the headline event count — currently **772**
- `dedup` prints `merge rate en-np` — currently **22.9%**

Your updated dataset is `data/outputs/canonical_events_final.csv`.

---

## Step 4 — did it work? (2 minutes)

```bash
PYTHONPATH=src .venv/bin/python -c "
import sqlite3, collections
c = sqlite3.connect('file:data/raw_sqlite/landslide_inventory.sqlite?mode=ro', uri=True)
print('articles :', c.execute('select count(*) from raw_articles').fetchone()[0], '(was 4453)')
print('events   :', c.execute(\"select count(*) from canonical_events where event_type='landslide' and hazard_type in ('landslide','debris_flow','rockfall')\").fetchone()[0], '(was 772)')
print()
print('events per year:')
for y, n in c.execute(\"select substr(event_date_ad,1,4), count(*) from canonical_events where event_type='landslide' group by 1 order by 1\"):
    print(f'  {y}: {n:4d} ' + '#' * (n // 4))
"
```

**The number that matters is not the total.** It's whether the year curve
flattens. Right now 2024 has **4.5×** the events of 2016. If that ratio drops
toward 2× or below, your temporal analysis becomes defensible. If it stays at
4.5×, the skew is real and belongs in your limitations section — either way you
learn something worth writing down.

---

## Step 5 — free local LLM (~20 minutes, optional)

Only worth doing after the data is fixed.

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b      # ~5 GB, good with Devanagari
ollama serve                # leave this running in its own Terminal tab
```

Then in your normal tab:

```bash
make run STAGE=benchmark_adjudicator
```

It prints two rows — `rules` and `llm` — scored on the same 362 articles you
labelled. **Only switch to the LLM if it wins.** Report both numbers in the
paper either way.

---

## Step 6 — fresh test set (5 minutes + labelling)

Do this **after** Steps 1–3. New articles change the sampling frame, and the v1
set has been scored twice, so it's spent.

Edit `src/landslide_inventory/validation/locked_test_set.py`, line ~62:

```python
DESIGN_VERSION = 'v2'     # was 'v1'
```

Then:

```bash
make run STAGE=locked_test_set
```

That writes a fresh `locked_test_set_v2_labels.csv`. v1 is untouched, so you can
compare. Labelling it is another session — tell me when you're there and I'll
build the v2 spreadsheet.

---

## If something breaks

```bash
# restore the database
cp data/raw_sqlite/landslide_inventory.snapshot_YYYYMMDD_pre_recollect.sqlite \
   data/raw_sqlite/landslide_inventory.sqlite

# undo config changes
git checkout config.yaml
```

Then paste me the error. Don't work around it — a silent workaround is how the
615 error pages got in.

---

## Summary

| step | time | your attention | value |
|---|---|---|---|
| 0 backup | 2 min | yes | insurance |
| 1 recover 429s | ~1 hr | no | ~600 articles |
| **2 find archives** | ~45 min | **yes** | **potentially thousands** |
| 3 rebuild | ~10 min | no | updated dataset |
| 4 check | 2 min | yes | tells you if it worked |
| 5 local LLM | 20 min | no | optional |
| 6 test set v2 | 5 min | later | needed before publishing |

**Step 2 is the one that matters.** Steps 1 and 3 are mostly waiting.
