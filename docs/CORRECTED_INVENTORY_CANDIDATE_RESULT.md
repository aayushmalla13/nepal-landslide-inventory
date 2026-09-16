# Corrected inventory candidate result

## Status

The validated identity, true-value, and structured-attribute plans have been
assembled into:

`data/releases/nepal_landslide_inventory_v0.7.0_candidate_20260916/`

This is a versioned candidate release with status
`pending_post_correction_validation`. It is not yet the final paper release and
does not inherit the frozen v7 evaluation metrics.

## Inventory effect

- Frozen source inventory: 2,885 events
- Superseded events removed: 55
- Reconstructed physical events added: 85
- Reconstruction candidates merged into existing events: 12
- True-value exclusions: 11
- Final candidate inventory: 2,904 events
- Net change: +19 events

All 2,904 event IDs are unique. The CSV and standalone SQLite snapshot contain
the same row count and date extent (`2015-03-07` to `2026-08-09`).

## Reproducibility

The builder is `scripts/assemble_corrected_inventory_release.py`. It validates
the checksums pinned by all three plan manifests before applying any change. It
also emits a 216-row correction application log, article-level provenance for
all reconstructed and merged events, and a checksummed release manifest.

The canonical CSV SHA-256 is:

`182071353abd87fed8404d0ae82b172b64d410599bf6e36a532c363cb6fdf663`

The repository release verifier accepts the bundle lock. Semantic
reconciliation confirms that every removal, addition, merge, exclusion, and
attribute correction matches its validated plan row.

## Next gate

Draw and label a fresh locked post-correction sample from this candidate. Only
after that gate passes should the candidate be promoted to a final inventory
release and used to rerun the rainfall linkage and manuscript tables.
