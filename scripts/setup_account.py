#!/usr/bin/env python3
"""
Account Setup & Discovery Script.
Run this FIRST when onboarding a new Kommo account.

Discovers and saves:
- Account info (name, ID, amojo_id)
- Pipelines and stages
- Custom fields (leads + contacts)
- Users and teams
- Chat channels/sources
- Tags in use

Usage:
    python scripts/setup_account.py

Prerequisites:
    1. Copy .env.example to .env
    2. Fill in KOMMO_BASE_URL and KOMMO_ACCESS_TOKEN
    3. Run this script
"""
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error

# Load env
ENV = {}
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if not os.path.exists(env_path):
    print("ERROR: .env file not found. Run: cp .env.example .env")
    sys.exit(1)

with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            ENV[k.strip()] = v.strip()

BASE_URL = ENV.get('KOMMO_BASE_URL', '')
TOKEN = ENV.get('KOMMO_ACCESS_TOKEN', '')

if not BASE_URL or not TOKEN:
    print("ERROR: KOMMO_BASE_URL and KOMMO_ACCESS_TOKEN must be set in .env")
    sys.exit(1)

CTX = ssl.create_default_context()
RATE_DELAY = 0.2  # 5 req/s, safe under 7/s limit


def api_get(path):
    """GET request to Kommo API v4."""
    time.sleep(RATE_DELAY)
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json'
    })
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=15) as resp:
            if resp.status == 204:
                return None
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(3)
            return api_get(path)
        print(f"  API Error {e.code} on {path}")
        return None


def main():
    print("=" * 60)
    print("  KOMMO ACCOUNT SETUP & DISCOVERY")
    print("=" * 60)

    output = {}

    # ── 1. Account Info ──────────────────────────────────────────
    print("\n[1/7] Account info...")
    data = api_get('/api/v4/account?with=amojo_id,users_groups,version')
    if not data:
        print("  FAILED: Cannot connect to Kommo API. Check URL and token.")
        sys.exit(1)

    output['account'] = {
        'id': data['id'],
        'name': data['name'],
        'subdomain': data['subdomain'],
        'amojo_id': data.get('amojo_id', ''),
        'country': data.get('country', ''),
        'currency': data.get('currency', ''),
        'language': data.get('language', ''),
    }
    print(f"  Account: {data['name']} (ID: {data['id']})")
    print(f"  Subdomain: {data['subdomain']}")
    print(f"  Amojo ID: {data.get('amojo_id', 'N/A')}")

    # ── 2. Pipelines & Stages ────────────────────────────────────
    print("\n[2/7] Pipelines and stages...")
    data = api_get('/api/v4/leads/pipelines')
    pipelines = {}
    if data:
        for p in data['_embedded']['pipelines']:
            stages = {}
            for s in p['_embedded']['statuses']:
                stages[str(s['id'])] = {
                    'name': s['name'], 'sort': s['sort'], 'color': s['color']
                }
            pipelines[str(p['id'])] = {
                'name': p['name'], 'sort': p['sort'],
                'is_main': p['is_main'], 'stages': stages
            }
            print(f"  Pipeline: {p['name']} ({len(stages)} stages)")
    output['pipelines'] = pipelines

    # ── 3. Custom Fields (Leads) ─────────────────────────────────
    print("\n[3/7] Lead custom fields...")
    data = api_get('/api/v4/leads/custom_fields?limit=250')
    lead_fields = {}
    if data:
        for f in data['_embedded']['custom_fields']:
            enums = None
            if f.get('enums'):
                enums = {str(e['id']): e['value'] for e in f['enums']}
            lead_fields[str(f['id'])] = {
                'name': f['name'], 'type': f['type'],
                'code': f.get('code'), 'enums': enums
            }
    output['lead_custom_fields'] = lead_fields
    print(f"  Found {len(lead_fields)} lead custom fields")

    # ── 4. Custom Fields (Contacts) ──────────────────────────────
    print("\n[4/7] Contact custom fields...")
    data = api_get('/api/v4/contacts/custom_fields?limit=250')
    contact_fields = {}
    if data:
        for f in data['_embedded']['custom_fields']:
            enums = None
            if f.get('enums'):
                enums = {str(e['id']): e['value'] for e in f['enums']}
            contact_fields[str(f['id'])] = {
                'name': f['name'], 'type': f['type'],
                'code': f.get('code'), 'enums': enums
            }
    output['contact_custom_fields'] = contact_fields
    print(f"  Found {len(contact_fields)} contact custom fields")

    # ── 5. Users ─────────────────────────────────────────────────
    print("\n[5/7] Users...")
    data = api_get('/api/v4/users?limit=250')
    users = {}
    if data:
        for u in data['_embedded']['users']:
            users[str(u['id'])] = {'name': u['name'], 'email': u['email']}
            print(f"  User: {u['name']} ({u['email']})")
    output['users'] = users

    # ── 6. Chat Channels (from recent talks) ─────────────────────
    print("\n[6/7] Chat channels (from recent talks)...")
    data = api_get('/api/v4/talks?limit=250')
    channels = {}
    if data:
        for t in data.get('_embedded', {}).get('talks', []):
            origin = t.get('origin', 'unknown')
            source_id = t.get('source_id', '')
            key = f"{origin}_{source_id}"
            if key not in channels:
                channels[key] = {
                    'origin': origin,
                    'source_id': source_id,
                    'count': 0
                }
            channels[key]['count'] += 1
    output['channels'] = list(channels.values())
    for ch in sorted(channels.values(), key=lambda x: -x['count']):
        print(f"  {ch['origin']}: source_id={ch['source_id']} ({ch['count']} talks)")

    # ── 7. Tags (from recent leads) ──────────────────────────────
    print("\n[7/7] Tags in use...")
    data = api_get('/api/v4/leads/tags?limit=250')
    tags = []
    if data:
        for t in data.get('_embedded', {}).get('tags', []):
            tags.append({'id': t['id'], 'name': t['name']})
            if len(tags) <= 15:
                print(f"  Tag: {t['name']}")
        if len(tags) > 15:
            print(f"  ... and {len(tags) - 15} more tags")
    output['tags'] = tags

    # ── Save ─────────────────────────────────────────────────────
    out_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'kommo_mappings.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"  SETUP COMPLETE")
    print(f"  Account: {output['account']['name']}")
    print(f"  Pipelines: {len(pipelines)}")
    print(f"  Lead fields: {len(lead_fields)}")
    print(f"  Contact fields: {len(contact_fields)}")
    print(f"  Users: {len(users)}")
    print(f"  Channels: {len(channels)}")
    print(f"  Tags: {len(tags)}")
    print(f"  Saved to: {out_path}")
    print(f"{'=' * 60}")
    print(f"\nNext steps:")
    print(f"  1. Review config/kommo_mappings.json")
    print(f"  2. Add login credentials to .env (user without 2FA)")
    print(f"  3. Run: python scripts/validate_setup.py")
    print(f"  4. Test: python scripts/scrape_v3.py --max-chats 5")


if __name__ == '__main__':
    main()
