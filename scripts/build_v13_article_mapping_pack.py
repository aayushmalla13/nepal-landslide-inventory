#!/usr/bin/env python3
"""Build the article-level identity decision pack for v1.3 remediation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_core():
    path = Path(__file__).with_name("build_v09_article_mapping_pack.py")
    spec = importlib.util.spec_from_file_location("v13_article_mapping_core", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load article-mapping core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/outputs"
RELEASE_DIR = ROOT / "data/releases/nepal_landslide_inventory_v1.2.0_candidate_20260929"


def configure_core() -> None:
    core.DATABASE = RELEASE_DIR / "landslide_inventory.sqlite"
    core.RELEASE_DIR = RELEASE_DIR
    core.CANONICAL = RELEASE_DIR / "canonical_events_final.csv"
    core.RELEASE_MANIFEST = RELEASE_DIR / "release_manifest.json"
    core.CANDIDATES = OUTPUT / "v13_remediation_BATCH_ARTICLE_MAPPING.csv"
    core.REMEDIATION_MANIFEST = OUTPUT / "v13_remediation_manifest.json"
    core.ARTICLE_MAP = OUTPUT / "v13_article_membership_MAP.csv"
    core.DECISIONS = OUTPUT / "v13_article_mapping_DECISIONS.csv"
    core.MANIFEST = OUTPUT / "v13_article_mapping_manifest.json"
    core.REPORT = OUTPUT / "v13_article_mapping_report.md"
    core.AUDIT_ID = "v13_article_mapping_v1"

    def verify_inputs() -> None:
        remediation = json.loads(core.REMEDIATION_MANIFEST.read_text(encoding="utf-8"))
        if core.sha256(core.CANDIDATES) != remediation["output_sha256"][core.CANDIDATES.name]:
            raise ValueError("Article-mapping batch differs from remediation manifest")
        release = json.loads(core.RELEASE_MANIFEST.read_text(encoding="utf-8"))
        if core.sha256(core.CANONICAL) != release["canonical_summary"]["sha256"]:
            raise ValueError("Candidate canonical CSV differs from release manifest")
        bundled = {row["file"]: row["sha256"] for row in release["files"]}
        if core.sha256(core.DATABASE) != bundled[core.DATABASE.name]:
            raise ValueError("Frozen candidate database differs from release manifest")

    if not hasattr(core, "_v13_original_render_report"):
        core._v13_original_render_report = core.render_report

    def render_report(decisions, articles):
        return core._v13_original_render_report(decisions, articles).replace(
            "# v0.9 article-mapping pack", "# v1.3 article-mapping pack", 1
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
