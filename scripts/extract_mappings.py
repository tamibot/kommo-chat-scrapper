#!/usr/bin/env python3
"""Extract Kommo account mappings (pipelines, fields, users) and save to JSON."""
import json
import os
import ssl
import urllib.request

# Read token from .env file manually
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
env_vars = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            env_vars[key.strip()] = val.strip()

TOKEN = env_vars.get('KOMMO_ACCESS_TOKEN', '')
BASE = env_vars.get('KOMMO_BASE_URL', 'https://propertamibotcom.kommo.com')

ctx = ssl.create_default_context()


def api_get(path):
    req = urllib.request.Request(
        f'{BASE}{path}',
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, context=ctx) as r:
        return json.loads(r.read())


def main():
    # Pipelines with statuses
    data = api_get('/api/v4/leads/pipelines')
    pipelines = {}
    for p in data['_embedded']['pipelines']:
        stages = {}
        for s in p['_embedded']['statuses']:
            stages[str(s['id'])] = {'name': s['name'], 'sort': s['sort'], 'color': s['color']}
        pipelines[str(p['id'])] = {
            'name': p['name'], 'sort': p['sort'],
            'is_main': p['is_main'], 'stages': stages
        }

    # Lead custom fields
    data2 = api_get('/api/v4/leads/custom_fields?limit=250')
    lead_fields = {}
    for f in data2['_embedded']['custom_fields']:
        enums = None
        if f.get('enums'):
            enums = {str(e['id']): e['value'] for e in f['enums']}
        lead_fields[str(f['id'])] = {
            'name': f['name'], 'type': f['type'],
            'code': f.get('code'), 'enums': enums
        }

    # Contact custom fields
    data3 = api_get('/api/v4/contacts/custom_fields?limit=250')
    contact_fields = {}
    for f in data3['_embedded']['custom_fields']:
        enums = None
        if f.get('enums'):
            enums = {str(e['id']): e['value'] for e in f['enums']}
        contact_fields[str(f['id'])] = {
            'name': f['name'], 'type': f['type'],
            'code': f.get('code'), 'enums': enums
        }

    # Users
    data4 = api_get('/api/v4/users?limit=250')
    users = {}
    for u in data4['_embedded']['users']:
        users[str(u['id'])] = {'name': u['name'], 'email': u['email']}

    result = {
        'account_id': 30050693,
        'subdomain': 'propertamibotcom',
        'amojo_id': '46db3794-cd6c-4506-a0a6-6205b2f546e9',
        'pipelines': pipelines,
        'lead_custom_fields': lead_fields,
        'contact_custom_fields': contact_fields,
        'users': users,
    }

    out_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'kommo_mappings.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Pipelines: {len(pipelines)}")
    print(f"Lead fields: {len(lead_fields)}")
    print(f"Contact fields: {len(contact_fields)}")
    print(f"Users: {len(users)}")
    for pid, p in pipelines.items():
        print(f"  Pipeline {pid}: {p['name']} ({len(p['stages'])} stages)")


if __name__ == '__main__':
    main()
