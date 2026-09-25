#!/usr/bin/env bash
# THE ONE COMMAND. Run on the Mac that holds the tracking (~/panthers_projects) and is logged in to
# Databricks (`databricks auth login --host …`, profile "panthers"). It does everything and pushes
# only aggregates (runs/<stamp>/), never raw rows. If a stage fails, what exists so far is pushed too,
# so the next person reads the failure from the repo instead of a terminal.
#
#   bash scripts/first_run.sh                 # 2022–2025, smoke test first, then the full pass
#   SEASONS="2025" bash scripts/first_run.sh  # one season
#   SMOKE_ONLY=1 bash scripts/first_run.sh    # just the 2-game smoke test
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/Library/Python/3.12/bin:$HOME/.local/bin:$PATH"
export DATABRICKS_HOST="${DATABRICKS_HOST:-https://adb-7405617646104787.7.azuredatabricks.net}"
export DATABRICKS_CONFIG_PROFILE="${DATABRICKS_CONFIG_PROFILE:-panthers}"
export PANTHERS_DATA_DIR="${PANTHERS_DATA_DIR:-$HOME/panthers_projects}"
SEASONS="${SEASONS:-2022 2023 2024 2025}"
STAMP="$(date +%Y-%m-%d_%H%M)"
RUN="runs/$STAMP"
mkdir -p "$RUN"
log() { printf '\n== %s  (%s)\n' "$*" "$(date +%H:%M:%S)" | tee -a "$RUN/log.txt"; }
push() {  # commit whatever the run produced; aggregates only
  git add data_contracts/uc_inventory.json "$RUN" 2>/dev/null
  git -c user.name="first_run" -c user.email="analytics@panthers.nfl.com" commit -qm "run $STAMP: $1" 2>/dev/null && git push -q origin HEAD 2>/dev/null && log "pushed $RUN ($1)"
}
fail() { log "FAILED at: $1"; push "partial — failed at $1"; exit 1; }

log "pull + install"
git pull -q --ff-only || true
pip install -q -e . 2>&1 | grep -v -E 'WARNING|notice' | tail -1
POSHUB="python3 -m position_hub.cli"

log "probe"
$POSHUB probe --json "$RUN/probe.json" 2>&1 | tee "$RUN/probe.txt" || fail probe
grep -q FAIL "$RUN/probe.txt" && fail "probe (see $RUN/probe.txt)"

log "discover"
$POSHUB discover 2>&1 | tee "$RUN/discover.txt" || fail discover

log "smoke: 2 games of the latest season"
LAST="${SEASONS##* }"
$POSHUB --out out_smoke features --seasons "$LAST" --weeks 1 --max-games 2 --workers 2 2>&1 | tee "$RUN/smoke_features.txt" || fail "smoke features"
$POSHUB --out out_smoke summarize --run-dir "$RUN/smoke" 2>&1 | tail -n +1 > /dev/null || fail "smoke summarize"
push "probe + discover + 2-game smoke"
if [ "${SMOKE_ONLY:-0}" = "1" ]; then log "SMOKE_ONLY set, stopping"; exit 0; fi

log "features $SEASONS (the slow step)"
$POSHUB features --seasons $SEASONS 2>&1 | tee "$RUN/features.txt" || fail features
$POSHUB summarize --run-dir "$RUN" > /dev/null; push "features"

log "fit / score / mix"
$POSHUB fit --holdout-weeks 17 18 2>&1 | tee "$RUN/fit.txt" || fail fit
$POSHUB score 2>&1 | tee "$RUN/score.txt" || fail score
$POSHUB mix 2>&1 | tee "$RUN/mix.txt" || fail mix
cp out/gates.md out/model.json "$RUN/" 2>/dev/null
cp viewer/data/role_mix.json "$RUN/role_mix.json" 2>/dev/null   # player-season aggregates for the viewer
$POSHUB summarize --run-dir "$RUN" > /dev/null
push "complete: features + fit + score + mix + gates"
log "DONE — read $RUN/summary.md"
