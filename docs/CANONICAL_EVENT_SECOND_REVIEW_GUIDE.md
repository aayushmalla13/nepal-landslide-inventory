# Independent second review of the canonical event audit

## Who should complete this

This pack must be completed by a different human reviewer from the first audit.
The second reviewer must not open:

- `canonical_event_audit_COMPLETED.csv`
- `canonical_event_audit_score.json`
- `canonical_event_audit_report.md`
- `canonical_event_audit_second_mapping.csv`
- `docs/CANONICAL_EVENT_AUDIT_RESULT.md`

The first reviewer used annotator ID `human`. The second reviewer must use a
different stable name or initials in every `annotator` cell.

## Files to open

Open these beside each other:

- `data/outputs/canonical_event_audit_second_LABEL_HERE.csv`
- `data/outputs/canonical_event_audit_second_reading_pack.csv`

The same 150 events are presented in a new shuffled order with new row IDs. No
first-review answer or note appears in either file.

## Labelling

Use the same rules as `docs/CANONICAL_EVENT_AUDIT_GUIDE.md`:

1. Fill `event_really_happened` with `yes`, `no`, or `unclear` for every row.
2. If `yes`, complete the event, district, date, type, hazard, deaths, and
   duplicate-merge fields.
3. Use `not_applicable` for `duplicate_merge_correct` when the cluster contains
   one article.
4. Fill `annotator` on every row and use concise evidence in `notes`.
5. Do not reorder rows or modify claimed fields.

Save the completed file as:

`data/outputs/canonical_event_audit_second_COMPLETED.csv`

## Agreement and adjudication

After completion, run:

```bash
PYTHONPATH=src .venv/bin/python scripts/score_canonical_event_second_review.py
```

The scorer validates independence and immutable fields, reports exact agreement
and Cohen's kappa, and creates
`data/outputs/canonical_event_audit_ADJUDICATE.csv` containing only rows where
the reviewers differ. The final correction layer must use adjudicated answers,
not either reviewer's answers alone.
