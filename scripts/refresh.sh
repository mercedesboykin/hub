#!/bin/bash
# Nightly hub refresh wrapper — invoked by launchd.
#
# Runs the Python CRM refresh script against BigQuery (shopify-dw.sales) and
# commits + pushes any changes. Logs everything to ~/hub/refresh.log. Auth is
# Google Application Default Credentials (ADC), which auto-renews — if the
# health check fails, logs a clear message and exits non-zero so launchd
# surfaces it.
set -uo pipefail

REPO="$HOME/hub"
LOG="$REPO/refresh.log"

# launchd inherits a minimal PATH. Put the tec toolchain (bq/gcloud) FIRST,
# then the usual bits.
export PATH="$HOME/.local/state/tec/toolchain/base_profile/bin:$HOME/.local/share/pnpm:$HOME/.local/state/tec/profiles/base/current/global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

stamp() { date "+%Y-%m-%d %H:%M:%S %Z"; }
log()   { echo "[$(stamp)] $*" >> "$LOG"; }

log "──────── refresh start ────────"
cd "$REPO" || { log "FATAL: cannot cd to $REPO"; exit 1; }

# 1. CRM health check — a trivial BigQuery that confirms bq is on PATH and ADC
#    is valid. If ADC has lapsed, one interactive login re-arms it for good.
if ! command -v bq >/dev/null 2>&1; then
  log "FATAL: bq CLI not on PATH — expected ~/.local/state/tec/toolchain/base_profile/bin"
  exit 1
fi

if ! bq query --project_id=shopify-dw --use_legacy_sql=false --format=json 'SELECT 1 AS ok' >/dev/null 2>>"$LOG"; then
  log "FATAL: CRM (BigQuery) health check failed. Run once: gcloud auth application-default login"
  exit 2
fi

# 2. Run the Python refresh.
log "Running refresh_deals.py against the CRM…"
if ! python3 "$REPO/scripts/refresh_deals.py" >> "$LOG" 2>&1; then
  log "FATAL: refresh_deals.py exited non-zero (see preceding output)"
  exit 3
fi

# 3. Commit + push if deal-data.json changed (this is the deploy step —
#    GitHub Pages serves the hub straight from the repo).
if git diff --quiet -- deal-data.json; then
  log "No deal-data.json changes — nothing to commit."
  log "──────── refresh end (no-op) ────────"
  exit 0
fi

git add deal-data.json
TS=$(date "+%Y-%m-%d")
git commit -m "Nightly CRM refresh ($TS)" >> "$LOG" 2>&1
git pull --rebase --autostash >> "$LOG" 2>&1
if git push >> "$LOG" 2>&1; then
  log "Pushed successfully."
else
  log "WARN: git push failed (see preceding output)"
fi

log "──────── refresh end ────────"
