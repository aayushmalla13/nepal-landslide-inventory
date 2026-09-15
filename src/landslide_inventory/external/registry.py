"""External adapter registry."""

from __future__ import annotations

from .archives import CommonCrawlAdapter, MediaCloudAdapter, WaybackCdxAdapter
from .base import SourceAdapter
from .structured import (
    ArcGisAdapter,
    BipadAdapter,
    DelimitedExportAdapter,
    DrrPortalAdapter,
    GenericJsonAdapter,
    ReliefWebAdapter,
    RoadClosureAdapter,
)
from .webdocs import (
    ArmedPoliceAdapter,
    HtmlDocumentsAdapter,
    KantipurEpaperAdapter,
    NdrrmaBulletinAdapter,
    NepalPoliceAdapter,
    RoadNoticeAdapter,
    RssAdapter,
)

ADAPTERS: dict[str, type[SourceAdapter]] = {
    "bipad": BipadAdapter,
    "drr_portal": DrrPortalAdapter,
    "generic_json": GenericJsonAdapter,
    "arcgis": ArcGisAdapter,
    "coolr": ArcGisAdapter,
    "reliefweb": ReliefWebAdapter,
    "road_closures": RoadClosureAdapter,
    "desinventar": DelimitedExportAdapter,
    "delimited_export": DelimitedExportAdapter,
    "wayback_cdx": WaybackCdxAdapter,
    "common_crawl": CommonCrawlAdapter,
    "media_cloud": MediaCloudAdapter,
    "html_documents": HtmlDocumentsAdapter,
    "ndrrma_bulletins": NdrrmaBulletinAdapter,
    "nepal_police": NepalPoliceAdapter,
    "armed_police": ArmedPoliceAdapter,
    "road_notices": RoadNoticeAdapter,
    "rss": RssAdapter,
    "kantipur_epaper": KantipurEpaperAdapter,
}


def adapter_class(name: str) -> type[SourceAdapter]:
    try:
        return ADAPTERS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown external adapter '{name}'. Available: {', '.join(sorted(ADAPTERS))}"
        ) from exc
