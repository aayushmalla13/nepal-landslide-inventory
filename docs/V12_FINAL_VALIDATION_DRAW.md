# v1.2 final locked validation draw

Date: 2026-09-29

## Candidate

- Release: `nepal_landslide_inventory_v1.2.0_candidate_20260929`
- Canonical events: 2,160.
- Canonical SHA-256:
  `0c077fab7290b3fbc3f9a74dacb3adfa827e19466433221b4424b4cd75162643`.
- Database SHA-256:
  `f5af3c3c0d256f74d9350a6190ff2152216f8d08f0cc311e83c9d221d7e1a9aa`.
- Bundle lock hash:
  `a3defc5aed2458541a9276b89849c7f62857f487f9240e12bdda328a95c78220`.
- Status: `pending_fresh_validation`.

## Draw

- Prespecified seed: 20260929.
- Eligible frame after all prior-review exclusions: 1,040 events.
- Reviewed event IDs excluded: 933.
- Reviewed article URLs excluded: 2,387.
- Stratified probability sample: 150 events.
- Unique sampled event IDs: 150.
- Previously unseen article URLs represented in the sample: 195.
- Sampled events with unavailable article evidence: 0.
- Sample overlap with reviewed event IDs: 0.
- Sample overlap with reviewed article URLs: 0.
- Nonblank label cells at draw time: 0.
- Repeated draw byte-identical: yes.

The strata are title language, study-period band, event type, and single- versus
multi-article support. Inclusion probabilities and sampling weights are locked
in `data/outputs/v12_final_validation_weights.csv`.

## Locked files

- Label sheet SHA-256:
  `a0025cc4e41cf077eca33c2e26ad80a945e5a74d0042023fb69bb14f35f45755`.
- Reading pack SHA-256:
  `0084768b8f44dc98ff7a4392a42332ea125401ab88b931f54a7137dc26cc3014`.
- Weights SHA-256:
  `3dc6374f9fe3a285ff2b3d1fea452510ae703f7118278d45885d277bfd07f706`.
- Draw manifest SHA-256:
  `83368209a62fbfbe40a6f8c150970800fdbab84c3c9a7108bb2db4c514079138`.

No performance claim or promotion decision exists for v1.2 until the completed
label sheet passes structural validation and the locked scorer is run.
