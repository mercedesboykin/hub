# Hub auto-refresh

Nightly Salesforce sync runs on `launchd` at 07:13 weekdays. Pulls fresh
PBR, stage, close, intent, and last-modified for every opp listed in
`deal-data.json` and rebuilds the Closed Won FY aggregate, then commits
and pushes if anything changed.

## Pieces

| File | Role |
|---|---|
| `scripts/refresh_deals.py` | Pure-stdlib Python. Reads `SF_ACCESS_TOKEN` + `SF_INSTANCE_URL` from env, queries SF, rewrites `deal-data.json`. |
| `scripts/refresh.sh` | Wrapper. Pulls a fresh access token from the `sf` CLI session, runs the Python script, commits and pushes any diff. |
| `~/Library/LaunchAgents/com.mercedes.hub-refresh.plist` | launchd job. Fires the wrapper Mon-Fri at 07:13 local. |
| `refresh.log` | Per-run log. Git-ignored. |

## When SF auth expires (every few weeks)

The wrapper detects it and logs:
```
FATAL: sf CLI session expired or invalid. Run: sf org login web ...
```
Fix:
```bash
sf org login web --alias hub-refresh --instance-url https://banff.my.salesforce.com
```
Then nothing else — the launchd job uses the fresh session automatically.

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

1. Add the SF opp ID under `deals.<slug>.sf.id` in `deal-data.json`.
2. The next nightly run picks up stage/close/PBR/intent/amount automatically.

## Caveats

- Laptop must be awake at 07:13 for the job to fire on its natural schedule. If it's asleep, launchd queues the run for wake.
- The `sf` CLI's PlatformCLI refresh tokens can't be used outside the CLI (Shopify SF org policy) — so this can't be moved to GitHub Actions without a Connected App + JWT Bearer setup.
