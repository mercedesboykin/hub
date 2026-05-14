# Sales Hub Blueprint

A personal sales operating system, hosted on GitHub Pages, that ties together:

- **Sales Dashboard** — current pipeline, week-at-a-glance calls, 3-tier forecast (⭐ Commit / ■ Best Case / ✓ Closed Won), Quarter Breakdown for Q1–Q4 of the current FY
- **Deal Review Room** — full MEDDIC + strategy + risks + done/left/manager questions for every active opp
- **MAP Hub** — index of all Mutual Action Plans + per-deal proposal/resource microsites
- **Auto-refreshed Salesforce data** — pulled via your own SF CLI auth (no special permits needed)
- **Multi-source MEDDIC enrichment** — Claude fans across every data source you have connected: call recordings (Fellow / Gong / Salesloft), Calendar attendees, Gmail threads, Drive docs/decks/RFPs, Slack mentions, and recent web news. The more tools your Claude has, the richer the draft

This blueprint is for **your Claude** to read. The `CLAUDE.md` next to it is the full spec — Claude reads it once and knows how to build, run, and maintain everything from scratch using your sources of truth (your Salesforce, your calendar, your Fellow meetings, your Gmail).

---

## What you need before starting

1. **A GitHub account** with the ability to create **two** public repos:
   - `<you>/hub` — your private dashboard (lock screen + dashboard + deal review + map hub index)
   - `<you>/maps` — prospect-facing microsites (one folder per deal, each with a proposal `index.html` + an editable MAP `map.html`)
2. **Salesforce CLI installed** and authenticated against your sandbox or production org. Test with `sf org list` — you should see a "Connected" row.
3. **Claude Code or Claude Desktop** with these MCP servers connected:
   - `tool-gateway` (for Calendar, Gmail, GitHub, Drive, Salesloft access)
   - `fellow-mcp` (for call summaries + transcripts → MEDDIC)
   - Optional: `playground-slack-mcp` if you live in Slack
