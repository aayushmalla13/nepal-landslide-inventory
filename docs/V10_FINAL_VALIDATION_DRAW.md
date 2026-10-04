# v1.0 final locked validation draw

Date: 2026-09-27

## Candidate

- Release: `nepal_landslide_inventory_v1.0.0_candidate_20260927`
- Canonical events: 2,605
- Canonical SHA-256:
  `68f2efd27a2c929c0df879974afcde14560ecbd6edf2ce389cc03a18f0857c8a`
- Status: `pending_fresh_validation`
- Release bundle lock: verified by `scripts/verify_releases.py`

## Draw

- Prespecified seed: 20260927
- Eligible frame after prior-review exclusions: 1,557 events
- Reviewed event IDs excluded: 633
- Reviewed article URLs excluded: 1,975
- Stratified probability sample: 150 events
- Sampled events with unavailable article evidence: 0
- Duplicate sampled event IDs: 0
- Label fields populated at draw time: 0
- Repeated draw byte-identical: yes

The strata are title language, study-period band, event type, and single- versus
multi-article support. Inclusion probabilities and sampling weights are locked
in `data/outputs/v10_final_validation_weights.csv`.

## Locked files

- Label sheet: `data/outputs/v10_final_validation_LABEL_HERE.csv`
  (`cce26b3d075859dc9b253467437391ac1600caa3646bfa0c4e2a5bfb55a5a90b`)
- Reading pack: `data/outputs/v10_final_validation_reading_pack.csv`
  (`d4ea26e46b1d7cef03314cbdaf135cfe38a480f1754b2b0f779de4155ca445c5`)
- Weights: `data/outputs/v10_final_validation_weights.csv`
  (`4a6b71b7fdda098fe6cf53a568c2953856bc04e9a50235f180c16e8361e6675a`)
- Manifest: `data/outputs/v10_final_validation_manifest.json`
  (`bb942dd26203a37c4db4512626ad63a63dbb0821735c498ac4289e34dbbd4d32`)

## Next gate

An independent reviewer must complete the label sheet using only the reading
pack and `docs/V10_FINAL_VALIDATION_GUIDE.md`. Save it as
`data/outputs/v10_final_validation_COMPLETED.csv`. The scorer will reject
changed claims, row order, or lock provenance.

No performance claim or promotion decision exists for v1.0 until that file is
validated and scored.
