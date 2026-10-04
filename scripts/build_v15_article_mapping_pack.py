#!/usr/bin/env python3
"""Build the article-level identity decision pack for v1.5 remediation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("build_v09_article_mapping_pack.py")
    spec = importlib.util.spec_from_file_location("v15_article_mapping_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load article-mapping core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE_DIR = ROOT / "data/releases/nepal_landslide_inventory_v1.4.0_candidate_20261002"
ARTICLE_RELEASE_DIR = ROOT / "data/releases/nepal_landslide_inventory_v1.2.0_candidate_20260929"


def configure_core() -> None:
    core.DATABASE = ARTICLE_RELEASE_DIR / "landslide_inventory.sqlite"
    core.RELEASE_DIR = RELEASE_DIR
    core.CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
    core.RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
    core.CANDIDATES = OUTPUT / "v15_remediation_BATCH_ARTICLE_MAPPING.csv"
    core.REMEDIATION_MANIFEST = OUTPUT / "v15_remediation_manifest.json"
    core.ARTICLE_MAP = OUTPUT / "v15_article_membership_MAP.csv"
    core.DECISIONS = OUTPUT / "v15_article_mapping_DECISIONS.csv"
    core.MANIFEST = OUTPUT / "v15_article_mapping_manifest.json"
    core.REPORT = OUTPUT / "v15_article_mapping_report.md"
    core.AUDIT_ID = "v15_article_mapping_v1"

    def verify_inputs() -> None:
        remediation = json.loads(core.REMEDIATION_MANIFEST.read_text(encoding="utf-8"))
        if core.sha256(core.CANDIDATES) != remediation["output_sha256"][core.CANDIDATES.name]:
            raise ValueError("Article-mapping batch differs from remediation manifest")
        release = json.loads(core.RELEASE_MANIFEST.read_text(encoding="utf-8"))
        if core.sha256(core.CANONICAL) != release["canonical_summary"]["sha256"]:
            raise ValueError("v1.4 canonical CSV differs from release manifest")
        database_key = str(core.DATABASE.relative_to(ROOT))
        if core.sha256(core.DATABASE) != release["inputs"][database_key]:
            raise ValueError("Pinned v1.2 article database differs from v1.4 provenance")

    if not hasattr(core, "_v15_original_render_report"):
        core._v15_original_render_report = core.render_report

    def render_report(decisions, articles):
        return core._v15_original_render_report(decisions, articles).replace(
            "# v0.9 article-mapping pack", "# v1.5 article-mapping pack", 1
        )

    core.verify_inputs = verify_inputs
    core.render_report = render_report
    core.__file__ = __file__


configure_core()
build_rows = core.build_rows
proposed_resolution = core.proposed_resolution


def main() -> int:
    configure_core()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
