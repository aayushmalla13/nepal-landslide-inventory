#!/usr/bin/env python3
"""Create the dependency-free SVG manuscript figures from the analysis outputs.

The figure code lives in ``landslide_inventory.analysis.figures`` so it is
importable and testable; this script stays as the documented entry point.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from landslide_inventory.analysis.figures import run_rainfall_figures_stage  # noqa: E402
from landslide_inventory.config import load_config  # noqa: E402


def main() -> None:
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config.yaml"
    run_rainfall_figures_stage(load_config(config_path))


if __name__ == "__main__":
    main()
