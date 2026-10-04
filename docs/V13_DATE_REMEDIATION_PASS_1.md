# v1.3 date remediation pass 1

**Status:** diagnostic repair complete; not a validated release

The frozen v1.2 probability sample identified 23 confirmed date failures. This
pass traced each failure to source evidence, tested broader parser rules, and
rejected the broad parser change after a global replay changed 504 article
dates and introduced at least one known Simaltal regression.

The accepted implementation is intentionally conservative:

- 17 records receive reviewed exact-date corrections.
- 6 records are excluded because the source does not establish an exact onset
  or leaves event identity/location unresolved.
- 19 article date/location values change, and every changed URL is present in
  the reviewed correction layer.
- No unreviewed article date or location changes.

The isolated diagnostic starts from the frozen v1.2 database and produces
2,152 canonical records, down from 2,160. The reduction reflects six explicit
exclusions plus consolidation caused by corrected event identities. The frozen
v1.2 canonical and database hashes remain unchanged.

`v13_date_remediation_replay.csv` and
`v13_date_remediation_summary.json` verify all 23 outcomes. This is a repair
replay on a spent sample, not a new performance estimate. Promotion still
requires completion of the remaining v1.3 remediation queue and a newly drawn,
untouched human validation sample.
