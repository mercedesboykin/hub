#!/bin/bash
# Nightly hub refresh wrapper — invoked by launchd.
#
# Pulls a fresh SF access token from the sf CLI session, runs the Python
# refresh script, and commits + pushes any changes. Logs everything to
# ~/hub/refresh.log. If the sf session has expired, logs a clear message
# and exits non-zero so launchd surfaces it.
set -uo pipefail

REPO="$HOME/hub"
LOG="$REPO/refresh.log"

# launchd inherits a minimal PATH; rebuild the bits we need.
export PATH="$HOME/.local/share/pnpm:$HOME/.local/state/tec/profiles/base/current/global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

stamp() { date "+%Y-%m-%d %H:%M:%S %Z"; }
log()   { echo "[$(stamp)] $*" >> "$LOG"; }

log "──────── refresh start ────────"
cd "$REPO" || { log "FATAL: cannot cd to $REPO"; exit 1; }

# 1. Get a fresh access token from sf CLI.
if ! command -v sf >/dev/null 2>&1; then
  log "FATAL: sf CLI not on PATH — run: pnpm add -g @salesforce/cli"
  exit 1
fi

SF_JSON=$(sf org display --target-org hub-refresh --json 2>/dev/null)
if [[ -z "$SF_JSON" ]] || ! echo "$SF_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('result',{}).get('accessToken') else 1)"; then
  log "FATAL: sf CLI session expired or invalid. Run: sf org login web --alias hub-refresh --instance-url https://banff.my.salesforce.com"
  exit 2
fi

export SF_ACCESS_TOKEN=$(echo "$SF_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['accessToken'])")
export SF_INSTANCE_URL=$(echo "$SF_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['instanceUrl'])")

# 2. Run the Python refresh.
log "Running refresh_deals.py…"
if ! python3 "$REPO/scripts/refresh_deals.py" >> "$LOG" 2>&1; then
  log "FATAL: refresh_deals.py exited non-zero (see preceding output)"
  exit 3
fi

# 3. Commit + push if deal-data.json changed.
if git diff --quiet -- deal-data.json; then
  log "No deal-data.json changes — nothing to commit."
  log "──────── refresh end (no-op) ────────"
  exit 0
fi

git add deal-data.json
TS=$(date "+%Y-%m-%d")
git commit -m "Nightly SF refresh ($TS)" >> "$LOG" 2>&1
git pull --rebase --autostash >> "$LOG" 2>&1
if git push >> "$LOG" 2>&1; then
  log "Pushed successfully."
else
  log "WARN: git push failed (see preceding output)"
fi

log "──────── refresh end ────────"
