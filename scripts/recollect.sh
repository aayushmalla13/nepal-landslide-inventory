#!/usr/bin/env bash
#
# Re-collect and rebuild the inventory, in the right order, with checks.
#
#   ./scripts/recollect.sh backup     back up the database (do this first)
#   ./scripts/recollect.sh collect    re-crawl the sources        (~1 hour)
#   ./scripts/recollect.sh rebuild    rerun the pipeline          (~10 min)
#   ./scripts/recollect.sh check      before/after comparison
#   ./scripts/recollect.sh all        backup + collect + rebuild + check
#   ./scripts/recollect.sh restore    undo everything
#
# Every step stops on the first error rather than carrying on with bad data.
# Nothing here needs the virtualenv activated; make handles that.

set -euo pipefail
cd "$(dirname "$0")/.."

DB=data/raw_sqlite/landslide_inventory.sqlite
STAMP=$(date +%Y%m%d_%H%M)
BACKUP="data/raw_sqlite/landslide_inventory.snapshot_${STAMP}_pre_recollect.sqlite"
PY="${PY_OVERRIDE:-.venv/bin/python}"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32m%s\033[0m\n' "$*"; }
warn() { printf '   \033[33m%s\033[0m\n' "$*"; }
die()  { printf '\n\033[31mSTOPPED: %s\033[0m\n' "$*" >&2; exit 1; }

[ -x "$PY" ] || die "No virtualenv at $PY. Run: make install"

stats() {
  PYTHONPATH=src "$PY" - "$1" <<'PYEOF'
import sqlite3, sys
label = sys.argv[1]
c = sqlite3.connect('file:data/raw_sqlite/landslide_inventory.sqlite?mode=ro', uri=True)
one = lambda q: c.execute(q).fetchone()[0]
H = ("event_type='landslide' AND hazard_type IN "
     "('landslide','debris_flow','rockfall')")
USABLE = (
    "select count(*) from raw_articles "
    "where http_status = 200 and length(coalesce(text, '')) >= 200"
)
print(f'   {label}')
print('     articles          %6d' % one('select count(*) from raw_articles'))
print('     usable (200+text) %6d' % one(USABLE))
try:
    print('     headline events   %6d' % one('select count(*) from canonical_events where ' + H))
except sqlite3.OperationalError:
    print('     headline events        -  (pipeline not yet run)')
PYEOF
}

case "${1:-all}" in

backup)
  say "Backing up the database"
  [ -f "$DB" ] || die "No database at $DB"
  cp "$DB" "$BACKUP"
  ok "saved $BACKUP"
  say "Running the test suite"
  make test >/dev/null 2>&1 || die "Tests fail. Do not collect on a broken tree — send me the output of 'make test'."
  ok "tests pass"
  stats "current state:"
  ;;

collect)
  say "Checking the crawl rate"
  grep -q 'rate_limit_seconds: 3.0' config.yaml \
    && ok "rate_limit_seconds is 3.0 (polite)" \
    || warn "rate_limit_seconds is not 3.0 — you may get rate-limited again"
  say "Rate-limit errors before this run"
  make run STAGE=article_quality 2>&1 | grep -E 'http_429|not usable' || true
  say "Collecting  (this is the slow one — leave it running)"
  make run STAGE=collect
  say "Rate-limit errors after this run"
  make run STAGE=article_quality 2>&1 | grep -E 'http_429|not usable' || true
  ok "if http_429 dropped, the recovery worked"
  ;;

rebuild)
  say "Rebuilding the inventory"
  for stage in normalize_dates lang extract event_specificity \
               location_consistency filter_scope corrections dedup event_typing export_final; do
    printf '   %-22s' "$stage"
    make run STAGE="$stage" >/tmp/stage_$stage.log 2>&1 \
      || { echo; die "$stage failed. Send me: tail -30 /tmp/stage_$stage.log"; }
    echo "done"
  done
  ok "dataset written to data/outputs/canonical_events_final.csv"
  grep -h 'headline landslide events' /tmp/stage_event_typing.log || true
  grep -h 'merge rate en-np'          /tmp/stage_dedup.log       || true
  ;;

check)
  say "Where you stand now"
  stats "after:"
  say "Events per year  (watch whether the curve flattens)"
  PYTHONPATH=src "$PY" - <<'PYEOF'
import sqlite3
c = sqlite3.connect('file:data/raw_sqlite/landslide_inventory.sqlite?mode=ro', uri=True)
rows = list(c.execute(
    "select substr(event_date_ad,1,4), count(*) from canonical_events "
    "where event_type='landslide' group by 1 order by 1"))
counts = dict(rows)
for year, n in rows:
    print(f'     {year}: {n:4d} ' + '#' * (n // 4))
a, b = counts.get('2024'), counts.get('2016')
if a and b:
    print(f'\n     2024/2016 ratio: {a/b:.1f}x   (was 4.5x)')
    print('     Below ~2x means the temporal analysis becomes defensible.')
    print('     Still 4.5x means the skew is real — report it as a limitation.')
PYEOF
  ;;

restore)
  say "Restoring"
  latest=$(ls -t data/raw_sqlite/*pre_recollect.sqlite 2>/dev/null | head -1) \
    || die "No backup found"
  [ -n "$latest" ] || die "No backup found"
  cp "$latest" "$DB"; ok "database restored from $latest"
  git checkout config.yaml 2>/dev/null && ok "config.yaml reverted" || true
  ;;

all)
  # Invoke via `bash "$0"` rather than "$0": the execute bit does not survive
  # on a Box-synced folder, so a bare "$0" fails with Permission denied.
  # set -e then stops the chain, so a failure here is not silently skipped.
  bash "$0" backup
  bash "$0" collect
  bash "$0" rebuild
  bash "$0" check
  say "Done"
  echo "   Next: paste me the output above, plus the result of"
  echo "   PYTHONPATH=src $PY scripts/verify_entry_points.py"
  ;;

*)
  sed -n '2,14p' "$0" | sed 's/^# \?//'
  exit 1
  ;;
esac
