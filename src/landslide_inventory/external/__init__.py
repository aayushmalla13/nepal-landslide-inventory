"""Collection of non-news observations and archive discovery metadata.

External records deliberately live outside ``raw_articles`` and
``canonical_events``.  They may be used for discovery, triangulation, or
validation, but are never silently treated as independent news articles.
"""

from .discover import run_external_discover_stage
from .ingest import run_external_epaper_ingest_stage, run_external_ingest_stage
from .match import run_external_match_stage
from .review_sync import run_external_review_sync_stage
from .epaper_ingest import run_external_epaper_ingest_stage
from .models import ExternalRecord
from .pipeline import (
    run_external_collect_stage,
    run_external_export_stage,
    run_external_probe_stage,
)

__all__ = [
    "ExternalRecord",
    "run_external_collect_stage",
    "run_external_discover_stage",
    "run_external_ingest_stage",
    "run_external_epaper_ingest_stage",
    "run_external_export_stage",
    "run_external_match_stage",
    "run_external_review_sync_stage",
    "run_external_epaper_ingest_stage",
    "run_external_probe_stage",
]
