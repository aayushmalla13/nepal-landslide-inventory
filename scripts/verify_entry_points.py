#!/usr/bin/env python3
"""Check candidate archive entry points before committing them to config.yaml.

WHY THIS EXISTS
The collection has severe holes, and they follow the discovery method exactly:

    source            method       earliest article   years with data
    myrepublica       tag          2012-07-27         12
    setopati          tag          2017-07-26         10
    himalayan-times   googlenews   2015-06-08         10  (mostly 429 pages)
    ekantipur         googlenews   2019-11-24          5
    kathmandu-post    googlenews   2019-07-19          3
    rising-nepal      googlenews   2022-03-25          3

Google News RSS `site:` queries return only recent items and never backfill
archives (review section 9.11). Every source that relies on it is missing most of
its history, which is why 2024 has 4.5x the articles of 2016 -- coverage, not
landslide activity.

The fix is per-site tag or archive pagination, as myrepublica and setopati
already use. But tag URLs change and cannot be guessed reliably, so this script
checks candidates before they go into config: does the URL return 200, does it
contain article links, and does pagination actually advance?

USAGE (run on a machine with network access to Nepali news sites)
    python scripts/verify_entry_points.py
    python scripts/verify_entry_points.py --url https://ekantipur.com/tag/pahiro
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UA = 'landslide-inventory/0.1.0 (+research; verifying archive entry points)'

# Candidates for the four sources with no working archive path. These are
# PATTERNS THAT NEED CHECKING, not verified URLs -- the whole point of this
# script. Nepali outlets change tag slugs; treat every one as a hypothesis.
CANDIDATES: dict[str, list[str]] = {
    'ekantipur': [
        'https://ekantipur.com/tag/पहिरो',
        'https://ekantipur.com/tag/landslide',
        'https://ekantipur.com/news',
        'https://ekantipur.com/search?q=पहिरो',
    ],
    'kathmandu-post': [
        'https://kathmandupost.com/tag/landslide',
        'https://kathmandupost.com/tag/landslides',
        'https://kathmandupost.com/tag/monsoon-floods',
        'https://kathmandupost.com/search?q=landslide',
    ],
    'himalayan-times': [
        'https://thehimalayantimes.com/tag/landslide',
        'https://thehimalayantimes.com/search?q=landslide',
        'https://thehimalayantimes.com/nepal',
    ],
    'rising-nepal': [
        'https://risingnepaldaily.com/tag/landslide',
        'https://risingnepaldaily.com/search?q=landslide',
    ],
    # These two work but stopped early -- check whether deeper pages exist.
    'online-khabar': [
        'https://www.onlinekhabar.com/trend/पहिरो/page/20',
        'https://www.onlinekhabar.com/trend/पहिरो/page/50',
    ],
    'ratopati': [
        'https://www.ratopati.com/tag/797?page=20',
        'https://www.ratopati.com/tag/797?page=50',
    ],
}

ARTICLE_LINK = re.compile(r'href="([^"]*(?:/20\d{2}/|/news/|/story/|/\d{6,})[^"]*)"')


def probe(url: str, timeout: int = 20) -> dict:
    """Fetch a candidate and report whether it looks like a usable index page."""

    try:
        with urlopen(Request(url, headers={'User-Agent': UA}), timeout=timeout) as response:
            body = response.read().decode('utf-8', errors='replace')
            status = int(response.status)
    except HTTPError as exc:
        return {'url': url, 'status': int(exc.code), 'links': 0, 'verdict': 'HTTP error'}
    except (URLError, TimeoutError, OSError) as exc:
        return {'url': url, 'status': None, 'links': 0, 'verdict': f'unreachable: {exc}'}

    links = {m.group(1) for m in ARTICLE_LINK.finditer(body)}
    # A tag page worth using lists many distinct articles, not a handful.
    verdict = ('USABLE' if len(links) >= 10 else
               'thin — few article links' if links else 'no article links found')
    return {'url': url, 'status': status, 'links': len(links), 'verdict': verdict}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', help='check a single URL instead of the candidate list')
    parser.add_argument('--delay', type=float, default=2.0, help='seconds between requests')
    args = parser.parse_args()

    if args.url:
        result = probe(args.url)
        print(f"{result['status']}  links={result['links']:<4} {result['verdict']}  {result['url']}")
        return 0 if result['verdict'] == 'USABLE' else 1

    print('Probing candidate archive entry points.')
    print('Be polite: this sleeps between requests.\n')
    usable: dict[str, list[str]] = {}
    for source, urls in CANDIDATES.items():
        print(f'{source}')
        for url in urls:
            result = probe(url)
            marker = '  OK ' if result['verdict'] == 'USABLE' else '     '
            print(f"{marker}{str(result['status']):>4}  links={result['links']:<4} "
                  f"{result['verdict']:<26} {url}")
            if result['verdict'] == 'USABLE':
                usable.setdefault(source, []).append(url)
            time.sleep(args.delay)
        print()

    print('=' * 72)
    if not usable:
        print('No candidate verified. The tag slugs have probably changed —')
        print('open each site, find its landslide tag page, and re-run with --url.')
        return 1
    print('Add these to config.yaml under the matching source\'s entry_points,')
    print('as kind: tag with the appropriate pagination, and REMOVE the')
    print('googlenews entry point so archive pagination is the primary path:\n')
    for source, urls in usable.items():
        print(f'  {source}:')
        for url in urls:
            print(f'    - kind: tag')
            print(f'      url: {url}')
            print(f'      pagination: page   # or next_link / /page/{{page}} — check the site')
    return 0


if __name__ == '__main__':
    sys.exit(main())
