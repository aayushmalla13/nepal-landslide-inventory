"""Tests for source-aware article parsing."""

from __future__ import annotations

from pathlib import Path

from landslide_inventory.config import load_config
from landslide_inventory.scrape.parser import parse_article_html
from landslide_inventory.sources import load_sources


def test_parse_kathmandu_post_fixture(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "kathmandu-post")
    html = Path("tests/fixtures/html/kathmandu_post_article.html").read_text(encoding="utf-8")
    article = parse_article_html(source, html, "https://kathmandupost.com/national/2021/07/14/story")
    assert article.parse_success is True
    assert article.title == "Landslide kills 2 in Sindhupalchok"
    assert article.published_date_raw == "2021-07-14T08:00:00+05:45"
    assert "heavy rain" in article.text


def test_parse_onlinekhabar_fixture(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "online-khabar")
    html = Path("tests/fixtures/html/online_khabar_article.html").read_text(encoding="utf-8")
    article = parse_article_html(source, html, "https://www.onlinekhabar.com/2022/08/1170000")
    assert article.parse_success is True
    assert article.title == "पहिरोमा ३ जनाको मृत्यु"
    assert article.published_date_raw == "2022-08-03T11:15:00+05:45"
    assert "सिन्धुपाल्चोक" in article.text


def test_parse_json_ld_datepublished_fallback(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "ekantipur")
    html = """
    <html>
      <head>
        <title>Example title</title>
        <script type="application/ld+json">
          {"@context":"https://schema.org","datePublished":"2026-03-23 17:53:59"}
        </script>
      </head>
      <body>
        <article><p>Example body</p></article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://ekantipur.com/example")
    assert article.published_date_raw == "2026-03-23 17:53:59"


def test_parse_time_datetime_fallback(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "setopati")
    html = """
    <html>
      <head><title>Example time fallback</title></head>
      <body>
        <time datetime="2024-07-12T09:30:00+05:45">2024-07-12</time>
        <article><p>Example body</p></article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://www.setopati.com/social/123")
    assert article.published_date_raw == "2024-07-12T09:30:00+05:45"


def test_parse_url_date_fallback(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "ekantipur")
    html = """
    <html>
      <head><title>URL date fallback</title></head>
      <body><article><p>Example body</p></article></body>
    </html>
    """
    article = parse_article_html(source, html, "https://ekantipur.com/koshi-pradesh/2026/03/24/example-story.html")
    assert article.published_date_raw == "2026-03-24"


def test_parse_setopati_visible_bs_publish_block(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "setopati")
    html = """
    <html>
      <head><title>Setopati article</title></head>
      <body>
        <div class="published-date col-md-6">
          <span class="pub-date">प्रकाशित मिति: आइतबार, साउन ४, २०८२ <span class="fa fa-clock-o"></span> १६:३४</span>
        </div>
        <article><p>Example body</p></article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://www.setopati.com/social/364609")
    assert article.published_date_raw == "आइतबार, साउन ४, २०८२ १६:३४"


def test_parse_rising_nepal_visible_publish_block_with_abbreviated_weekday(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "rising-nepal")
    html = """
    <html>
      <head><title>Rising Nepal article</title></head>
      <body>
        <div class="jeg_meta_date">Sun, 3 July 2022</div>
        <article><p>Example body</p></article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://risingnepaldaily.com/news/13416")
    assert article.published_date_raw == "Sun, 3 July 2022"


def test_parse_ratopati_published_json_field_fallback(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "ratopati")
    html = """
    <html>
      <head>
        <title>Ratopati article</title>
        <script type="application/ld+json">
          {"Published":"2026-03-25 21:33:31"}
        </script>
      </head>
      <body><article><p>Example body</p></article></body>
    </html>
    """
    article = parse_article_html(source, html, "https://www.ratopati.com/story/552740/example")
    assert article.published_date_raw == "2026-03-25 21:33:31"


def test_parse_meta_datepublished_name_fallback(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "ratopati")
    html = """
    <html>
      <head>
        <title>Ratopati article</title>
        <meta name="datePublished" content="2026-03-25 20:45:31" />
      </head>
      <body><article><p>Example body</p></article></body>
    </html>
    """
    article = parse_article_html(source, html, "https://www.ratopati.com/story/552735/example")
    assert article.published_date_raw == "2026-03-25 20:45:31"


def test_parse_visible_month_day_year_publish_text(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "kathmandu-post")
    html = """
    <html>
      <head><title>KP publish text</title></head>
      <body>
        <div class="updated-time">Published at : March 24, 2026</div>
        <article><p>Example body</p></article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://kathmandupost.com/national/2026/03/24/example")
    assert article.published_date_raw == "March 24, 2026"


def test_parse_kathmandu_post_prefers_published_at_over_other_dates(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "kathmandu-post")
    html = """
    <html>
      <head><title>KP publish specificity</title></head>
      <body>
        <div class="top-item-left">Thursday, 26 March 2026</div>
        <div class="updated-time">Published at : March 24, 2026</div>
        <div class="updated-time">Updated at : March 24, 2026 09:55</div>
        <article><p>Example body</p></article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://kathmandupost.com/national/2026/03/24/example")
    assert article.published_date_raw == "March 24, 2026"


