# Hub auto-refresh

Nightly CRM sync runs on `launchd` at 07:13 weekdays. Pulls fresh PBR, stage,
close date, and CRM metadata for every opp listed in `deal-data.json` and
rebuilds the Closed Won FY aggregate, then commits and pushes if anything
changed. Source of truth is the homegrown CRM ("unicorn"), read through
BigQuery at `shopify-dw.sales` (Salesforce was retired 2026-07-01).

## Pieces

| File | Role |
|---|---|
| `scripts/refresh_deals.py` | Pure-stdlib Python. Queries the CRM via the `bq` CLI (subprocess + json), rewrites `deal-data.json`. |
| `scripts/refresh.sh` | Wrapper. Runs a `bq 'SELECT 1'` health check, runs the Python script, commits and pushes any diff. |
| `~/Library/LaunchAgents/com.mercedes.hub-refresh.plist` | launchd job. Fires the wrapper Mon-Fri at 07:13 local. |
| `refresh.log` | Per-run log. Git-ignored. |

## Data source

- **Main table:** `shopify-dw.sales.sales_opportunities_v2` (one row per opp, PK `opportunity_id`).
- **Revenue (PBR):** `shopify-dw.sales.sales_opportunity_products_revenue`, `SUM(total_projected_billed_revenue)` grouped by `opportunity_id`.
- **Owner filter:** `owner_id = '39432'` (the numeric prefix of the Vault user slug `39432-Mercedes-Boykin-Sabalones`).
- **Matching:** tracked deals match on CRM `opportunity_id` OR the legacy `salesforce_opportunity_id` bridge column. Once matched, `sf.id` is canonicalized to the CRM `opportunity_id`.
- **Stages:** stored as CRM tokens (`evaluate` / `propose` / `dealcraft` / `launch` / `closed_won` / `closed_lost`). Frontends map tokens → display labels and also accept legacy Salesforce stage names for any cached data.

## When CRM auth expires

Auth is Google Application Default Credentials (ADC), which auto-renews. If the
health check ever fails, the wrapper logs:
```
FATAL: CRM (BigQuery) health check failed. Run once: gcloud auth application-default login
```
Fix:
```bash
gcloud auth application-default login
```
Then nothing else — ADC keeps the launchd job working from then on.

## Manual ops

```bash
# Run once now
~/hub/scripts/refresh.sh

# See next scheduled firing + state
launchctl print gui/$(id -u)/com.mercedes.hub-refresh

# Trigger immediately under launchd's environment (for debugging plist quirks)
launchctl kickstart -k gui/$(id -u)/com.mercedes.hub-refresh

# Unload / reload after editing the plist
launchctl bootout gui/$(id -u)/com.mercedes.hub-refresh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.mercedes.hub-refresh.plist

# Tail the log
tail -f ~/hub/refresh.log
```

## Adding a new opp

1. Add the deal's CRM `opportunity_id` (or its legacy Salesforce Opp Id) under `deals.<slug>.sf.id` in `deal-data.json`.
2. The next nightly run picks up stage/close/PBR automatically and canonicalizes the id to the CRM `opportunity_id`.

## Notes

- `amount` and `merchant_intent` have no CRM equivalent; their existing values are preserved (never overwritten).
- Launch-target dates (B2B/Plus launch, target migration, go-live) are hand-edited planning fields and are never touched by the refresh.
- Laptop must be awake at 07:13 for the job to fire on its natural schedule. If it's asleep, launchd queues the run for wake.
