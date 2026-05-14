# Sales Hub — Operating Instructions for Claude

You are the maintainer of a personal sales hub hosted on GitHub Pages. This document is the authoritative spec for how the hub is structured, how data flows, what conventions to follow, and which workflows you run on the user's behalf.

Read this file fully before doing any work on the repo.

---

## ⚡ Bootstrap mode (read this FIRST)

**You are in bootstrap mode if ANY of these are true:**
- The user's prompt mentioned "bootstrap" / "set up" / "scaffold" the sales hub.
- The current working directory is NOT a scaffolded hub (no `~/hub` with `dashboard/index.html` etc.).
- You just fetched this file from `chasemccane/hub-template` (the source-of-truth lives at github.com/chasemccane/hub-template; if you're reading this file from anywhere else, the user has already scaffolded — operate in maintenance mode using the rest of this spec).

If bootstrap: your job is to take the user from empty machine to live hub at `https://<their-github>.github.io/hub/` in ~20–40 min (most of the time goes to SF queries + MEDDIC fan-out, which scales with their open-opp count). Ask the minimum, do everything else yourself.

**Step 1 — Preflight (run silently, then surface results).**
Run the CLI checks in parallel and report which are green/red. Then enumerate the MCP servers and tools available in this session — those are the data sources you'll use during scaffold and ongoing.

```bash
gh auth status            # GitHub CLI authed?
gh auth status 2>&1 | grep -i "scopes" || gh auth refresh -s repo,workflow  # need repo + workflow scopes
sf org list               # any "Connected" SF org? Note the alias.
python3 --version         # Python 3 present?
which gh && which sf      # CLIs on PATH?
```

**Required `gh` scopes:** the GitHub CLI token needs at minimum `repo` (to create the two repos + push), and ideally `workflow` (for enabling Pages programmatically via the API). If `gh auth status` doesn't show these, run `gh auth refresh -s repo,workflow` and ask the user to complete the browser flow before continuing.

**Then survey data sources.** Check which of these MCP tools you can actually call (some reps have none, some have all):

- **Salesforce** — direct via SF CLI (always required; this is the spine)
- **Fellow** (`mcp__fellow-mcp__*`) — call summaries + transcripts
- **Salesloft / Gong** (`mcp__revenue-mcp__search_salesloft_tool`) — call recordings, cadence activity, conversation intelligence
- **Calendar** (`mcp__tool-gateway__gws_calendar_*`) — past + upcoming meetings, attendee lists
- **Gmail** (`mcp__tool-gateway__gws_gmail_*`) — email threads with prospects
- **Drive** (`mcp__tool-gateway__gws_drive_*`, `gws_docs_*`) — proposal docs, design briefs, customer-shared files
- **Slack** (`mcp__tool-gateway__slack_*` or `mcp__playground-slack-mcp__*`) — DM threads, channels, search
- **WebSearch / WebFetch** — recent news / press releases / 10-Ks about the company
- **Revenue MCP** (`mcp__revenue-mcp__search_data_tool`) — Copilot enrichment, news data — only if sdp-pii permit is active; otherwise skip
- **Vault** (`mcp__vault-mcp__*`) — internal Shopify GSD/Mission context, useful for partner / mission tagging

Report to the user: "I have access to [Fellow, Calendar, Gmail, Drive, Slack, WebSearch]" so they know the coverage. Don't fail if some are missing — fewer sources just means thinner first-pass MEDDIC.

**Preflight failure modes — give the user the exact one-line fix and stop:**

- `gh auth status` not authed → `gh auth login` (pick GitHub.com, HTTPS, browser).
- `gh` token missing `repo` scope → `gh auth refresh -s repo,workflow`.
- `sf org list` shows no Connected org → `sf org login web --alias hub-refresh --instance-url https://<their-instance>.lightning.force.com` (ask the user for their SF instance URL).
- `python3 --version` < 3.9 → ask the user to install a recent Python (system Python 3 on macOS is fine; Linux varies).
- Missing MCP servers are non-blocking — only SF is required.

**Step 2 — Ask the user 5 questions in one batch** (use AskUserQuestion or a numbered list, depending on harness):

1. GitHub username (e.g. `jsmith`) — for the repo URLs
2. 4-digit passcode for the lock screen (e.g. `1234`)
3. Brand accent color (default: `#00a86b` Shopify green)
4. This-quarter PBR quota (e.g. `1,000,000`) and open-opp goal (e.g. `7`)
5. Your name + role title (e.g. `Jane Smith / Sr. Account Executive · B2B AMER`)

If they accept defaults on the color and quotas, that's fine — defaults are documented above.

Also check whether `~/hub` and `~/maps` already exist on disk. If either does, ask the user before touching it (they may already have an unrelated `~/maps` folder, or be re-running bootstrap).

**Step 3 — Initialize local repos (no remote yet).** We create the repos on GitHub at push time in Step 6 using `gh repo create --source=. --push`. This avoids the empty-remote-with-no-default-branch problem.

```bash
mkdir -p ~/hub ~/maps

cd ~/hub
git init -b main

cd ~/maps
git init -b main
# placeholder so the first push doesn't fail on an empty tree
printf '# Maps\n\nProspect-facing MAP + proposal microsites.\nOne folder per deal.\n' > README.md
```

**Step 4 — Scaffold the hub repo files.** Read each reference file from `chasemccane/hub`, then write the adapted version into `~/hub/`. Read with one of (use whichever is responsive — the raw URL is the fastest):

```bash
curl -fsSL https://raw.githubusercontent.com/chasemccane/hub/main/<path>
# fallback:
gh api repos/chasemccane/hub/contents/<path> --jq '.content' | base64 -d
```

**Files to scaffold (and the specific substitutions to make in each):**

| Source file | Substitutions |
|---|---|
| `index.html` (lock screen) | `const PASSCODE = '0309'` → user's passcode; brand circle initials → user's; `--accent` color CSS var → user's; AE name + role |
| `dashboard/index.html` | `--accent` → user's color; AE name; `FC_DEFAULTS.pbr_quota` → user's quota; `FC_DEFAULTS.opps_quota` → user's open-opp goal; **replace the entire `DEFAULT_DEALS` (or `DEALS`) array body with `[]`**; **replace `REMOVED_IDS` with `[]`**; replace `CALLS` array with `[]` |
| `deal-review/index.html` | Same substitutions: accent, name, **`DEFAULT_DEALS` → `[]`**, **`REMOVED_IDS` → `[]`** |
| `map-hub/index.html` | Accent, name, **replace the `DEALS` array body with `[]`** |
| `scripts/refresh_deals.py` | Copy verbatim — it reads `deal-data.json` and doesn't hardcode anyone's data |
| `BLUEPRINT.md`, `CLAUDE.md` | Copy from THIS template repo (`chasemccane/hub-template`), NOT from `chasemccane/hub` — the template versions are written for general use |

**Critical: strip Chase's deals.** The reference repo's `dashboard/index.html`, `deal-review/index.html`, and `map-hub/index.html` contain hardcoded arrays with Chase's real deals (Bulldog Tools, Nature's First, Washington Floral, Anatomy Warehouse, Ohio Power Tool, Vault CPS, Sourcebooks, etc.). Before writing the file to `~/hub/`, locate each of these arrays and replace their entire body with `[]`. After scaffolding, grep `~/hub/` for any of Chase's deal slugs (`bulldog-tools`, `natures-first`, `washington-floral`, `anatomy-warehouse`, `ohio-power-tool`, `vault-cps`, `source-books`, `feniex`, `hedrick`) and verify zero matches. If any slip through, fix and re-grep.

