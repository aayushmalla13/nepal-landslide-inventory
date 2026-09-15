# Research source checkpoint — 2026-09-15

This document identifies the exact source and ignored data state associated with
Git tag `research-state-20260915`. The Git commit contains code, tests,
configuration, correction provenance, gazetteers, scripts, and manuscript
documentation. Large and source-text-bearing data remain outside Git and are
identified by checksummed release bundles.

## Current linked releases

- Inventory: `nepal_landslide_inventory_v0.5.0_v7_20260915`
  - bundle lock: `c3a3679afbef226a57e4dda721e7d4ac1ea2379acea5b63f13b9512d0da15f55`
  - canonical CSV SHA-256: `3b335babbfcbe0b50d2aad9023e08e55a2ca6e8e0881729615df33e2c9b9d0e8`
  - 2,885 canonical events and a SQLite snapshot
  - human locked-v7 validation and reviewed-correction provenance
- Rainfall: `nepal_landslide_rainfall_v0.7.0_20260915`
  - bundle lock: `b90aca466257103880770ee7bbb361ba5e390ffaac6a559f0749e035cec079bf`
  - provenance-only successor to v0.6.0; numerical results are unchanged
  - its manifest verifies that the canonical-input hash matches the inventory
    release above

## Human-validation evidence outside the release bundles

- locked-v7 final labels:
  `177dbaa667063f39e37ff68d86e1b9a128be23ad04cbd2a09c72130bbed78803`
- locked-v7 predictions:
  `917b27bcda7fda4f9c4847217b3017deb64db4aa5b5207584365a44d3b0bfa4f`
- locked-v7 score:
  `68558791e65088ea4a14019fe1b763bad9917770ff860a4d835335f6215bac88`
- second-annotator completed sheet:
  `b693070ba25518bf0269e607eb6bcfc7ffb3588f2391f973747591c9d4dae57c`
- second-annotator draw manifest:
  `3183baf0b746de6f2797fa8283329d5efee4a3cb48d93bf78f36a677e2cf78ad`
- pre-adjudication inter-rater agreement report:
  `c51b9d7d9584465acf1ecfd32920da0b9b56ddfec1266c904785d87862cba3c5`

## Verification commands

```bash
PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider
.venv/bin/python scripts/verify_releases.py --strict
git diff --check
```

At checkpoint creation, the full test suite passed with only the two intentional
data-dependent skips, every historical and current bundle lock verified, and
the working rainfall outputs matched v0.7.0.

## Scope boundary

The tag does not include `data/`, local transfer directories, duplicate
root-level completed sheets, or assistant review scratch files. Reproducible
publication or DOI deposition therefore requires distributing the two current
release directories alongside the tagged source, subject to the source-text and
data-licensing review documented in the manuscript checklist.
