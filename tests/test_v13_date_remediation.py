"""Locks the reviewed date decisions introduced by v1.3 remediation."""

from __future__ import annotations

from pathlib import Path

from landslide_inventory.unify.reviewed_corrections import load_reviewed_corrections


ROOT = Path(__file__).resolve().parents[1]


def test_v13_reviewed_date_corrections_and_exclusions_are_versioned() -> None:
    rows = load_reviewed_corrections(ROOT / "corrections/article_corrections.csv")
    by_url = {row["url"]: row for row in rows}

    tuin = by_url[
        "https://www.onlinekhabar.com/2025/09/1768535/"
        "landslide-in-tuin-khela-disrupts-traffic-on-narayangadh-muglin-road-section"
    ]
    assert tuin["published_date_ad"] == "2025-09-19"
    assert tuin["event_date_ad"] == "2025-09-19"

    daunne = by_url[
        "https://www.onlinekhabar.com/2025/08/1735669/"
        "landslide-in-daunne-east-west-highway-closed-to-one-way-traffic"
    ]
    assert daunne["event_date_ad"] == "2025-08-04"
    assert daunne["district"] == "Nawalpur"

    unresolved = by_url[
        "https://myrepublica.nagariknetwork.com/news/"
        "school-closed-due-to-landslide-for-over-20-days-in-panchthar"
    ]
    assert unresolved["event_date_ad"] is None
    assert unresolved["exclude_from_canonical"] == 1