**Then write empty `deal-data.json`** to `~/hub/deal-data.json`:

```json
{
  "version": 2,
  "updated": null,
  "deals": {},
  "closed_won": {
    "fy": { "year": null, "count": 0, "pbr": 0 },
    "current_quarter": null,
    "quarters": {
      "Q1": { "year": null, "count": 0, "pbr": 0, "deals": [] },
      "Q2": { "year": null, "count": 0, "pbr": 0, "deals": [] },
      "Q3": { "year": null, "count": 0, "pbr": 0, "deals": [] },
      "Q4": { "year": null, "count": 0, "pbr": 0, "deals": [] }
    },
    "updated": null
  }
}
```

And copy a `.gitignore` (Python + secrets + editor cruft) — see this template's `.gitignore` for the canonical contents.

**Step 5 — Pull open Salesforce opportunities for this user.** Use the SF CLI route (see "Salesforce" section below). Query:

```sql
SELECT Id, Name, StageName, CloseDate, Projected_Billed_Revenue__c, CreatedDate,
       Account.Name, Account.Industry, Account.BillingCity, Account.BillingState
FROM Opportunity
WHERE IsClosed = false AND OwnerId = <current user's SF Id>
ORDER BY CloseDate
```

**`Projected_Billed_Revenue__c` is a Shopify-specific custom field.** If the user is on a non-Shopify org (or their org doesn't have this field), the query will return an `INVALID_FIELD` error. In that case:
1. Surface the error to the user verbatim.
2. Ask which numeric field on their Opportunity object represents the deal size (common alternatives: `Amount`, `ExpectedRevenue`, custom ARR/MRR fields).
3. Swap that field name into the SOQL and into `scripts/refresh_deals.py` (search for `Projected_Billed_Revenue__c` and replace globally in the script).

Same handling for `StageName` values — if the user's stage labels differ from the reference set (Pre-Qualified / Envision / Solution / Demonstrate / Closed Won / Closed Lost), update the `STAGE_MAP` in `scripts/refresh_deals.py` accordingly.

For each opp, generate a slug, then **fan out to every data source enumerated in Step 1** to assemble the richest possible first-pass MEDDIC (see "Multi-source MEDDIC enrichment" below for the cross-source recipe). Add to `deal-data.json` AND to the hardcoded `DEALS` / `DEFAULT_DEALS` arrays in all three HTML files. Surface a summary table BEFORE pushing showing: deal name, stage, close, PBR, MEDDIC coverage (which sources contributed), and a flag for thin qualification (< 12 / 24). Let the user drop opps or pull deeper on any deal before you commit.

**Step 6 — First commit + create remote + push + enable Pages.**

```bash
cd ~/hub
git add -A
git commit -m "Initial hub scaffold for <user>"
gh repo create <user>/hub --public --source=. --remote=origin --push \
  --description "Personal sales hub"
gh api -X POST repos/<user>/hub/pages \
  -f source[branch]=main -f source[path]=/

cd ~/maps
git add -A
git commit -m "Initial maps scaffold for <user>"
gh repo create <user>/maps --public --source=. --remote=origin --push \
  --description "Prospect-facing MAP + proposal microsites"
gh api -X POST repos/<user>/maps/pages \
  -f source[branch]=main -f source[path]=/
```

If `gh repo create` errors with "name already exists", ask the user — they may have a pre-existing repo to either reuse (in which case `git remote add origin git@github.com:<user>/<repo>.git && git push -u origin main`) or pick a different name. Don't auto-overwrite.

If the Pages POST returns 409 ("Pages already enabled"), that's fine — ignore.

**Step 7 — Surface the live URL** and tell the user the build takes 30–90s. Suggest they bookmark `https://<user>.github.io/hub/` and try the passcode. Stop there; don't lecture.

If they want the dashboard's forecast-star writes to persist to `deal-data.json`, point them at the dashboard's gear icon to paste a GitHub PAT (scope: `repo`) — that gets stored in `localStorage['hub-gh-token']` and authorizes the Contents API writes. Without it, stars work in-session only.

**After bootstrap completes**, the rest of this file is the spec for ongoing maintenance — adding deals, refreshing pipeline, MEDDIC enrichment, etc.

---

## Common bootstrap failure modes

A reference of what tends to go wrong, mapped to the fix. Surface the specific symptom + fix to the user; don't try increasingly clever workarounds.

| Symptom | Likely cause | Fix |
|---|---|---|
| `gh: command not found` | GitHub CLI not installed | Install `gh` per their OS (`brew install gh` on macOS) then `gh auth login` |
| `gh repo create` → "GraphQL: Resource not accessible by integration" | Token missing `repo` scope | `gh auth refresh -s repo,workflow` |
| `gh repo create` → "name already exists" | Repo exists from a prior attempt or unrelated project | Ask user to pick a different name OR reuse existing repo (manual `git remote add origin` + `git push -u`) |
| `sf org list` shows no Connected org | SF CLI not authed | `sf org login web --alias hub-refresh --instance-url <their-instance>` |
| `SF_ACCESS_TOKEN` empty after `sf org display` | Wrong alias or session expired | Re-auth with `sf org login web --alias hub-refresh ...` |
| SOQL query → `INVALID_FIELD: Projected_Billed_Revenue__c` | Non-Shopify SF org | Swap to `Amount` (or whatever their field is) in the SOQL + `refresh_deals.py` |
| SOQL query → `INSUFFICIENT_ACCESS` on `OwnerId = <id>` | User-id detection failed | Run `sf org display --target-org hub-refresh --json` and grab `result.username`; query `WHERE Owner.Username = '<username>'` instead |
| `gh api ... /pages` → 422 "Custom theme not found" or similar | Pages already enabled with different settings | Ignore — Pages will deploy on the existing config |
| Pages site shows 404 after push | Deploy still in flight | Wait 30–90s; check `gh run list --repo <user>/hub --limit 3` |
| Lock screen accepts any passcode | Forgot to substitute `PASSCODE` in `index.html` | Re-edit `~/hub/index.html`, grep for `PASSCODE = '0309'`, replace with user's, push |
| Chase's deals visible on dashboard after bootstrap | Forgot to strip `DEFAULT_DEALS` array body | Grep `~/hub/` for `bulldog-tools` (or any other Chase slug); zero matches expected. If non-zero, re-scaffold those files. |
| Forecast stars don't persist on click | No GitHub PAT in `localStorage['hub-gh-token']` | Tell user to use the dashboard's gear icon to paste a PAT (scope: `repo`) |

---

## What this hub is

A passcode-gated personal sales operating system. Five page types:

1. **`index.html`** — Lock screen + landing page. Single passcode. Once unlocked, surfaces top-level nav.
2. **`dashboard/index.html`** — Sales dashboard: pipeline cards, week-at-a-glance calls, 3-tier forecast (Closed Won / Commit / Best Case), Quarter Breakdown for Q1–Q4 of current FY.
3. **`deal-review/index.html`** — Per-deal review room: MEDDIC, strategy, risks, done/left, notes, manager Q&A. Edits write to `deal-data.json`.
4. **`map-hub/index.html`** — Index of all Mutual Action Plans. Cards link out to `<user>/maps/<slug>/` microsites.
5. **`<user>/maps/<slug>/`** (in a **separate** repo) — Per-deal prospect-facing files: `index.html` (proposal) + `map.html` (editable MAP). Passcode-gated, branded to the deal.

A single JSON file (`deal-data.json`) is the canonical store for everything dynamic in the hub. The HTML pages have a hardcoded `DEALS` (or `DEFAULT_DEALS`) array as a seed, then overlay fresh SF data + user-edited fields from `deal-data.json` at page load.

---

## Two-repo architecture

This system uses **two separate GitHub repos** that deploy to two separate Pages sites:

1. **Hub repo** (e.g. `<user>/hub` → `<user>.github.io/hub/`) — the AE-only operating system: lock screen, dashboard, deal review, map hub index.
2. **Maps repo** (e.g. `<user>/maps` → `<user>.github.io/maps/`) — prospect-facing microsites, one folder per deal. Each deal gets **two files**: a proposal (`index.html`) and an editable mutual action plan (`map.html`). Both share one passcode.

The hub repo holds your private data and links *out* to the maps repo. The maps repo is what you send to prospects.

```
~/hub/                            ← hub repo (private dashboards)
├── index.html                    # Lock screen
├── dashboard/index.html          # Pipeline + calls + 3-tier forecast + Quarter Breakdown
├── deal-review/index.html        # MEDDIC review room
├── map-hub/index.html            # MAP index (cards link to ~/maps/<slug>/)
├── scripts/
│   └── refresh_deals.py          # Pulls SF data → writes deal-data.json (incl. Closed Won aggregate)
├── deal-data.json                # Canonical dynamic store
├── BLUEPRINT.md                  # Coworker-facing overview
└── CLAUDE.md                     # This file

~/maps/                           ← maps repo (prospect-facing microsites)
├── <slug-1>/
│   ├── index.html                # Proposal / resource microsite (the "why Shopify" story)
│   └── map.html                  # Mutual Action Plan (editable milestones, actions, questions)
├── <slug-2>/
│   ├── index.html
│   └── map.html
└── ...
```

**Hub `DEALS` entries reference both maps files:**

```js
{
  id: 'example-account',
  ...
  map_url:      'https://<user>.github.io/maps/example-account/map.html',  // MAP
  proposal_url: 'https://<user>.github.io/maps/example-account/',          // proposal
}
```

---

## Data flow

```
Salesforce ──[scripts/refresh_deals.py]──► deal-data.json (sf fields + closed_won aggregate)
                                              │
Fellow MCP ──[your Claude tool calls]────────►│ (meddic, done, left, notes)
Calendar ───[your Claude tool calls]─────────►│ (last_call, next_call, CALLS array on dashboard)
                                              │
GitHub Pages ◄──[git push]── deal-data.json + HTML files
       │
       ▼
   Browser fetches deal-data.json on page load
       │
       ▼
   `applyRemoteData(data)` overlays SF + MEDDIC + edits onto the hardcoded DEFAULT_DEALS seed
```

The hardcoded `DEALS` array in each HTML page is the **structural** record (id, name, industry, SE, urls). The `deal-data.json` is the **dynamic** record (current stage/close/PBR, MEDDIC content, strategy, risks, done, left, notes, forecast tier, Closed Won aggregates).

When you add a deal: update **both** (HTML hardcoded + `deal-data.json`).
When you refresh SF: update **only** `deal-data.json`.
When you edit MEDDIC/strategy/risks: update **only** `deal-data.json`.

---

## `deal-data.json` schema

```json
{
  "version": 2,
  "updated": "2026-05-13T14:30:00Z",
  "deals": {
    "<deal-id>": {
      "sf": {
        "id": "006OG00000XXXXXYYYY",
        "pbr": 323170,
        "stage": "Demonstrate",
        "close": "2026-06-17",
        "created": "2026-03-26"
      },
      "meddic": {
        "metrics": "free text — KPIs, ROI numbers, success criteria",
        "economic_buyer": "Who signs. Title + name. Note risk if unconfirmed.",
        "decision_criteria": "Their stated requirements + how they'll evaluate",
        "decision_process": "Steps + timeline + who's involved",
        "pain": "The why-now. Quantified where possible.",
        "champion": "Internal advocate + their motivation"
      },
      "strategy": "free-text play summary — how we win this deal",
      "risks": [
        { "sev": "high|med|low", "text": "short summary", "mit": "mitigation plan" }
      ],
      "done": ["completed milestone 1", "completed milestone 2"],
      "left": ["pending milestone 1", "pending milestone 2"],
      "notes": "free-text scratchpad",
      "last_call": "free-text summary of most recent meaningful touch",
      "next_call": "what's next + when",
      "manager_q": "questions for the manager 1:1",
      "forecast": "commit | bestcase | null"
    }
  },
  "closed_won": {
    "fy": { "year": 2026, "count": 3, "pbr": 850000 },
    "current_quarter": 2,
    "quarters": {
      "Q1": { "year": 2026, "count": 1, "pbr": 200000, "deals": [...] },
      "Q2": { "year": 2026, "count": 2, "pbr": 650000, "deals": [...] },
      "Q3": { "year": 2026, "count": 0, "pbr": 0, "deals": [] },
      "Q4": { "year": 2026, "count": 0, "pbr": 0, "deals": [] }
    },
    "updated": "2026-05-13T14:30:00Z"
  }
}
```

All fields except `sf` and `closed_won` are user-editable. `sf` is overwritten by `refresh_deals.py`. `closed_won` is built by the same script from a separate SF query (Owner = current user, StageName = 'Closed Won', CloseDate >= start of FY).

The `forecast` field on each deal is set by the user clicking the ⭐ Commit / ■ Best Case toggle on the dashboard's Quarter Breakdown card. Star writes go through the GitHub Contents API (requires `localStorage['hub-gh-token']`).

---

## HTML conventions (read before scaffolding)

### Lock screen pattern (`index.html`)
- Numeric numpad keypad, 4-digit passcode
- Stored in a JS const at the top: `const PASSCODE = '0309';` — set at setup time per user preference
- On success: `sessionStorage.setItem('hub-auth', '1')` and redirect or show nav
- Other pages check `sessionStorage.getItem('hub-auth') === '1'` on load; redirect to `/` if not

### Page conventions
- Font: **Inter** (sans), optionally **Playfair Display** for MAP pages
- Theme: pick one accent color (reference uses `#00a86b` green); apply consistently across all pages
- Light mode by default; dark backgrounds for hero/lock sections
- Card-grid layout for deals on dashboard + map-hub
- Tab-based interface for deal-review (one tab per deal, sticky tab bar)

### The seed + overlay pattern (CRITICAL)
Every page has this shape:

```js
// 1. Hardcoded seed — every deal you actively track
const DEFAULT_DEALS = [
  { id:'example-account', name:'Example Account', industry:'...', stage:'Demonstrate',
    close:'2026-06-17', pbr:323170, se:'Your SE',
    map_url:'https://<user>.github.io/maps/example-account/map.html',
    proposal_url:'https://<user>.github.io/maps/example-account/',
    sf_url:'https://...lightning.../006.../view',
    created:'2026-03-26',
    forecast: null,  // 'commit' | 'bestcase' | null
    meddic: { metrics:'', economic_buyer:'', decision_criteria:'',
              decision_process:'', pain:'', champion:'' },
    strategy: '', risks:[], done:[], left:[], notes:''
  },
  // ...
];

// 2. Working copy
let DEALS = JSON.parse(JSON.stringify(DEFAULT_DEALS));

// 3. Remote fetch + overlay
async function init() {
  const remote = await fetchRemote();          // GETs deal-data.json
  if (remote) applyRemoteData(remote);         // overlays sf + meddic + edits + forecast
  render();
}

function applyRemoteData(data) {
  if (!data || !data.deals) return;
  DEALS.forEach(d => {
    const r = data.deals[d.id];
    if (!r) return;
    if (r.sf) {
      if (r.sf.pbr !== undefined) d.pbr = r.sf.pbr;
      if (r.sf.stage) d.stage = r.sf.stage;
      if (r.sf.close) d.close = fmtISODate(r.sf.close);
      if (r.sf.created) d.created = r.sf.created;
    }
    if (r.meddic)                  d.meddic    = r.meddic;
    if (r.strategy !== undefined)  d.strategy  = r.strategy;
    if (r.risks)                   d.risks     = r.risks;
    if (r.done)                    d.done      = r.done;
    if (r.left)                    d.left      = r.left;
    if (r.notes !== undefined)     d.notes     = r.notes;
    if (r.last_call !== undefined) d.last_call = r.last_call;
    if (r.next_call !== undefined) d.next_call = r.next_call;
    if (r.manager_q)               d.manager_q = r.manager_q;
    if (r.forecast !== undefined)  d.forecast  = r.forecast;
  });
}
```

### `REMOVED_IDS` pattern
Browsers cache prior versions in `localStorage`. When you remove a deal, also add its id to a `REMOVED_IDS` array near the bottom of the page so cached state is filtered out on load:

```js
const REMOVED_IDS = ['old-deal-1', 'closed-lost-deal-2'];
const saved = JSON.parse(raw).filter(d => !REMOVED_IDS.includes(d.id));
```

### Version-bump pattern for forecast quotas
The forecast widget on the dashboard stores quota goals in localStorage. Bump `FC_VERSION` when defaults change to force-overwrite cached values:

```js
const FC_KEY = 'hub-forecast';
const FC_VERSION = 3;
const FC_DEFAULTS = { opps_quota: 7, pbr_quota: 1041000, v: FC_VERSION };
let fc = Object.assign({}, FC_DEFAULTS);
const raw = localStorage.getItem(FC_KEY);
if (raw) {
  const stored = JSON.parse(raw);
  if ((stored.v || 0) < FC_VERSION) {
    fc = { ...FC_DEFAULTS,
           opps_quota: stored.opps_goal || stored.opps_quota || FC_DEFAULTS.opps_quota,
           pbr_quota:  stored.pbr_quota || FC_DEFAULTS.pbr_quota };
  } else {
    fc = { ...FC_DEFAULTS, ...stored };
  }
}
```

`FC_VERSION 3` dropped legacy `opps` / `pbr` running totals — star-driven forecast totals are now derived live from `DEALS[i].forecast`, so only quota goals persist.

### Edit-and-save pattern (deal-review + forecast stars)
Deal review and the dashboard's forecast stars write back to `deal-data.json` via the GitHub Contents API:

1. User edits a field in the UI (or clicks a star).
2. JS builds the full updated JSON object.
3. Pushes via `PUT /repos/{owner}/{repo}/contents/deal-data.json` with the cached `sha`.
4. On 200, refreshes `sha` from response.
5. GitHub Pages picks up the change in 30-90s.

A user-supplied GitHub PAT (stored in `localStorage` under `hub-gh-token`) is required to write. Read uses the public raw URL — no auth needed.

---

## Dashboard — 3-tier forecast + Quarter Breakdown

The dashboard surfaces **two** stacked cards:

### Card 1 — Total Open Pipeline + Closed-Won FY
- Big number: total open-deal count + total PBR
- Right-side sidecar: "Closed-Won FY\<year\>" — count + PBR for all Closed Won deals you own this FY, sourced from `data.closed_won.fy`

### Card 2 — My Quarter Forecast (3 stacked tiers, current quarter only)
- **✓ Closed Won · Q\<n\>** — count + PBR from `data.closed_won.quarters['Q' + cq.q]`
- **⭐ Commit · Feel Great** — sum of all deals where `d.forecast === 'commit'` AND `quarterOf(d.close) === cq.q`
- **■ Best Case · Have a Shot** — sum of all deals where `d.forecast === 'bestcase'` AND `quarterOf(d.close) === cq.q`

Quota progress bars show `(won) / quota`, `(won + commit) / quota`, and total pipeline / quota. PBR quota is editable inline (contenteditable span, parsed on blur).

### Quarter Breakdown card
Always renders **Q1–Q4 of the current FY**, even quarters with no deals. Each quarter is a collapsible row showing:
- Open deals closing in that quarter, with per-deal ⭐ / ■ star toggle buttons
- Closed-Won deals from `data.closed_won.quarters['Q' + n].deals[]` for past quarters
- Empty-state copy ("No deals in this quarter") when both lists are empty

The current quarter is highlighted and open by default; past quarters are dimmed (`opacity: .65`).

### Forecast tier helper
Normalize the per-deal forecast field:

```js
function forecastTier(d) {
  const f = d.forecast;
  if (f === 'commit' || f === 'bestcase') return f;
  return null;
}
```

### Current-quarter helper
Shopify FY = calendar year, so:

```js
function currentQuarter() {
  const now = new Date();
  return { q: Math.floor(now.getMonth() / 3) + 1, year: now.getFullYear() };
}
function quarterOf(dateStr) {
  const d = new Date(dateStr);
  return { q: Math.floor(d.getMonth() / 3) + 1, year: d.getFullYear() };
}
```

---

## Salesforce — the SF CLI route (NEVER use sdp-pii)

The user has authenticated their own SF CLI under an alias (default suggestion: `hub-refresh`). **Always use this route**. Do not call `mcp__revenue-mcp__search_salesforce_tool` or `mcp__revenue-mcp__search_data_tool` for hub data — the sdp-pii CloudDo permit is unreliable across sessions.

### Setup (one-time)
```bash
# User authenticates their own org
sf org login web --alias hub-refresh --instance-url https://yourcompany.lightning.force.com
sf org list  # confirm "Connected"

# Set up Python venv for simple-salesforce
python3 -m venv /tmp/sfvenv
/tmp/sfvenv/bin/pip install simple-salesforce requests
```

### Pulling SF data
```bash
sf org display --target-org hub-refresh --json > /tmp/sf-org.json
export SF_ACCESS_TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/sf-org.json'))['result']['accessToken'])")
export SF_INSTANCE_URL=$(python3 -c "import json; print(json.load(open('/tmp/sf-org.json'))['result']['instanceUrl'])")
/tmp/sfvenv/bin/python scripts/refresh_deals.py
```

The script in `scripts/refresh_deals.py` is the canonical template — it queries each tracked deal by Id **and** runs a second query for all your Closed Won opps in the current FY (bucketed per quarter). See the file itself for the full SOQL.

### Ad-hoc SF queries (finding a missing Opp Id, etc.)
```bash
# Export env vars first (see above), then:
/tmp/sfvenv/bin/python -c "
import os
from simple_salesforce import Salesforce
sf = Salesforce(session_id=os.environ['SF_ACCESS_TOKEN'], instance_url=os.environ['SF_INSTANCE_URL'])
r = sf.query(\"SELECT Id, Name, StageName FROM Opportunity WHERE Name LIKE '%Anatomy%' AND IsClosed = false\")
for rec in r['records']: print(rec['Id'], '|', rec['Name'], '|', rec['StageName'])
"
```

---

## Multi-source MEDDIC enrichment

MEDDIC drafting is **never single-source**. Every time you draft or refresh MEDDIC for a deal, fan out across every data source available in this session (the list you enumerated in Step 1 of bootstrap, or that you've discovered since). Different sources surface different MEDDIC dimensions — leaning on just one leaves gaps.

### Source-to-MEDDIC mapping

This is the playbook. For each MEDDIC field, the most reliable sources are listed first; skip sources you don't have access to.

| MEDDIC field | Best sources |
|---|---|
| **Metrics** (KPIs, ROI, success criteria) | Call recordings (Fellow/Gong/Salesloft transcripts) → Drive (RFPs, scoping docs) → Email threads quoting numbers → Salesforce notes/activity → WebSearch for public revenue/employee counts |
| **Economic Buyer** | Calendar attendees on later-stage meetings (titles + seniority) → Salesforce contacts (decision-maker role flags) → LinkedIn (via WebFetch) → Email signature blocks → Slack mentions ("CEO wants to see…") |
| **Decision Criteria** | RFPs/scoping docs in Drive → Call summaries listing requirements → Email asks ("can you confirm X works?") → Salesforce custom fields if your org tracks criteria |
| **Decision Process** | Calendar cadence (how often they meet, who joins) → Call transcripts where prospect describes their eval process → Salesloft cadence activity → Drive timeline docs |
| **Paper Process** | Call transcripts mentioning legal review / procurement / security review → Email threads with redlines → Drive (MSAs, NDAs already shared) |
| **Identify Pain** | Call transcripts (quotes are gold — pull verbatim) → Recent company news (layoffs, missed earnings, leadership changes → WebSearch) → Slack/email mentions of urgency or deadlines |
| **Champion** | Highest meeting frequency in Calendar → who replies fastest in Gmail → who's tagged in Slack threads → Fellow/Gong "engagement scores" if available → who asks for materials |
| **Competition** | Call transcripts ("we're also looking at X") → Drive (RFPs listing vendors) → WebSearch for press releases naming competitors → Salesloft notes |

### Available data sources & how to use them

Use whichever of these is connected in the user's session. Always probe before committing to a workflow — if a tool 404s or returns auth errors, skip it gracefully and note the gap.

**Salesforce** (always available; spine of the system)
- Activity history on the Opp (`Task`, `Event` objects) — past calls, emails logged, notes
- Contacts on the Account with roles + titles
- Opportunity Contact Roles (decision-maker flags)
- Account/Opp custom fields your org uses

**Fellow** (`mcp__fellow-mcp__*`)
- `search_meetings(title="<account>", from_date=..., has_summary=true)` to discover meetings
- `get_meeting_summary(meeting_ids=[...])` for key points + action items
- `get_meeting_transcript(meeting_id, start_time, end_time)` for direct quotes — pull 5-min windows around relevant moments, not the full transcript

**Salesloft / Gong** (`mcp__revenue-mcp__search_salesloft_tool`)
- `resource_type="calls"` with `filters={"to": "<phone>"}` or by contact — call recordings + conversation intelligence
- `resource_type="conversations"` with `extensive=true` + an id — full conversation breakdown (topics, sentiment, action items)
- `resource_type="activities"` — cadence touches, emails sent, calls logged

**Calendar** (`mcp__tool-gateway__gws_calendar_*` or `gws_calendar_list`)
- Pull last 90 days + next 30 days. Filter events to those with prospect-domain attendees.
- Use attendee titles (if in profile) to infer Economic Buyer candidates.
- Cadence pattern is itself a signal: weekly calls = high engagement; monthly = casual.

**Gmail** (`mcp__tool-gateway__gws_gmail_search`)
- `from:<champion-email> after:<deal-created-date>` — pull threads with the champion
- Search `subject:<account-name>` for any cross-team threads
- Look for redline / contract / legal mentions for Paper Process
- Don't dump full email bodies into MEDDIC — extract claims, cite the sender + date

**Drive** (`mcp__tool-gateway__gws_drive_search` + `gws_docs_read` / `gws_sheets_read`)
- Search Drive for the account name → pull any decks, scoping docs, RFPs, mutual NDAs
- For Google Docs/Sheets, read content to extract Decision Criteria + Metrics
- For uploaded PDFs/.docx, use `gws_drive_import_office_file` first if needed

**Slack** (`mcp__tool-gateway__slack_search_*` or `mcp__playground-slack-mcp__*`)
- Call `slack_who_am_i` first (system constraint)
- `slack_search_public(query="<account>")` for any team channels discussing the deal
- DM history with internal stakeholders (SE, Plus support, partner managers) — surfaces internal context the user might've forgotten

**WebSearch / WebFetch**
- Recent news about the company (acquisitions, layoffs, leadership changes, funding) — moves Pain and Decision Process
- LinkedIn (via WebFetch) for stakeholder titles + tenure
- 10-K / annual reports for public companies — Metrics gold

**Vault** (`mcp__vault-mcp__*`) — internal Shopify only
- Useful for tagging deals to Missions / Products / Themes
- Find internal docs about similar deals or vertical strategy

### Workflow: "Add a new opportunity — \<Account Name\>"

1. **Salesforce first.** Look up the Opp by name (with `IsClosed = false`). If multiple matches, ask the user. Extract Id, stage, close, PBR, created, account industry/location.
2. **Fan out across every available source IN PARALLEL** for that account:
   - Fellow / Salesloft / Gong: any meetings, calls, or transcripts in the last 90 days
   - Calendar: past + upcoming events with prospect-domain attendees
   - Gmail: recent threads (`subject:<account>` OR `from:@<prospect-domain>`)
   - Drive: any docs/decks/RFPs mentioning the account
   - Slack: team mentions of the deal
   - WebSearch: recent news about the company
3. **Synthesize.** Build the MEDDIC draft using the source-to-field map above. Don't paste raw content — extract claims, quote sparingly, attribute to source ("per the 4/22 call with Lori" / "per the RFP shared 5/3").
4. **Surface coverage.** Tell the user which sources contributed and which were empty. Flag dimensions still scoring < 2 / 3.
5. **Confirm before pushing.** Draft MEDDIC is a recommendation; user accepts/edits before commit.

### Workflow: "Update MEDDIC on \<deal\> from the call I just had"

1. Find the call across all available sources (Fellow → Salesloft → Calendar event ID → Gmail meeting recap email).
2. Pull the summary + targeted transcript chunks where MEDDIC dimensions are thin.
3. **In parallel,** check Gmail and Slack for follow-up activity since the call — sometimes the most valuable signal is what happened AFTER the call.
4. Read existing MEDDIC. **Merge, don't overwrite.** New info appends; existing claims stay unless directly contradicted.
5. Update `meddic`, append to `done`, prune `left`, update `last_call` and `next_call`.
6. Surface a one-paragraph diff. Wait for confirmation if it materially changes strategy or risks.
7. Commit + push.

### Workflow: "Hub-wide refresh" (the everything-everywhere pass)

When the user says "hub refresh" / "refresh everything" / "Monday refresh", run a multi-source sweep:

1. **Salesforce** — Run `scripts/refresh_deals.py`. Captures stage moves, close-date slips, PBR changes, Closed Won aggregates.
2. **Calendar** — Pull next 7 days. Cross-reference to active deals. Update the dashboard CALLS array.
3. **Fellow + Salesloft/Gong** — For each active deal, check for new call summaries since the deal's `last_call`. Flag any with material updates.
4. **Gmail** — Search for recent threads from active-deal stakeholders (use champion + economic buyer emails from MEDDIC). Flag movement.
5. **Drive** — Search for new docs with prospect names in the title (decks, scoping, RFPs).
6. **Slack** — Search for active-deal mentions in team channels since last refresh.
7. **WebSearch** — One query per deal for recent news (`<account name> announcement OR layoffs OR funding OR earnings`).

Bundle findings into a single summary message ("Stage changes: X. New meetings: Y. Notable emails: Z. News: W."). Single commit, descriptive message: `Hub-wide refresh from <sources used> (YYYY-MM-DD)`.

---

## Outbound communication — drafts only

For ANY email, Slack message, or external touch: **draft only, never send.** Use `gws_gmail_create_draft`, `slack_send_message_draft`, or equivalent. The user reviews and sends from their own client. This is non-negotiable across all tools.

---

## Commit + push conventions

- After every meaningful change to the hub repo: `git add` the specific files → `git commit -m "<short message>"` → `git pull --rebase` → `git push`.
- Do not batch unrelated changes into one commit. One workflow = one commit.
- GitHub Pages takes 30-90 seconds to redeploy. If the user asks "is it live?", check with:
  ```bash
  gh run list --repo <user>/<repo> --limit 3
  curl -s "https://raw.githubusercontent.com/<user>/<repo>/main/deal-data.json" | head -c 200
  ```

---

## Workflows in detail

### Initial setup (first time only)

1. Ask user: GitHub username, repo name, SF CLI alias, full name, role, passcode preference, theme color, quarter PBR quota + opp count goal, SE name(s).
2. Create the repo on GitHub:
   ```bash
   gh repo create <user>/<repo> --public --description "Personal sales hub"
   ```
3. Scaffold the file structure (see "File structure" above). Use the reference repo [github.com/chasemccane/hub](https://github.com/chasemccane/hub) to copy CSS / HTML conventions verbatim where possible (lock screen, dashboard cards + forecast + Quarter Breakdown, deal review tabs, MAP hub grid). Substitute the user's branding (color, name, passcode).

   Useful files to read from the reference repo via `mcp__tool-gateway__grokt_get_file` or `gh api`:
   - `index.html` — lock screen + passcode pattern
   - `dashboard/index.html` — deal cards, CALLS array, 3-tier forecast, Quarter Breakdown
   - `deal-review/index.html` — tab pattern, MEDDIC UI, applyRemoteData + REMOVED_IDS
   - `map-hub/index.html` — MAP card grid + stage integer mapping
   - `scripts/refresh_deals.py` — SF data refresh (+ Closed Won aggregate)
   - `deal-data.json` — schema reference

4. Pull all open opportunities from SF:
   ```sql
   SELECT Id, Name, StageName, CloseDate, Projected_Billed_Revenue__c, CreatedDate, Account.Name,
          Account.Industry, Account.BillingCity, Account.BillingState
   FROM Opportunity
   WHERE IsClosed = false AND OwnerId = <user's SF user id>
   ```
5. For each opp:
   - Generate a slug from the account name (lowercase, hyphens, no special chars)
   - Build the entry for the hardcoded DEALS array (id, name, industry, stage, close, pbr, se, sf_url, created, forecast: null)
   - Search Fellow for prior meetings → draft MEDDIC
   - Add to `deal-data.json`
6. Commit + push everything.
7. Enable GitHub Pages:
   ```bash
   gh api -X POST repos/<user>/<repo>/pages -f source[branch]=main -f source[path]=/
   ```
8. Surface the live URL to the user.

### Add a new opportunity

1. User: "Add a new opp — \<Account Name\>"
2. Look up in SF by account name + open status. If multiple matches, ask the user to disambiguate.
3. Extract the SF fields. Generate a slug.
4. Search Fellow for prior meetings (last 30 days). Draft MEDDIC.
5. Build the new `DEALS` array entry. **Append it to all three** HTML files:
   - `dashboard/index.html` → `DEALS` array
   - `deal-review/index.html` → `DEFAULT_DEALS` array
   - `map-hub/index.html` → deal card object in the cards array
6. Add to `deal-data.json` under `deals.<slug>` with `sf`, `meddic`, `strategy`, `risks: []`, `done: []`, `left: []`, `notes: ''`, `forecast: null`.
7. **Always scaffold BOTH files in the maps repo** — never optional:
   - `~/maps/<slug>/index.html` (proposal/microsite) — the "why Shopify Plus" story
   - `~/maps/<slug>/map.html` (mutual action plan) — the editable shared milestone tracker
   The hub `map_url` in DEALS arrays points at `map.html`; `proposal_url` points at the directory root (the proposal).
8. Surface a one-paragraph summary of what you added + the draft MEDDIC + both URLs + passcode.
9. Commit + push the hub repo AND the maps repo (two separate `git push` commands, two separate working dirs).

### Scaffolding the proposal + MAP (required for every new opportunity)

Every new deal gets **two files** in the standalone maps repo at `~/maps/<slug>/`. Both share the same passcode but have separate `sessionStorage` keys.

#### File 1 — `~/maps/<slug>/index.html` (Proposal / Microsite)

The prospect-facing proposal — the link the AE pastes into emails to tell the "why Shopify Plus, for you, now" story. Static marketing-style content with branded sections.

**Required sections (in order):**

1. **Password gate** — full-screen black overlay, brand-circle logo, single passcode field, shake on miss, `sessionStorage.setItem('<slug>_auth', '1')` on success. Default passcode `<Slug><Year>` (e.g. `OPT123`, `Feniex123`); accept lowercase + uppercase entry.
2. **Sticky top nav** — brand circle (3-letter abbrev) + account name + section anchor links + "Shopify Plus" wordmark + a "Mutual Action Plan" link to `./map.html`.
3. **Hero** — full-viewport-height dark section. Eyebrow ("Prepared Exclusively For"), centered brand seal, Playfair headline with one italicized phrase in accent color, sub-line, hero meta row.
4. **Section 01 — Today** — 4-card grid summarizing current state (catalog, stack, channels, deadline) + a "real pain points" block quoting the prospect's words.
5. **Stat bar** — 4-cell dark bar with headline numbers.
6. **Section 02 — Why Shopify Plus** — 2-4 "pillars" mapped to their decision criteria.
7. **Section 03 — Integrations** — tiles showing each piece of current stack (ERP, tax, marketing, payments, partner) on Plus.
8. **Section 04 — The Migration Path** — 3-5 phased steps. Phase 0 = validation gate; final phase = hard deadline.
9. **Section 05 — Investment** — 2 pricing cards (recommended term = accent border + featured tag).
10. **Section 06 — Stakeholders** — grid of person cards with org tag, name, title, role/motivation.
11. **Section 07 — Next Steps** — short summary that points the reader to `./map.html` for the live, editable plan.
12. **Final callout** — dark CTA card, eyebrow, big headline with italicized accent phrase.
13. **Footer** — `Account × Shopify Plus · Prepared by <AE Name> · <Month> <Year>`.

**CSS conventions:** Inter + Playfair Display, CSS custom properties for color (`--bg`, `--white`, `--black`, `--dark`, `--mid`, `--light`, `--border`, brand accent). Section padding `6rem 2.5rem`, `max-width: 1080px`. Mobile breakpoint at 720px.

**Reference:** `https://chasemccane.github.io/maps/ohio-power-tool/` (canonical, black + OPT red).

#### File 2 — `~/maps/<slug>/map.html` (Mutual Action Plan) — CANONICAL TEMPLATE

The shared, editable milestone tracker. Both AE and prospect view the same page; edits persist in `localStorage` under `map-<slug>`. This is **the file that gets auto-created for every new opportunity** — copy the structure verbatim from the canonical template.

**Canonical template:** `https://chasemccane.github.io/maps/feniex/map.html`. Always start from this file. Only swap:

- `const PASS = '<Passcode>'` (same passcode as the proposal)
- `sessionStorage` key: `map-auth-<slug>`
- `CFG.store_key = 'map-<slug>'` (localStorage key for persisted edits)
- `CFG.company`, `CFG.short` (3-letter abbrev for brand circle), `CFG.ae`, `CFG.ae_email`, `CFG.replacing` (e.g. "Adobe Commerce Cloud", "BigCommerce", "Magento")
- `CFG.team.customer[]`, `CFG.team.shopify[]`, and optionally `CFG.team.partner[]` (third group for SI partners like i95dev, Atwix)
- `CFG.goals[]` (4 short outcome statements)
- `DEFAULTS.milestones[]` (array of `{ title, s: 'pending|progress|complete|na', date, note, desc, started_at, completed_at }`)
- `DEFAULTS.actions[]` (`{ action, owner, side: 'customer|shopify|partner', due, s }`)
- `DEFAULTS.questions[]` (`{ question, from, side, assigned, s: 'open|answered' }`)
- CSS `--accent` color (prospect brand) + `--accent-light` tint

**Required structural elements (do not rewrite — copy from feniex/map.html):**

- Auth gate (passcode → `sessionStorage` → reveal main)
- Sticky nav with section anchors and accent underline on active section
- Hero with two-column layout: company name + AE info on left, deal context on right with "View Proposal" link to `./` (sibling index.html)
- "Goals" section: 4 outcome cards
- "Team" section: `renderTeam()` renders one group per `CFG.team.*` (customer, shopify, optionally partner)
- "Milestones" section: numbered timeline with status cyclers (`cycleMS(idx)` → pending → progress → complete → na). Auto-stamps `started_at` and `completed_at` on transitions.
- "Actions" section: editable rows, status cyclers (`cycleStat`), owner pills tinted by side
- "Questions" section: open/answered cyclers (`cycleQ`)
- "Trial Store" form (formsubmit.co endpoint)
- Footer with "View Proposal →" link pointing at `./`
- `<script>`: localStorage persistence under `CFG.store_key`, 'storage' event listener for cross-tab sync, IntersectionObserver for nav highlighting

**Populating content from Fellow + SF:**
- Milestones → seed from your typical sales cycle (Discovery → Technical Discovery → Trial Validation → Scoping → Solution Review → Exec Alignment → LOI → Contract → Trial Store → Sign → Implementation → Decommission → Go-Live). Adjust per deal.
- Mark completed milestones based on Fellow meeting history (use the meeting date as `completed_at`).
- Mark the next upcoming meeting from calendar as `progress` with that date.
- Actions → pull from Fellow action items + your `left` array in `deal-data.json`.
- Questions → pull from Fellow summary "open questions" + anything explicit you logged in MEDDIC.
- Team → from MEDDIC `economic_buyer` + `champion` + calendar attendees + any partner (SI) named in the deal.

**Reference implementations:**
- `~/maps/feniex/map.html` — **CANONICAL TEMPLATE.** Always copy this file's structure when scaffolding a new MAP.
- `~/maps/hedrick/map.html`, `~/maps/bulldog-tools/map.html`, `~/maps/ohio-power-tool/map.html` — examples with varying team sizes / accent colors / partner involvement.

**Reference proposal implementations:**
- `~/maps/ohio-power-tool/index.html` — black + OPT red, B2B+DTC+retail story.
- `~/maps/washington-floral/index.html` — forest + sage, wholesale-only.
- `~/maps/anatomy-warehouse/index.html` — longer form, deeper MEDDIC.

Always copy the structural skeleton; do not rewrite from scratch. Visual consistency across maps is part of the brand.

### Daily refresh

1. Run `scripts/refresh_deals.py` (env vars exported via SF CLI). Captures both per-deal updates AND the Closed Won FY aggregate.
2. Pull calendar for the next 7 days. Cross-reference to deals. Update `CALLS` array on dashboard.
3. Optional: scan Fellow for any new meeting summaries since last refresh. For each, ask the user if MEDDIC should be updated.
4. Commit + push.

### Remove a deal

1. Remove the entry from all three hub HTML `DEALS` arrays.
2. Remove from `deal-data.json`.
3. **Append the id to `REMOVED_IDS`** in `deal-review/index.html` (and `map-hub/index.html` if it has one).
4. Leave the `~/maps/<slug>/` folder in the maps repo alone — it no longer surfaces in the hub once the id is removed, but the prospect-shared URL stays live in case they're still reviewing. Only delete the maps folder if the user explicitly asks.
5. Commit + push the hub repo.

### MEDDIC enrichment after a call

1. User: "Update MEDDIC on \<deal\> from today's call" (or you proactively notice a new Fellow meeting summary).
2. Search Fellow → pull summary → pull transcript chunks for any thin MEDDIC dimensions.
3. Read existing MEDDIC. **Merge, don't overwrite.**
4. Update `done` (append the new milestone), `left` (prune anything addressed), `last_call`, `next_call`.
5. Surface the diff. Get confirmation.
6. Commit + push.

---

## MEDDPICC scoring (auto-apply on new deals + refreshes)

When adding a new deal or running a hub-wide refresh, also score each deal against MEDDPICC and surface gaps. The score lives in `deal-data.json` under `deals.<id>.meddpicc`:

```json
"meddpicc": {
  "metrics": 2, "economic_buyer": 1, "decision_criteria": 3,
  "decision_process": 2, "paper_process": 0, "identify_pain": 3,
  "champion": 2, "competition": 1,
  "score": 14,
  "qualifying_questions": ["What's the budget approval process?", "..."]
}
```

Scoring: 0 = unknown, 1 = thin, 2 = solid, 3 = strong. Total /24. Surface deals scoring < 12 as "thin qualification" — these need targeted discovery before forecasting.

Generate qualifying questions for any dimension scoring 0–1, prioritizing the ones with biggest forecast impact (Economic Buyer, Paper Process, Decision Process).

---

## Anti-patterns — things to never do

- **Do not** use `mcp__revenue-mcp__search_salesforce_tool` or any sdp-pii-permit-dependent tool for hub data. Use the SF CLI route via `scripts/refresh_deals.py` or direct `simple_salesforce` calls.
- **Do not** track ARR. Use PBR (Projected Billed Revenue) only.
- **Do not** add backwards-compat shims, version-migration logic, or "rollback safety" code unless the user asks. Edits go forward.
- **Do not** add file-level or function-level comments explaining what the code does. The patterns in this doc are the comment.
- **Do not** send emails or Slack messages without explicit confirmation. Drafts only.
- **Do not** modify Salesforce. Read-only.
- **Do not** end responses with a recap of what you just did. The diff is visible; jump to the next step or stop.
- **Do not** invent stage names. Use whatever StageName values come back from the user's SF org — if their stage labels differ from the reference set, update the `STAGE_MAP` in `refresh_deals.py` and propagate the new labels to the deal-card UIs.
- **Do not** trust browser localStorage for fresh state. After any edit, the source of truth is `deal-data.json` on the main branch.

---

## When to ask the user vs. just do it

**Just do it:**
- Refresh SF data
- Cross-reference calendar to deals
- Commit + push after a clear edit
- Fix a typo or obvious bug in the hub

**Ask first:**
- Draft MEDDIC inferred from calls — surface the draft before writing
- Adding a deal where SF search returns ambiguous matches
- Removing a deal (confirm it's actually closed/dead)
- Any change that meaningfully alters strategy / risks
- Anything that requires more than a one-line outbound (email/Slack drafts)

When in doubt: surface a one-sentence summary of the proposed change and wait for "yes" / "go" / "looks good." Keep the surface terse — the user reads diffs, not paragraphs.

---

## Reference: known-good hub

[github.com/chasemccane/hub](https://github.com/chasemccane/hub) is the canonical reference implementation. Read it directly with `mcp__tool-gateway__grokt_get_file` or `gh api repos/chasemccane/hub/contents/<path>` when you need to copy a pattern. Specifically useful files:

- `index.html` — lock screen + passcode pattern
- `dashboard/index.html` — deal cards, CALLS array, 3-tier forecast, Quarter Breakdown
- `deal-review/index.html` — tab pattern, MEDDIC UI, applyRemoteData + REMOVED_IDS
- `map-hub/index.html` — MAP card grid + stage integer mapping
- `scripts/refresh_deals.py` — SF data refresh (PBR + stage + Closed Won aggregate)
- `deal-data.json` — schema reference (full real-world example)

Match the structure. Substitute the user's branding, deals, and passcode.
