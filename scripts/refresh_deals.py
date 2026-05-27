#!/usr/bin/env python3
"""
Salesforce refresh for deal-data.json.

Reads SF_ACCESS_TOKEN + SF_INSTANCE_URL from the environment, queries each
opp listed under deals.*.sf.id, and rewrites each `sf` block with the
current stage, close date, PBR, merchant intent, and last-modified date.
Also rebuilds the Closed Won FY aggregate for the quota tile.

Uses only the Python stdlib — no simple-salesforce, no requests.
Invoked nightly by ~/Library/LaunchAgents/com.mercedes.hub-refresh.plist.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_VERSION = 'v66.0'

SF_ACCESS_TOKEN = os.environ.get('SF_ACCESS_TOKEN', '').strip()
SF_INSTANCE_URL = os.environ.get('SF_INSTANCE_URL', '').strip().rstrip('/')

if not SF_ACCESS_TOKEN or not SF_INSTANCE_URL:
    print('ERROR: SF_ACCESS_TOKEN or SF_INSTANCE_URL missing from env.', file=sys.stderr)
    sys.exit(2)


def soql(query):
    url = f"{SF_INSTANCE_URL}/services/data/{API_VERSION}/query?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {SF_ACCESS_TOKEN}'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def userinfo():
    url = f"{SF_INSTANCE_URL}/services/oauth2/userinfo"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {SF_ACCESS_TOKEN}'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'deal-data.json')
with open(DATA_FILE) as f:
    data = json.load(f)

# Collect opp IDs to refresh
sf_ids = []
id_to_slug = {}
for slug, deal in data['deals'].items():
    opp_id = (deal.get('sf') or {}).get('id')
    if opp_id:
        sf_ids.append(opp_id)
        id_to_slug[opp_id] = slug

if not sf_ids:
    print('No Salesforce IDs found in deal-data.json — nothing to refresh.')
    sys.exit(0)

ids_str = "', '".join(sf_ids)
q = (
    "SELECT Id, Name, StageName, CloseDate, Projected_Billed_Revenue__c, Amount, "
    "CreatedDate, LastModifiedDate, Merchant_Intent__c, Owner.Name, Account.Name "
    f"FROM Opportunity WHERE Id IN ('{ids_str}')"
)
print(f'Querying {len(sf_ids)} opportunities…')
result = soql(q)
records = result.get('records', [])
print(f'Got {len(records)} records.')

updated = 0
for rec in records:
    slug = id_to_slug.get(rec['Id'])
    if not slug:
        continue
    old = dict(data['deals'][slug].get('sf') or {})
    new_sf = {
        'id': rec['Id'],
        'stage': rec.get('StageName', ''),
        'close': rec.get('CloseDate', ''),
        'pbr': int(rec.get('Projected_Billed_Revenue__c') or 0),
        'amount': int(rec.get('Amount') or 0),
        'merchant_intent': rec.get('Merchant_Intent__c') or '',
        'last_modified': (rec.get('LastModifiedDate') or '')[:10],
    }
    if old.get('name'):
        new_sf['name'] = old['name']
    if old.get('owner'):
        new_sf['owner'] = old['owner']
    data['deals'][slug]['sf'] = new_sf

    diffs = []
    if old.get('stage') != new_sf['stage']:
        diffs.append(f"stage {old.get('stage')} → {new_sf['stage']}")
    if old.get('close') != new_sf['close']:
        diffs.append(f"close {old.get('close')} → {new_sf['close']}")
    if old.get('pbr') != new_sf['pbr']:
        diffs.append(f"PBR ${old.get('pbr', 0):,} → ${new_sf['pbr']:,}")
    if old.get('merchant_intent') != new_sf['merchant_intent']:
        diffs.append(f"intent {old.get('merchant_intent') or '∅'} → {new_sf['merchant_intent'] or '∅'}")
    if diffs:
        print(f"  {slug}: " + '; '.join(diffs))
    updated += 1

# Closed Won FY aggregate
try:
    info = userinfo()
    current_user_id = info.get('user_id')
except Exception as e:
    print(f'WARN: userinfo lookup failed: {e}', file=sys.stderr)
    current_user_id = None

if current_user_id:
    now = datetime.now(timezone.utc)
    fy_start = f'{now.year}-01-01'
    cw = soql(
        'SELECT Id, Name, StageName, CloseDate, Projected_Billed_Revenue__c, Account.Name '
        f"FROM Opportunity WHERE OwnerId = '{current_user_id}' AND StageName = 'Closed Won' "
        f'AND CloseDate >= {fy_start}'
    )
    quarters = {n: {'count': 0, 'pbr': 0, 'deals': []} for n in (1, 2, 3, 4)}
    fy_count = 0
    fy_pbr = 0
    for rec in cw.get('records', []):
        pbr = int(rec.get('Projected_Billed_Revenue__c') or 0)
        fy_count += 1
        fy_pbr += pbr
        close_v = rec.get('CloseDate', '')
        if close_v:
            qn = (int(close_v.split('-')[1]) - 1) // 3 + 1
            quarters[qn]['count'] += 1
            quarters[qn]['pbr'] += pbr
            quarters[qn]['deals'].append({
                'id': rec['Id'],
                'name': rec.get('Name', ''),
                'pbr': pbr,
                'close': close_v,
            })
    data['closed_won'] = {
        'fy': {'year': now.year, 'count': fy_count, 'pbr': fy_pbr},
        'current_quarter': (now.month - 1) // 3 + 1,
        'quarters': {f'Q{n}': {'year': now.year, **quarters[n]} for n in (1, 2, 3, 4)},
        'updated': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    print(f'Closed Won FY{now.year}: {fy_count} deals, ${fy_pbr:,}')

data['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
data['version'] = int(data.get('version', 0)) + 1

with open(DATA_FILE, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f'Done. {updated} deals refreshed. New version: {data["version"]}.')
