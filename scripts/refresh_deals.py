#!/usr/bin/env python3
"""
CRM refresh for deal-data.json.

Shopify retired Salesforce on 2026-07-01; deal data now lives in the homegrown
CRM ("unicorn"), surfaced through BigQuery at shopify-dw.sales. This script
queries the CRM via the `bq` CLI (stdlib subprocess + json only — no pip
installs, so it runs cleanly under cron) and rewrites each `sf` block in
deal-data.json with the current stage, close date, PBR, and CRM metadata.
Also rebuilds the Closed Won FY aggregate for the quota tile.

The output JSON shape is unchanged from the Salesforce era — only the source
of the data moved. New CRM-native fields (close_reason, is_closed, is_won,
salesforce_opportunity_id) are added alongside the existing keys; nothing is
renamed or removed.

Matching: a tracked deal's stored `sf.id` is matched against the CRM
`opportunity_id` OR the legacy `salesforce_opportunity_id` bridge column (which
still holds the old Salesforce Opp Id). Once matched, `sf.id` is canonicalized
to the CRM opportunity_id going forward.

Stages are stored as the CRM's lowercase tokens (evaluate / propose / dealcraft
/ launch / closed_won / closed_lost); the frontends map those to display labels.

`amount` and `merchant_intent` have no CRM equivalent — their existing values
are preserved (never overwritten). Launch-target dates live only in the
frontends as hand-edited planning fields and are never touched here.

Invoked nightly by ~/Library/LaunchAgents/com.mercedes.hub-refresh.plist.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

# CRM owner id. The value the CRM stores in owner_id is the numeric prefix;
# the "-Mercedes-Boykin-Sabalones" suffix is only part of the Vault URL slug
# (https://vault.shopify.io/crm/users/39432-Mercedes-Boykin-Sabalones).
OWNER_ID_SLUG = '39432-Mercedes-Boykin-Sabalones'
OWNER_ID = OWNER_ID_SLUG.split('-')[0]

PROJECT = 'shopify-dw'
OPPS_TABLE = 'shopify-dw.sales.sales_opportunities_v2'
REVENUE_TABLE = 'shopify-dw.sales.sales_opportunity_products_revenue'

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'deal-data.json')


def bq(query):
    """Run a BigQuery query via the bq CLI and return parsed JSON rows."""
    cmd = [
        'bq', 'query',
        f'--project_id={PROJECT}',
        '--use_legacy_sql=false',
        '--format=json',
        '--max_rows=100000',
        query,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        print('ERROR: `bq` not found on PATH. Ensure '
              '~/.local/state/tec/toolchain/base_profile/bin is on PATH.', file=sys.stderr)
        sys.exit(2)
    if out.returncode != 0:
        print('ERROR: bq query failed:\n' + (out.stderr or out.stdout), file=sys.stderr)
        sys.exit(3)
    body = (out.stdout or '').strip()
    if not body:
        return []
    return json.loads(body)


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


# ── Pull every opportunity owned by this CRM user, with PBR joined in. ──
# One query serves both the tracked-deal refresh and the Closed Won aggregate.
OWNER_QUERY = f"""
SELECT
  o.opportunity_id,
  o.salesforce_opportunity_id,
  o.name,
  o.current_stage_name,
  CAST(o.close_date AS STRING) AS close_date,
  CAST(DATE(o.created_at) AS STRING) AS created_date,
  CAST(DATE(o.updated_at) AS STRING) AS updated_date,
  o.is_closed,
  o.is_won,
  o.close_reason,
  o.product_list,
  CAST(IFNULL(r.pbr, 0) AS INT64) AS pbr
