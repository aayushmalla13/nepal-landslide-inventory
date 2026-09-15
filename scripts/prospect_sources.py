#!/usr/bin/env python3
"""Find NEW Nepali news outlets with archives that actually reach back to 2015.

WHY THIS EXISTS, AND WHY IT REPLACES THE OLD PLAN
-------------------------------------------------
`verify_entry_points.py` assumed the eight configured sources each had an
archive door we simply hadn't found. Probing them on 2026-08-08 showed that is
false for the two that matter most:

    kathmandupost.com/tag/landslide   returns the homepage, even with JavaScript
                                      rendering. There is no tag archive.
    kathmandupost.com/national?page=N the page parameter is ignored; page 60
                                      serves today's stories.
    ekantipur.com/sitemap.xml         404.
    Google News RSS                   contributes ZERO articles. The 16 rows in
                                      discovered_urls are the feed URLs; collect.py
                                      skips method='googlenews' entirely.

So the corpus comes from sitemaps (myrepublica, himalayan-times) and site search
(setopati, ratopati, rising-nepal). And the real hole is not "eKantipur is
missing nine years" — it is this:

    source              15   16   17   18   19   20   21   22   23   24   25   26
    ekantipur            ·    ·    ·    ·    1    1    ·    ·    1    ·   11  397
    kathmandu-post       2    ·    ·    ·    ·    ·    2    ·    ·    ·    ·   84
    online-khabar        ·    ·    ·    ·    ·    ·    ·    ·   49  175   78   75
    ratopati             ·    ·    ·    1    ·    ·    ·    ·    1    1   70  286
    setopati             ·    ·   63   64   85  240  223  150  166  331  153   53
    himalayan-times    140  172  112   78   62  128   29   14   11   33   17    7
    myrepublica         97  119   90  115   82  102   79   79   83  156   10    ·

**Nepali-language coverage barely exists before 2023.** Setopati is the only
Nepali source with depth. Separately, both English workhorses collapse in
2025–26. Adding outlets is therefore not a nice-to-have: a bilingual inventory
whose Nepali half is three years long cannot support the bilingual claim.

WHAT THIS SCRIPT MEASURES
-------------------------
Not "does this URL return 200" — **how far back can we actually get**. A tag page
with 40 links from last month is worthless here; a sitemap index reaching 2014 is
the whole game. So every probe reports the earliest and latest year it can
demonstrate, and candidates are ranked by depth.

Two discovery shapes are checked per domain, in the order they have historically
worked for this project:

1. **Sitemaps** — via robots.txt and the usual paths. This is how myrepublica and
   himalayan-times got their 2015–2024 depth, so a new outlet with a sitemap
   index is close to free: `scrape/discovery.py` already has the machinery.
2. **Search / tag endpoints** — the shapes setopati and ratopati use.

USAGE  (run on a machine that can reach Nepali news sites — not the sandbox)

    PYTHONPATH=src .venv/bin/python scripts/prospect_sources.py
    PYTHONPATH=src .venv/bin/python scripts/prospect_sources.py --only nagarik
    PYTHONPATH=src .venv/bin/python scripts/prospect_sources.py --url https://x.com/sitemap.xml

Paste the output back. Depth is what to look at, not the OK markers.
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
import time
from collections import Counter
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

UA = 'landslide-inventory/0.1.0 (+research; prospecting archive coverage)'

# Candidate outlets, Nepali-language first because that is where the hole is.
#
# `prior` records why each one is here, so a later reader can tell a reasoned
# candidate from a guess. The single strongest prior is nagariknews: it is the
# same publisher as myrepublica, whose sitemap discovery ALREADY WORKS in this
# repo, so an identical sitemap shape would cost almost no new code.
CANDIDATES: list[dict] = [
    # --- Nepali language -----------------------------------------------------
    {'slug': 'nagarik', 'lang': 'np', 'base': 'https://nagariknews.nagariknetwork.com',
     'prior': 'Same publisher as myrepublica, whose sitemap_news discovery already works. Best bet.'},
    {'slug': 'annapurna-post', 'lang': 'np', 'base': 'https://annapurnapost.com',
     'prior': 'Major national daily, print since 2002.'},
    {'slug': 'gorkhapatra', 'lang': 'np', 'base': 'https://gorkhapatraonline.com',
     'prior': 'State daily, oldest paper in Nepal. Sibling of rising-nepal, so shapes may match.'},
    {'slug': 'naya-patrika', 'lang': 'np', 'base': 'https://nayapatrikadaily.com',
     'prior': 'National daily with district correspondents — good for rural landslides.'},
    {'slug': 'baahrakhari', 'lang': 'np', 'base': 'https://baahrakhari.com',
     'prior': 'Digital-native, strong district reporting.'},
    {'slug': 'nepal-press', 'lang': 'np', 'base': 'https://nepalpress.com',
     'prior': 'Digital-native, 2020 onward — may help the 2020-23 band only.'},
    {'slug': 'himalkhabar', 'lang': 'np', 'base': 'https://himalkhabar.com',
     'prior': 'Himal Khabarpatrika; long-form, deep archive, strong on disasters.'},
    {'slug': 'ujyaalo', 'lang': 'np', 'base': 'https://ujyaaloonline.com',
     'prior': 'Radio network with nationwide district stringers.'},
    {'slug': 'deshsanchar', 'lang': 'np', 'base': 'https://deshsanchar.com',
     'prior': 'High-volume portal, heavy district coverage.'},
    {'slug': 'kendrabindu', 'lang': 'np', 'base': 'https://kendrabindu.com',
     'prior': 'Digital-native.'},
    {'slug': 'pahilopost', 'lang': 'np', 'base': 'https://pahilopost.com',
     'prior': 'Digital-native, 2015 onward — spans the whole study period.'},
    {'slug': 'lokantar', 'lang': 'np', 'base': 'https://lokaantar.com',
     'prior': 'Digital-native, 2015 onward.'},
    {'slug': 'rajdhani', 'lang': 'np', 'base': 'https://rajdhanidaily.com',
     'prior': 'National daily.'},
    # --- English -------------------------------------------------------------
    {'slug': 'nepali-times', 'lang': 'en', 'base': 'https://nepalitimes.com',
     'prior': 'Weekly with an unusually complete online archive back to the 1990s.'},
    {'slug': 'khabarhub-en', 'lang': 'en', 'base': 'https://english.khabarhub.com',
     'prior': 'Bilingual outlet; the Nepali side is a separate candidate.'},
    {'slug': 'onlinekhabar-en', 'lang': 'en', 'base': 'https://english.onlinekhabar.com',
     'prior': 'English arm of a source already configured — same CMS, so cheap.'},
    {'slug': 'setopati-en', 'lang': 'en', 'base': 'https://en.setopati.com',
     'prior': 'English arm of our deepest Nepali source. Also a natural en-np dedup test.'},
    {'slug': 'nepalnews', 'lang': 'en', 'base': 'https://nepalnews.com',
     'prior': 'One of the oldest Nepali news sites in English.'},
]

# Sitemap locations worth trying when robots.txt does not advertise one.
SITEMAP_PATHS = (
    '/sitemap.xml',
    '/sitemap_index.xml',
    '/sitemap-index.xml',
    '/sitemap.xml.gz',
    '/wp-sitemap.xml',            # WordPress 5.5+
    '/sitemap_index.xml.gz',
    '/news-sitemap.xml',
    '/sitemap/sitemap-index.xml',
)

# Search / tag shapes, {q} replaced with a landslide keyword in the right script.
SEARCH_SHAPES = (
    '/search?q={q}',
    '/search?query={q}',
    '/search/{q}',
    '/?s={q}',                    # WordPress default
    '/tag/{q}',
    '/trend/{q}',
)

KEYWORD = {'np': 'पहिरो', 'en': 'landslide'}

YEAR_IN_URL = re.compile(r'/(20[01][0-9]|202[0-9])(?:[/\-]|$)')
LASTMOD_YEAR = re.compile(r'<lastmod>\s*(20\d{2})')
LOC = re.compile(r'<loc>\s*([^<\s]+)\s*</loc>')
ARTICLE_LINK = re.compile(r'href="([^"]*(?:/20\d{2}/|/news/|/story/|/\d{6,})[^"]*)"')


def _maybe_gunzip(url: str, body: bytes) -> bytes:
    if url.endswith('.gz') or body[:2] == b'\x1f\x8b':
        try:
            return gzip.decompress(body)
        except OSError:
            pass                      # truncated gzip: fall back to raw bytes
    return body


def fetch(url: str, timeout: int = 25) -> tuple[int | None, bytes, str]:
    """Return (status, body, note). **Never raises** — a dead candidate is data.

    The except clauses are deliberately a bare ``Exception``. An earlier version
    listed the exceptions it expected and was killed mid-run by one it hadn't:

        http.client.IncompleteRead: IncompleteRead(3259 bytes read, 1 more expected)

    which is neither an OSError nor a ValueError, and which several Nepali
    outlets produce routinely because they send a Content-Length that overshoots
    the body by a byte. Nineteen candidates probed over one connection is exactly
    the situation where one ill-behaved server must not end the run — the same
    reasoning as the per-source try/except in ``scrape/collect.py``.

    ``IncompleteRead`` is also *recoverable*: the bytes already read are on
    ``exc.partial``, and for a sitemap a truncated tail still proves the archive
    depth we are measuring. So we use it rather than discarding it.
    """

    try:
        request = Request(url, headers={'User-Agent': UA})
        with urlopen(request, timeout=timeout) as response:
            return int(response.status), _maybe_gunzip(url, response.read()), ''
    except HTTPError as exc:
        return int(exc.code), b'', 'http error'
    except Exception as exc:  # noqa: BLE001 - see docstring
        partial = getattr(exc, 'partial', b'')
        if partial:
            return 200, _maybe_gunzip(url, partial), f'partial ({len(partial)} bytes)'
        return None, b'', f'unreachable: {type(exc).__name__}'


# Nepal's news sites went online in the mid-2000s and this study covers 2015-2026.
# A "year" outside this band is a slug or an id that happens to look like one --
# kendrabindu reported "2000-2000" from exactly that.
PLAUSIBLE_YEARS = range(2005, 2027)


def years_in(text: str, *, use_lastmod: bool = True) -> Counter:
    """Years this blob can demonstrate, from URL paths and optionally <lastmod>.

    ``use_lastmod`` is the important switch, and the two cases are genuinely
    different:

    - In a **sitemap index**, ``<lastmod>`` is when each *child file* was last
      regenerated. On a live site that is always "recently", so counting it
      invents depth that does not exist. Pass ``use_lastmod=False``.
    - In a **child urlset**, ``<lastmod>`` is per-article and is the closest
      thing to a publication date the sitemap offers. It must be counted.

    That distinction is not academic. Most Nepali outlets use opaque article
    URLs (``/?p=12345``, ``/news/98765``) with no date in them at all, so on the
    2026-08-08 run, discarding ``<lastmod>`` in child files left nine of eleven
    reachable candidates reporting "no dated URLs" -- i.e. the script could not
    answer the only question it exists to answer.
    """

    counts: Counter = Counter()
    for match in YEAR_IN_URL.finditer(text):
        year = int(match.group(1))
        if year in PLAUSIBLE_YEARS:
            counts[year] += 1
    if use_lastmod:
        for match in LASTMOD_YEAR.finditer(text):
            year = int(match.group(1))
            if year in PLAUSIBLE_YEARS:
                counts[year] += 1
    return counts


def depth_label(counts: Counter) -> str:
    """Summarise reachable depth. This is the number that decides everything."""

    if not counts:
        return 'no dated URLs'
    years = sorted(y for y in counts if 2000 <= y <= 2026)
    if not years:
        return 'no plausible years'
    return f'{years[0]}-{years[-1]} ({len(years)} yrs)'


# CHOOSING WHICH CHILD OF A SITEMAP INDEX TO FOLLOW
#
# The first version of this script followed ``sorted(locs)[0]`` -- the
# alphabetically first child. On WordPress that is essentially never a post
# sitemap, and the 2026-08-08 run reported depths that were pure artefact:
#
#   deshsanchar   "2001-2026"  <- author-sitemap.xml     (author profile dates)
#   rajdhani      "2000-2026"  <- attachment-sitemap.xml (image upload dates)
#   lokaantar     "2018-2026"  <- sitemap-categories.xml (category pages)
#   nepalpress    "2020-2026"  <- wp-sitemap-posts-npauthor-1.xml
#
# An author page's lastmod says nothing about whether the outlet's 2015 articles
# are reachable, which is the only question being asked. Worse, it reported
# reassuring depth for sites that may have none -- the exact failure mode this
# project keeps hitting, where a plausible number hides a missing check.
#
# So: exclude the taxonomy sitemaps explicitly, prefer children that name posts
# or carry a year, and sample the oldest, middle and newest rather than one.
NON_ARTICLE_SITEMAP = re.compile(
    r'(author|attachment|category|categories|tag|taxonom|/page|-page|user'
    r'|image|video|web-?stor|amp)', re.IGNORECASE)
ARTICLE_SITEMAP = re.compile(r'(post|article|news|stor(y|ies)|20\d{2})', re.IGNORECASE)


def choose_children(locs: list[str], limit: int = 3) -> list[str]:
    """Pick child sitemaps most likely to contain ARTICLES, oldest first.

    Returns up to ``limit`` spread across the range (oldest, middle, newest) so
    a single unlucky pick cannot decide the verdict.
    """

    articleish = [u for u in locs
                  if not NON_ARTICLE_SITEMAP.search(u) and ARTICLE_SITEMAP.search(u)]
    if not articleish:
        articleish = [u for u in locs if not NON_ARTICLE_SITEMAP.search(u)]
    if not articleish:
        return []

    # Sort by any year-month embedded in the name, else lexically. WordPress
    # names monthly post sitemaps like sitemap-posts-post-2015-07.xml, so this
    # usually is a true chronological sort.
    def key(url: str) -> tuple:
        years = [int(y) for y in re.findall(r'20\d{2}', url)]
        if years:
            return (min(years), 0, url)
        # Paginated news sitemaps (annapurnapost, lokaantar) use
        # sitemap-news.xml?p=N with no year anywhere. Sort those NUMERICALLY --
        # lexically "?p=999" sorts before "?p=1000", which would make the
        # "newest" sample an arbitrary middle page. Higher p is normally older,
        # so a numeric spread is what actually probes the archive's far end.
        page = re.search(r'[?&]p(?:age)?=(\d+)', url)
        return (9999, int(page.group(1)) if page else 0, url)

    ordered = sorted(set(articleish), key=key)
    if len(ordered) <= limit:
        return ordered
    middle = ordered[len(ordered) // 2]
    return [ordered[0], middle, ordered[-1]][:limit]


def probe_sitemaps(base: str, delay: float) -> list[dict]:
    """Look for a sitemap, and follow one level of index -> child."""

    found: list[dict] = []
    advertised: list[str] = []

    status, body, _ = fetch(base.rstrip('/') + '/robots.txt')
    if status == 200:
        for line in body.decode('utf-8', 'replace').splitlines():
            if line.lower().startswith('sitemap:'):
                advertised.append(line.split(':', 1)[1].strip())
    time.sleep(delay)

    seen: set[str] = set()
    for candidate in advertised + [base.rstrip('/') + p for p in SITEMAP_PATHS]:
        if candidate in seen:
            continue
        seen.add(candidate)
        status, body, note = fetch(candidate)
        time.sleep(delay)
        if status != 200 or not body:
            continue
        text = body.decode('utf-8', 'replace')
        if '<' not in text:
            continue
        locs = LOC.findall(text)
        is_index = '<sitemapindex' in text

        # Depth is measured ONLY from article URLs. The index's own text is not
        # counted: its <lastmod> values are when each child was regenerated,
        # which for a live site is always "recently" and tells us nothing.
        counts: Counter = Counter()
        child_note = ''
        if is_index and locs:
            children = choose_children(locs)
            sampled: list[str] = []
            for child in children:
                c_status, c_body, _ = fetch(child)
                time.sleep(delay)
                if c_status == 200 and c_body:
                    child_text = c_body.decode('utf-8', 'replace')
                    # A child urlset: count BOTH the article URLs and their
                    # per-article <lastmod>. See years_in() for why lastmod is
                    # counted here but not at index level.
                    counts += years_in(child_text, use_lastmod=True)
                    # The child's own name too -- WordPress encodes the month
                    # there (sitemap-posts-post-2015-07.xml).
                    counts += years_in(child, use_lastmod=False)
                    sampled.append(child.rsplit('/', 1)[-1])
            skipped = len(locs) - len(children)
            child_note = ('  [sampled ' + ', '.join(sampled) + f'; {skipped} more children]'
                          if sampled else '  [no article-like children found]')
        else:
            counts = years_in(text, use_lastmod=True)

        found.append({
            'url': candidate,
            'kind': 'sitemap index' if is_index else 'sitemap',
            'entries': len(locs),
            'depth': depth_label(counts),
            'note': child_note,
        })
        if len(found) >= 1:      # one working sitemap per site is enough evidence
            break
    return found


def probe_search(base: str, lang: str, delay: float) -> list[dict]:
    """Try the search / tag shapes that already work for other sources."""

    keyword = KEYWORD[lang]
    results: list[dict] = []
    for shape in SEARCH_SHAPES:
        url = base.rstrip('/') + shape.replace('{q}', quote(keyword))
        status, body, note = fetch(url)
        time.sleep(delay)
        if status != 200 or not body:
            continue
        text = body.decode('utf-8', 'replace')
        links = {m.group(1) for m in ARTICLE_LINK.finditer(text)}
        if len(links) < 10:
            continue
        results.append({
            'url': url,
            'kind': 'search/tag',
            'entries': len(links),
            'depth': depth_label(years_in(' '.join(links))),
            'note': '',
        })
        if len(results) >= 2:
            break
    return results


def report(candidate: dict, hits: list[dict]) -> None:
    print(f"\n{candidate['slug']}  [{candidate['lang']}]  {candidate['base']}")
    print(f"    why: {candidate['prior']}")
    if not hits:
        print('    -- nothing usable found')
        return
    for hit in hits:
        print(f"    OK  {hit['kind']:<13} entries={hit['entries']:<6} "
              f"depth={hit['depth']:<20} {hit['url']}{hit['note']}")


def inspect(base: str, lang: str, delay: float) -> None:
    """Answer the two questions that decide HOW a source can be wired in.

    Depth alone is not enough to add a source. The existing sitemap discovery
    (``discover_himalayan_times_sitemaps``) filters candidates with
    ``keyword_match(article.url, ...)`` -- it looks for the landslide keyword in
    the URL itself. That works for himalayan-times, whose slugs are English
    words. It returns **nothing** for a site using opaque ids like
    ``/?p=12345``, and there is no way to tell which case a site is in from the
    depth figure. Crawling every article to find out is not an option: a 271-child
    sitemap is on the order of a quarter of a million URLs.

    So:

    Q1  Do article URLs carry the keyword? -> if yes, sitemap + keyword filter
        works and the source is nearly free to add.
    Q2  Does the search endpoint paginate backwards in time? -> if yes, use the
        setopati/ratopati search shape instead, which filters server-side.

    A source needs a yes to one of them. Both no means the archive is reachable
    but not *searchable*, and it should be skipped rather than crawled blindly.
    """

    keyword = KEYWORD[lang]
    print(f'\n=== {base}')

    # Q1 -- sample real article URLs out of a child sitemap.
    print('\nQ1  do article URLs contain the keyword?')
    hits = probe_sitemaps(base, delay)
    sample: list[str] = []
    for hit in hits:
        status, body, _ = fetch(hit['url'])
        time.sleep(delay)
        if status != 200:
            continue
        locs = LOC.findall(body.decode('utf-8', 'replace'))
        children = choose_children(locs) or locs[:1]
        for child in children[:1]:
            c_status, c_body, _ = fetch(child)
            time.sleep(delay)
            if c_status == 200:
                sample = LOC.findall(c_body.decode('utf-8', 'replace'))[:8]
        if sample:
            break
    if not sample:
        print('    could not sample article URLs')
    else:
        for url in sample:
            print(f'      {url}')
        quoted = quote(keyword)
        matched = sum(1 for u in sample if keyword in u or quoted in u)
        dated = sum(1 for u in sample if YEAR_IN_URL.search(u))
        print(f'    -> {matched}/{len(sample)} contain the keyword.', end=' ')
        print('sitemap + keyword filter WILL work' if matched
              else 'opaque URLs: keyword filtering on the URL will return NOTHING')
        # Separate question, and a consolation prize worth having: even without
        # the keyword, a DATE in the URL gives year_hint for free and lets the
        # sitemap be walked date-first. deshsanchar has this
        # (/2017/12/02/545/); rajdhani does not (/id/148/).
        print(f'    -> {dated}/{len(sample)} carry a date in the URL.', end=' ')
        print('year_hint comes free; sitemap can be walked by date'
              if dated else 'no date either — every article must be fetched to be dated')

    # Q2 -- walk the search endpoint and see whether the years move.
    #
    # The first version appended `&page=N` and reported "19 links, 2022-2026" on
    # pages 1, 5, 15 AND 40 for rajdhani. Identical counts and identical depth at
    # page 40 is not a shallow archive -- it is the parameter being IGNORED and
    # page 1 served every time. Both these sites are WordPress, which paginates
    # search as a path segment (`/page/2/?s=kw`), not a query parameter.
    #
    # So: try several shapes, and decide by comparing the actual LINK SETS rather
    # than their counts. Two pages with the same number of different links is
    # working pagination; two pages with the same links is a no-op. Counting
    # alone cannot tell those apart, which is exactly how the first run produced
    # a confident wrong answer.
    print('\nQ2  does search paginate backwards in time?')
    searches = probe_search(base, lang, delay)
    if not searches:
        print('    no working search endpoint')
        return

    endpoint = searches[0]['url']
    parts = endpoint.split('?', 1)
    root, query = parts[0].rstrip('/'), (parts[1] if len(parts) > 1 else '')
    shapes = {
        'wp /page/N/?s=': lambda n: f'{root}/page/{n}/?{query}',
        '?...&paged=N':   lambda n: f'{endpoint}&paged={n}',
        '?...&page=N':    lambda n: f'{endpoint}&page={n}',
    }

    def links_at(url: str) -> set[str]:
        status, body, _ = fetch(url)
        time.sleep(delay)
        if status != 200 or not body:
            return set()
        return {m.group(1) for m in ARTICLE_LINK.finditer(body.decode('utf-8', 'replace'))}

    first = links_at(endpoint)
    print(f'    page 1  links={len(first)}')
    for label, build in shapes.items():
        page3 = links_at(build(3))
        if not page3:
            print(f'    {label:<16} page 3 empty — shape not supported')
            continue
        if page3 == first:
            print(f'    {label:<16} page 3 IDENTICAL to page 1 — parameter ignored')
            continue
        deep = links_at(build(30))
        overlap = len(page3 & first) / max(len(page3), 1)
        print(f'    {label:<16} page 3 differs (overlap {overlap:.0%}), '
              f'page 30 links={len(deep)}  '
              f'depth={depth_label(years_in(" ".join(page3 | deep), use_lastmod=False))}')
        print(f'    -> WORKING pagination shape: {build("{page}")}')
        return
    print('    -> no working pagination shape found; search returns only page 1.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', help='probe a single URL and stop')
    parser.add_argument('--inspect', metavar='SLUG',
                        help='deep-dive one candidate: are URLs keyword-bearing, '
                             'and does search paginate? Run this before wiring '
                             'a source into config.yaml.')
    parser.add_argument('--only', help='substring filter on candidate slug')
    parser.add_argument('--lang', choices=('np', 'en'), help='restrict by language')
    parser.add_argument('--delay', type=float, default=1.5,
                        help='seconds between requests (be polite)')
    args = parser.parse_args()

    if args.url:
        status, body, note = fetch(args.url)
        text = body.decode('utf-8', 'replace')
        print(f'status={status} bytes={len(body)} {note}')
        print(f'depth={depth_label(years_in(text))}')
        print(f'article-ish links={len({m.group(1) for m in ARTICLE_LINK.finditer(text)})}')
        return 0

    if args.inspect:
        matches = [c for c in CANDIDATES if args.inspect in c['slug']]
        if not matches:
            print(f'No candidate matching {args.inspect!r}. Known slugs:')
            print('  ' + ', '.join(c['slug'] for c in CANDIDATES))
            return 1
        for candidate in matches:
            inspect(candidate['base'], candidate['lang'], args.delay)
        return 0

    selected = [c for c in CANDIDATES
                if (not args.only or args.only in c['slug'])
                and (not args.lang or c['lang'] == args.lang)]

    print('Prospecting candidate outlets for ARCHIVE DEPTH.')
    print('Read the depth column, not the OK markers: a source that only reaches')
    print('2023 does not fix the hole. This is slow on purpose.\n')
    print(f'{len(selected)} candidates, ~{args.delay:.1f}s between requests.')

    usable: list[tuple[dict, list[dict]]] = []
    for candidate in selected:
        # One bad candidate must not end a 19-site run. Same reasoning as the
        # per-source try/except in scrape/collect.py: partial results that look
        # complete are worse than a loud failure, so failures are named inline.
        try:
            hits = probe_sitemaps(candidate['base'], args.delay)
            # A sitemap that exists but proves no depth is not an answer. Fall
            # through to search/tag in that case too, not only when the sitemap
            # is missing entirely -- otherwise a useless index masks a usable
            # search endpoint, which is how annapurnapost reported nothing on
            # the first run despite having 1,265 children.
            if not hits or all('yrs' not in h['depth'] for h in hits):
                hits = hits + probe_search(candidate['base'], candidate['lang'], args.delay)
        except Exception as exc:  # noqa: BLE001
            print(f"\n{candidate['slug']}  [{candidate['lang']}]  {candidate['base']}")
            print(f'    !! probe failed: {type(exc).__name__}: {exc}')
            sys.stdout.flush()
            continue
        report(candidate, hits)
        sys.stdout.flush()
        if hits:
            usable.append((candidate, hits))

    print('\n' + '=' * 72)
    if not usable:
        print('Nothing found. Either the network blocked us or the shapes have moved.')
        return 1
    print(f'{len(usable)} of {len(selected)} candidates have a reachable index.\n')
    print('Paste this whole output back — the depth figures decide which of these')
    print('are worth wiring into config.yaml and which are just more recent noise.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