def test_parse_myrepublica_prefers_json_ld_over_broken_template_time(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "myrepublica")
    html = """
    <html>
      <head>
        <title>myRepublica article</title>
        <script type="application/ld+json">
          {"@context":"https://schema.org","datePublished":"2022-06-01T14:24:00+05:45"}
        </script>
      </head>
      <body>
        <time id="pub-date" datetime="2024-08-08"></time>
        <article><p>Example body</p></article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://myrepublica.nagariknetwork.com/news/example")
    assert article.published_date_raw == "2022-06-01T14:24:00+05:45"


def test_parse_rising_nepal_ignores_generic_page_top_text_without_publish_block(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "rising-nepal")
    html = """
    <html>
      <head><title>Rising Nepal article</title></head>
      <body>
        <div class="site-date">Wednesday, 1 April 2026</div>
        <article><p>Kimathanka, June 1 (RSS): Two people were buried to death in a landslide.</p></article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://risingnepaldaily.com/news/11980")
    assert article.published_date_raw is None




def test_parse_himalayan_times_falls_back_when_htmlparser_collects_js_noise(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "himalayan-times")
    html = """
    <html>
      <head>
        <title>Taplejung landslide update - The Himalayan Times</title>
        <meta property="article:published_time" content="2015-06-11T19:49:12+05:45" />
      </head>
      <body>
        <article class="post-content">
          <p>,"#"===e.firstChild.getAttribute("href")})||fe("type|href|height|width",function(e,t,n){if(!n)return e.getAttribute(t)}</p>
          <div><p>Taplejung, June 11</p><p>Security personnel recovered 21 bodies after the landslides in Taplejung.</p></div>
        </article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://thehimalayantimes.com/nepal/21-bodies-recovered-from-taplejung-landslides-number-of-missing-unknown")
    assert article.parse_success is True
    assert article.published_date_raw == "2015-06-11T19:49:12+05:45"
    assert "Security personnel recovered 21 bodies after the landslides in Taplejung." in article.text
    assert "firstChild.getAttribute" not in article.text

def test_parse_himalayan_times_ignores_script_noise_and_uses_article_paragraphs(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "himalayan-times")
    html = """
    <html>
      <head>
        <title>Six of a family buried to death in Rolpa landslide - The Himalayan Times - Nepal's No.1 English Daily Newspaper</title>
        <meta property="article:published_time" content="2019-09-14T14:25:03+05:45" />
      </head>
      <body>
        <script>var junk='","#"===e.firstChild.getAttribute("href")})||fe("type|href|height|width",function(e,t,n){if(!n)return e.getAttribute(t)';</script>
        <article class="post-content">
          <h1>Six of a family buried to death in Rolpa landslide</h1>
          <p>Rolpa, September 14</p>
          <p>Six members of a family were buried to death in a landslide in Rolpa.</p>
          <p>Police said the victims died on the spot.</p>
        </article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://thehimalayantimes.com/nepal/six-of-a-family-buried-to-death-in-rolpa-landslide")
    assert article.parse_success is True
    assert article.published_date_raw == "2019-09-14T14:25:03+05:45"
    assert "Six members of a family were buried to death in a landslide in Rolpa." in article.text
    assert "getAttribute" not in article.text


def test_parse_ratopati_trims_navigation_noise_from_article_text(config_file) -> None:
    config = load_config(config_file)
    source = next(source for source in load_sources(config) if source.slug == "ratopati")
    html = """
    <html>
      <head>
        <title>ललितपुरको टाकुचेमा पहिरो खसेर कान्ति लोकपथ अवरुद्ध | Nepal's first 24-hour updated news portal - Ratopati</title>
        <meta name="datePublished" content="2026-04-21 12:30:00" />
      </head>
      <body>
        <article>
          <p>काठमाडौँ । अविरल वर्षाका कारण ललितपुरको बागमती गाउँपालिका वडा नम्बर–३ टाकुचेमा पहिरो खसेको छ । पहिरोका कारण हेटौँडा जोड्ने कान्ति लोकपथ पूर्ण रुपमा अवरुद्ध भएको जिल्ला प्रशासन कार्यालय ललितपुरले जनाएको छ । समाचार अदालत/प्रशासन सुरक्षा/अपराध हेडलाइन एक्सक्लुसिभ प्रदेश थप समाचार सिरहामा वडाध्यक्षले सचिवलाई कुटेपछि...</p>
        </article>
      </body>
    </html>
    """
    article = parse_article_html(source, html, "https://www.ratopati.com/story/999999/example")
    assert article.parse_success is True
    assert "कान्ति लोकपथ पूर्ण रुपमा अवरुद्ध" in article.text
    assert "समाचार अदालत/प्रशासन सुरक्षा/अपराध" not in article.text
    assert "थप समाचार" not in article.text
    assert "‘सबैको, सबैभन्दा राम्रो’ रातोपाटी डटकम" not in article.text