FROM `{OPPS_TABLE}` o
LEFT JOIN (
  SELECT opportunity_id, SUM(total_projected_billed_revenue) AS pbr
  FROM `{REVENUE_TABLE}`
  GROUP BY opportunity_id
) r ON o.opportunity_id = r.opportunity_id
WHERE o.owner_id = '{OWNER_ID}'
"""


def as_bool(v):
    return str(v).lower() == 'true'


def main():
    with open(DATA_FILE) as f:
        data = json.load(f)

    print(f'Querying CRM for owner {OWNER_ID}…')
    rows = bq(OWNER_QUERY)
    print(f'Got {len(rows)} opportunities from the CRM.')

    # Index CRM rows by both the CRM id and the legacy Salesforce bridge id,
    # so a tracked deal matches whichever id it currently stores.
    by_id = {}
    for r in rows:
        oid = r.get('opportunity_id')
        sfid = r.get('salesforce_opportunity_id')
        if oid:
            by_id[oid] = r
        if sfid:
            by_id.setdefault(sfid, r)

    updated = 0
    unmatched = []
    for slug, deal in data['deals'].items():
        old = dict(deal.get('sf') or {})
        stored_id = old.get('id')
        rec = by_id.get(stored_id) if stored_id else None
        if not rec:
            unmatched.append(slug)
            continue

        crm_id = rec['opportunity_id']  # canonicalize going forward
        new_sf = {
            'id': crm_id,
            'stage': rec.get('current_stage_name') or '',
            'close': rec.get('close_date') or '',
            'pbr': to_int(rec.get('pbr')),
            # No CRM equivalent — preserve whatever was there (manual/legacy).
            'amount': to_int(old.get('amount')),
            'merchant_intent': old.get('merchant_intent') or '',
            'last_modified': rec.get('updated_date') or '',
            # CRM-native additions.
            'created': rec.get('created_date') or old.get('created') or '',
            'is_closed': as_bool(rec.get('is_closed')),
            'is_won': as_bool(rec.get('is_won')),
            'close_reason': rec.get('close_reason') or '',
            'salesforce_opportunity_id': rec.get('salesforce_opportunity_id') or '',
        }
        # Preserve descriptive fields the refresh never sourced.
        if old.get('name'):
            new_sf['name'] = old['name']
        if old.get('owner'):
            new_sf['owner'] = old['owner']

        data['deals'][slug]['sf'] = new_sf

        diffs = []
        if old.get('id') != new_sf['id']:
            diffs.append(f"id {old.get('id')} → {new_sf['id']} (canonicalized)")
        if old.get('stage') != new_sf['stage']:
            diffs.append(f"stage {old.get('stage')} → {new_sf['stage']}")
        if old.get('close') != new_sf['close']:
            diffs.append(f"close {old.get('close')} → {new_sf['close']}")
        if old.get('pbr') != new_sf['pbr']:
            diffs.append(f"PBR ${to_int(old.get('pbr')):,} → ${new_sf['pbr']:,}")
        if diffs:
            print(f"  {slug}: " + '; '.join(diffs))
        updated += 1

    if unmatched:
        print('WARN: no CRM match for: ' + ', '.join(unmatched) +
              ' (left unchanged — check ownership or id).', file=sys.stderr)

    # ── Closed Won FY aggregate (all owner deals, not just tracked). ──
    now = datetime.now(timezone.utc)
    fy_start = datetime(now.year, 1, 1).date()
    quarters = {n: {'count': 0, 'pbr': 0, 'deals': []} for n in (1, 2, 3, 4)}
    fy_count = 0
    fy_pbr = 0
    for r in rows:
        if not as_bool(r.get('is_won')):
            continue
        close_v = r.get('close_date') or ''
        if not close_v or close_v < str(fy_start):
            continue
        pbr = to_int(r.get('pbr'))
        fy_count += 1
        fy_pbr += pbr
        qn = (int(close_v.split('-')[1]) - 1) // 3 + 1
        quarters[qn]['count'] += 1
        quarters[qn]['pbr'] += pbr
        quarters[qn]['deals'].append({
            'id': r['opportunity_id'],
            'name': r.get('name', ''),
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

    data['updated'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    data['version'] = int(data.get('version', 0)) + 1

    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')

    print(f'Done. {updated} deals refreshed. New version: {data["version"]}.')


if __name__ == '__main__':
    main()