4. **Python 3** available (system Python is fine; we'll set up a venv).

That's it. Everything else Claude will scaffold.

### Why two repos?

The hub repo is your operating system — it carries your real pipeline data and is gated by a single passcode. The maps repo is what you actually send to prospects — each deal lives at `https://<you>.github.io/maps/<deal-slug>/` (proposal) and `https://<you>.github.io/maps/<deal-slug>/map.html` (mutual action plan). Splitting them keeps your dashboards private from prospects and means a leaked MAP passcode never exposes other deals.

---

## Getting started

Open Claude Code in any folder and paste:

```
Set up my personal sales hub from this template repo: github.com/chasemccane/hub-template

Pull the full spec to disk first (don't use WebFetch — it summarizes long files):

  curl -fsSL https://raw.githubusercontent.com/chasemccane/hub-template/main/CLAUDE.md   -o /tmp/hub-CLAUDE.md
  curl -fsSL https://raw.githubusercontent.com/chasemccane/hub-template/main/BLUEPRINT.md -o /tmp/hub-BLUEPRINT.md

Then Read /tmp/hub-CLAUDE.md fully and follow the "⚡ Bootstrap mode" section. Batch your questions to me.
```

Claude will:

1. Ask for your GitHub username, the repo name you want, your SF CLI org alias, your full name + role, your preferred passcode, your accent color, and your quarter quotas.
2. Scaffold the file structure (`index.html`, `dashboard/`, `deal-review/`, `map-hub/`, `maps/`, `scripts/`, `deal-data.json`) by cloning patterns from the reference repo at [github.com/chasemccane/hub](https://github.com/chasemccane/hub) and substituting your branding.
3. Generate the three core HTML pages.
4. Pull your current open opportunities from Salesforce and seed `deal-data.json`.
5. For each opp, search Fellow for prior meetings → draft first-pass MEDDIC + done/left.
6. Help you commit + push + enable GitHub Pages.

Once Pages is live, you'll have a passcode-protected hub at `https://<your-github-username>.github.io/<repo-name>/`.

---

## Day-to-day workflows

Once the hub is running, the things you'll ask Claude to do:

### "Add a new opportunity called [Account Name]"
Claude will:
- Query SF for the Opportunity by name → grab Id, StageName, CloseDate, Projected_Billed_Revenue__c, CreatedDate
- **Fan out across every data source you have connected** (Fellow / Gong / Salesloft for calls, Calendar for attendees + cadence, Gmail for stakeholder threads, Drive for decks/RFPs/scoping docs, Slack for internal context, WebSearch for company news) → draft a first-pass MEDDIC. Report which sources contributed and which dimensions are still thin.
- Scaffold a new `maps/<slug>/` folder with **both** files: passcode-gated proposal (`index.html`) + editable MAP (`map.html`)
- Insert the deal into the DEALS array in all three HTML pages (dashboard, deal-review, map-hub)
- Append it to `deal-data.json` with the MEDDIC, strategy, and risks it drafted
- Commit + push the hub repo AND the maps repo

### "Refresh my pipeline"
Claude runs `scripts/refresh_deals.py` (pulls fresh SF stage/close/PBR for every deal in `deal-data.json`, **plus** all Closed-Won opps you own for the current FY, bucketed per quarter), commits, pushes.

### "Hub-wide refresh" (the everything-everywhere pass)
Claude pulls fresh data from every source you have connected — Salesforce, Fellow / Gong / Salesloft, Gmail, Calendar, Drive, Slack, WebSearch — in one workflow, cross-references everything against your active deals, surfaces changes (stage moves, new meetings, fresh email threads, news about the company), updates MEDDIC where there's signal, and commits. Use this on Monday mornings or before pipeline reviews.

### "Update MEDDIC on [deal] from the call I just had"
Claude finds the call across whichever recording tool you use (Fellow / Gong / Salesloft / Calendar event recap), pulls summary + targeted transcript chunks, also scans Gmail + Slack for post-call follow-up activity, **merges** updates into the MEDDIC + done/left items in `deal-data.json` (doesn't overwrite existing context), commits, pushes.

### "What's on my calendar this week and what calls do I need to prep for?"
Claude pulls calendar via `tool-gateway`, cross-references each meeting against your active deals, updates the CALLS array on the dashboard, surfaces prep items.

### "Remove [deal]"
Claude pulls it from all three HTML DEALS arrays, removes from `deal-data.json`, adds the id to `REMOVED_IDS` so any cached browser state purges it.

---

## What Claude does NOT touch

- **Salesforce writes.** All SF data is read-only. If you want to update an opp, you do it in SF — Claude reads it back next refresh.
- **Email/Slack sends.** Drafts only, by default. You review and send.
- **Calendar invites.** Read-only. Claude won't create/move/delete meetings unless you ask explicitly.

---

## Customizing

The defaults in `CLAUDE.md` describe the reference setup. Things you'll likely want to change first:

- **Passcode** for the lock screen (`0309` in the reference repo) — set during initial setup
- **Brand color / fonts** — reference uses Shopify green (`#00a86b`) with Inter; tell Claude your preference
- **Forecast quotas** — opp count + PBR quota for the current quarter
- **Your SE / Solutions Engineer name(s)** — appears in the deal cards
- **Salesforce instance URL** — your sandbox or prod org URL (e.g. `banff.lightning.force.com` or `yourcompany.lightning.force.com`)

Tell Claude any of these at setup time, or change them anytime.

---

## Reference repo

The canonical reference implementation is **[github.com/chasemccane/hub](https://github.com/chasemccane/hub)** (public). Your Claude can read it directly when scaffolding to copy CSS/HTML conventions verbatim. The `CLAUDE.md` tells your Claude to use this repo as the structural reference; you don't need to do anything special.

---

## Troubleshooting

- **"sdp-pii permit error" when Claude tries SF tools** — ignore the Revenue MCP route. Claude is instructed in `CLAUDE.md` to use your SF CLI auth only.
- **GitHub Pages stale** — deploys take 30-90s after push. Check `gh run list --repo <user>/<repo>` for the build status.
- **`deal-data.json` change didn't show up** — the hub pages cache localStorage. Bump the relevant VERSION constant or clear localStorage in DevTools.
- **MEDDIC field empty after Fellow pull** — Fellow only has summary content if the bot was in the meeting. For meetings without bot, Claude will fall back to your notes / calendar description.
- **Forecast stars not persisting** — the dashboard writes star changes back to `deal-data.json` via the GitHub Contents API. Requires a PAT in `localStorage['hub-gh-token']` (scope: `repo`). Set up via the dashboard's gear icon.

If something's broken, paste the error into Claude with the file path — it'll fix it.
