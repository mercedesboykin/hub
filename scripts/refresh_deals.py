#!/usr/bin/env python3
"""
Daily Salesforce refresh for deal-data.json
Updates: pbr, stage, close date, created date for each deal.
Run via GitHub Actions or manually: python scripts/refresh_deals.py
"""

import json
import os
import sys
from datetime import datetime, timezone

try:
    from simple_salesforce import Salesforce
except ImportError:
    print("ERROR: Run 'pip install simple-salesforce' first.")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: Run 'pip install requests' first.")
    sys.exit(1)

# ── Auth via SF CLI access token (Okta-compatible) ────────────────────────────
SF_ACCESS_TOKEN = os.environ['SF_ACCESS_TOKEN']
SF_INSTANCE_URL = os.environ['SF_INSTANCE_URL'].rstrip('/')

sf = Salesforce(session_id=SF_ACCESS_TOKEN, instance_url=SF_INSTANCE_URL)
print(f"Connected: {SF_INSTANCE_URL}")

# ── Resolve current user (for Closed Won by owner query) ─────────────────────
CURRENT_USER_ID = None
try:
    userinfo = requests.get(
        f"{SF_INSTANCE_URL}/services/oauth2/userinfo",
        headers={"Authorization": f"Bearer {SF_ACCESS_TOKEN}"},
        timeout=15,
    ).json()
    CURRENT_USER_ID = userinfo.get('user_id')
    print(f"Authenticated as: {userinfo.get('preferred_username')} ({CURRENT_USER_ID})")
except Exception as e:
    print(f"WARN: Could not resolve current user via userinfo: {e}")

# ── Load deal-data.json ───────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'deal-data.json')
with open(DATA_FILE) as f:
    data = json.load(f)

# ── Collect Opportunity IDs ───────────────────────────────────────────────────
sf_ids = []
id_to_deal = {}
for deal_id, deal in data['deals'].items():
    sf_info = deal.get('sf', {})
    opp_id = sf_info.get('id')
    if opp_id:
        sf_ids.append(opp_id)
        id_to_deal[opp_id] = deal_id

if not sf_ids:
    print("No Salesforce IDs found in deal-data.json — nothing to refresh.")
    sys.exit(0)

# ── Query Salesforce ──────────────────────────────────────────────────────────
ids_str = "', '".join(sf_ids)
soql = f"""
    SELECT Id, Name, StageName, CloseDate, Projected_Billed_Revenue__c, CreatedDate
    FROM Opportunity
    WHERE Id IN ('{ids_str}')
""".strip()

print(f"Querying {len(sf_ids)} opportunities…")
result = sf.query(soql)
records = result.get('records', [])
print(f"Got {len(records)} records.")

# Stage name passthrough — Shopify Salesforce stages match hub display names
STAGE_MAP = {
    'Pre-Qualified': 'Pre-Qualified',
    'Envision':      'Envision',
    'Solution':      'Solution',
    'Demonstrate':   'Demonstrate',
    'Closed Won':    'Closed Won',
    # Add any Salesforce-specific stage names that differ:
    # 'Proposal/Price Quote': 'Solution',
}

# ── Apply updates ─────────────────────────────────────────────────────────────
updated_count = 0
for rec in records:
    opp_id   = rec['Id']
    deal_id  = id_to_deal.get(opp_id)
    if not deal_id:
        continue

    sf_node = data['deals'][deal_id].setdefault('sf', {})
    sf_node['id'] = opp_id

    # PBR
    pbr = rec.get('Projected_Billed_Revenue__c')
    sf_node['pbr'] = int(pbr) if pbr is not None else 0

    # Stage
    stage_sf = rec.get('StageName', '')
    sf_node['stage'] = STAGE_MAP.get(stage_sf, stage_sf)

    # Close Date — Salesforce returns "YYYY-MM-DD"
    close = rec.get('CloseDate')
    if close:
        sf_node['close'] = close  # keep as ISO YYYY-MM-DD

    # Created Date — Salesforce returns ISO datetime, keep just the date
    created = rec.get('CreatedDate')
    if created:
        sf_node['created'] = created[:10]

    print(f"  {deal_id}: stage={sf_node['stage']}, close={sf_node.get('close')}, pbr={sf_node['pbr']}")
    updated_count += 1

# ── Closed Won aggregate for current FY (Shopify = calendar year) ─────────────
if CURRENT_USER_ID:
    now = datetime.now(timezone.utc)
    fy_start = f"{now.year}-01-01"
    q = (now.month - 1) // 3 + 1
    q_start_month = (q - 1) * 3 + 1
    q_start = f"{now.year}-{q_start_month:02d}-01"
    q_end_month = q_start_month + 2
    last_day = [31, 28 if now.year % 4 else 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][q_end_month - 1]
    if q_end_month == 2 and (now.year % 400 == 0 or (now.year % 4 == 0 and now.year % 100 != 0)):
        last_day = 29
    q_end = f"{now.year}-{q_end_month:02d}-{last_day:02d}"

    cw_soql = f"""
        SELECT Id, Name, StageName, CloseDate, Projected_Billed_Revenue__c
        FROM Opportunity
        WHERE OwnerId = '{CURRENT_USER_ID}'
          AND StageName = 'Closed Won'
          AND CloseDate >= {fy_start}
    """.strip()
    print(f"\nQuerying Closed Won for OwnerId {CURRENT_USER_ID} since {fy_start}…")
    cw_result = sf.query_all(cw_soql)
    cw_records = cw_result.get('records', [])
    print(f"Got {len(cw_records)} Closed Won records.")

    fy_count = 0
    fy_pbr = 0
    # Per-quarter buckets — every quarter in the FY
    quarters = {n: {'count': 0, 'pbr': 0, 'deals': []} for n in (1, 2, 3, 4)}

    for rec in cw_records:
        pbr_v = int(rec.get('Projected_Billed_Revenue__c') or 0)
        close_v = rec.get('CloseDate') or ''
        fy_count += 1
        fy_pbr += pbr_v
        deal_entry = {
            'id': rec['Id'],
            'name': rec.get('Name', ''),
            'pbr': pbr_v,
            'close': close_v,
        }
        # Bucket by quarter (Shopify FY = calendar year)
        if close_v:
            try:
                m = int(close_v.split('-')[1])
                qn = (m - 1) // 3 + 1
                quarters[qn]['count'] += 1
                quarters[qn]['pbr'] += pbr_v
                quarters[qn]['deals'].append(deal_entry)
            except (ValueError, IndexError):
                pass

    data['closed_won'] = {
        'fy': {'year': now.year, 'count': fy_count, 'pbr': fy_pbr},
        'current_quarter': q,
        'quarters': {
            'Q1': {'year': now.year, **quarters[1]},
            'Q2': {'year': now.year, **quarters[2]},
            'Q3': {'year': now.year, **quarters[3]},
            'Q4': {'year': now.year, **quarters[4]},
        },
        'updated': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    print(f"  FY {now.year}: {fy_count} deals, ${fy_pbr:,} PBR")
    for n in (1, 2, 3, 4):
        print(f"  Q{n} {now.year}: {quarters[n]['count']} deals, ${quarters[n]['pbr']:,} PBR")
else:
    print("\nSkipping Closed Won aggregate (no CURRENT_USER_ID).")

# ── Update timestamp ──────────────────────────────────────────────────────────
data['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
data['version'] = 2

# ── Write back ────────────────────────────────────────────────────────────────
with open(DATA_FILE, 'w') as f:
    json.dump(data, f, indent=2)

print(f"\nDone. {updated_count} deals refreshed. Timestamp: {data['updated']}")
