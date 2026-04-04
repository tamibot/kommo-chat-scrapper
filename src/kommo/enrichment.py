"""
Kommo API Enrichment Module.
Fetches lead, contact, tag, and stage data respecting rate limits (max 7 req/s).
Uses batch endpoints where possible to minimize requests.
"""
import json
import logging
import os
import ssl
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Rate limiter: max 7 requests per second
class RateLimiter:
    def __init__(self, max_per_sec=6):  # 6 to be safe under 7
        self.max_per_sec = max_per_sec
        self.timestamps = []

    def wait(self):
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < 1.0]
        if len(self.timestamps) >= self.max_per_sec:
            sleep_time = 1.0 - (now - self.timestamps[0]) + 0.05
            if sleep_time > 0:
                time.sleep(sleep_time)
        self.timestamps.append(time.time())


class KommoEnrichment:
    """Enriches scraped data with Kommo API v4 data."""

    def __init__(self, base_url: str = None, token: str = None, mappings_path: str = None):
        env = self._load_env()
        self.base_url = base_url or env.get('KOMMO_BASE_URL', 'https://tu-dominio.kommo.com')
        self.token = token or env.get('KOMMO_ACCESS_TOKEN', '')
        self.ctx = ssl.create_default_context()
        self.rate = RateLimiter(max_per_sec=6)
        self.mappings = {}

        mp = mappings_path or os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'kommo_mappings.json')
        if os.path.exists(mp):
            with open(mp) as f:
                self.mappings = json.load(f)

    def _load_env(self):
        env = {}
        ep = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
        if os.path.exists(ep):
            with open(ep) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        env[k.strip()] = v.strip()
        return env

    def _api_get(self, path: str) -> Optional[dict]:
        """GET request with rate limiting and error handling."""
        self.rate.wait()
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        })
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=15) as resp:
                if resp.status == 204:
                    return None
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry = int(e.headers.get('Retry-After', 3))
                logger.warning(f"Rate limited, sleeping {retry}s")
                time.sleep(retry)
                return self._api_get(path)  # retry once
            elif e.code == 204:
                return None
            else:
                logger.debug(f"API error {e.code} on {path}")
                return None
        except Exception as e:
            logger.debug(f"Request failed: {e}")
            return None

    # ── Batch Lead Fetch ─────────────────────────────────────────────

    def fetch_leads_batch(self, lead_ids: List[int]) -> Dict[int, dict]:
        """Fetch leads in batches of 50 (API limit), returns {lead_id: lead_data}."""
        result = {}
        batch_size = 50
        for i in range(0, len(lead_ids), batch_size):
            batch = lead_ids[i:i+batch_size]
            params = '&'.join(f'filter[id][]={lid}' for lid in batch)
            data = self._api_get(f'/api/v4/leads?{params}&with=contacts&limit=250')
            if data:
                for lead in data.get('_embedded', {}).get('leads', []):
                    result[lead['id']] = self._parse_lead(lead)
        logger.info(f"Fetched {len(result)}/{len(lead_ids)} leads")
        return result

    def _parse_lead(self, lead: dict) -> dict:
        """Parse a lead into clean structure."""
        pid = str(lead.get('pipeline_id', ''))
        sid = str(lead.get('status_id', ''))
        pinfo = self.mappings.get('pipelines', {}).get(pid, {})
        sinfo = pinfo.get('stages', {}).get(sid, {})
        ruid = str(lead.get('responsible_user_id', ''))
        ruser = self.mappings.get('users', {}).get(ruid, {})

        # Tags
        tags = []
        for tag in lead.get('_embedded', {}).get('tags', []):
            tags.append(tag.get('name', ''))

        # Custom fields
        cfields = {}
        for cf in (lead.get('custom_fields_values') or []):
            fname = cf.get('field_name', cf.get('field_id', ''))
            vals = cf.get('values', [])
            if vals:
                val = vals[0].get('value', '')
                if isinstance(val, (int, float)):
                    val = str(val)
                cfields[fname] = val

        # Contact IDs
        contacts = lead.get('_embedded', {}).get('contacts', [])
        contact_id = contacts[0]['id'] if contacts else None

        # Catalog Elements (Products and Subscriptions)
        catalog_elements = []
        for cat in lead.get('_embedded', {}).get('catalog_elements', []):
            catalog_elements.append({
                'id': cat.get('id'),
                'quantity': cat.get('metadata', {}).get('quantity', 1),
                'catalog_id': cat.get('metadata', {}).get('catalog_id')
            })

        return {
            'lead_id': lead['id'],
            'name': lead.get('name', ''),
            'contact_id': contact_id,
            'responsible_user_id': lead.get('responsible_user_id'),
            'responsible_user_name': ruser.get('name', ''),
            'pipeline_id': lead.get('pipeline_id'),
            'pipeline_name': pinfo.get('name', ''),
            'status_id': lead.get('status_id'),
            'stage_name': sinfo.get('name', ''),
            'price': lead.get('price', 0),
            'tags': tags,
            'source': cfields.get('utm_source', ''),
            'utm_campaign': cfields.get('utm_campaign', ''),
            'utm_medium': cfields.get('utm_medium', ''),
            'loss_reason_id': lead.get('loss_reason_id'),
            'created_at': datetime.fromtimestamp(lead['created_at']) if lead.get('created_at') else None,
            'updated_at': datetime.fromtimestamp(lead['updated_at']) if lead.get('updated_at') else None,
            'closed_at': datetime.fromtimestamp(lead['closed_at']) if lead.get('closed_at') else None,
            'custom_fields': cfields,
            'catalog_elements': catalog_elements,
        }

    # ── Batch Contact Fetch ──────────────────────────────────────────

    def fetch_contacts_batch(self, contact_ids: List[int]) -> Dict[int, dict]:
        """Fetch contacts in batches of 50."""
        result = {}
        batch_size = 50
        for i in range(0, len(contact_ids), batch_size):
            batch = contact_ids[i:i+batch_size]
            params = '&'.join(f'filter[id][]={cid}' for cid in batch)
            data = self._api_get(f'/api/v4/contacts?{params}&limit=250')
            if data:
                for contact in data.get('_embedded', {}).get('contacts', []):
                    result[contact['id']] = self._parse_contact(contact)
        logger.info(f"Fetched {len(result)}/{len(contact_ids)} contacts")
        return result

    def _parse_contact(self, contact: dict) -> dict:
        """Parse a contact into clean structure."""
        phone = ''
        email = ''
        cfields = {}
        for cf in (contact.get('custom_fields_values') or []):
            code = cf.get('field_code', '')
            fname = cf.get('field_name', '')
            vals = cf.get('values', [])
            if code == 'PHONE' and vals:
                phone = vals[0].get('value', '')
            elif code == 'EMAIL' and vals:
                email = vals[0].get('value', '')
            elif vals:
                cfields[fname] = vals[0].get('value', '')

        return {
            'contact_id': contact['id'],
            'name': contact.get('name', ''),
            'phone': phone,
            'email': email,
            'created_at': datetime.fromtimestamp(contact['created_at']) if contact.get('created_at') else None,
            'updated_at': datetime.fromtimestamp(contact['updated_at']) if contact.get('updated_at') else None,
            'custom_fields': cfields,
        }

    # ── Stage Changes ────────────────────────────────────────────────

    def fetch_stage_changes_by_date(self, ts_from: int, ts_to: int) -> List[dict]:
        """Fetch ALL lead_status_changed events in a date range. Much more efficient."""
        changes = []
        page = 1
        while True:
            data = self._api_get(
                f'/api/v4/events?limit=250&page={page}'
                f'&filter[type]=lead_status_changed'
                f'&filter[created_at][from]={ts_from}'
                f'&filter[created_at][to]={ts_to}'
            )
            if not data:
                break
            events = data.get('_embedded', {}).get('events', [])
            if not events:
                break
            for ev in events:
                change = self._parse_stage_change(ev)
                if change:
                    changes.append(change)
            if len(events) < 250:
                break
            page += 1
        logger.info(f"Found {len(changes)} stage changes in date range")
        return changes

    def fetch_stage_changes(self, lead_ids: List[int]) -> List[dict]:
        """Fetch lead_status_changed events for specific leads (fallback)."""
        changes = []
        for i in range(0, len(lead_ids), 10):
            batch = lead_ids[i:i+10]
            params = '&'.join(f'filter[entity][]={lid}' for lid in batch)
            data = self._api_get(
                f'/api/v4/events?{params}&filter[entity_type]=lead'
                f'&filter[type][]=lead_status_changed&limit=250'
            )
            if data:
                for ev in data.get('_embedded', {}).get('events', []):
                    change = self._parse_stage_change(ev)
                    if change:
                        changes.append(change)
        logger.info(f"Found {len(changes)} stage changes for {len(lead_ids)} leads")
        return changes

    # ── All Events by Date ─────────────────────────────────────────────

    def fetch_all_events_by_date(self, ts_from: int, ts_to: int,
                                  event_types: List[str] = None) -> List[dict]:
        """Fetch ALL events of specified types in a date range."""
        if not event_types:
            event_types = [
                'lead_status_changed', 'entity_tag_added', 'entity_linked',
                'lead_added', 'contact_added', 'talk_created',
                'incoming_chat_message', 'outgoing_chat_message',
            ]

        all_events = []
        for etype in event_types:
            page = 1
            while True:
                data = self._api_get(
                    f'/api/v4/events?limit=250&page={page}'
                    f'&filter[type]={etype}'
                    f'&filter[created_at][from]={ts_from}'
                    f'&filter[created_at][to]={ts_to}'
                )
                if not data:
                    break
                events = data.get('_embedded', {}).get('events', [])
                if not events:
                    break
                for ev in events:
                    all_events.append({
                        'event_id': ev['id'],
                        'event_type': ev['type'],
                        'entity_type': ev.get('entity_type', ''),
                        'entity_id': ev.get('entity_id'),
                        'value_before': ev.get('value_before', []),
                        'value_after': ev.get('value_after', []),
                        'created_by': ev.get('created_by', 0),
                        'created_at': datetime.fromtimestamp(ev['created_at']) if ev.get('created_at') else None,
                    })
                if len(events) < 250:
                    break
                page += 1

        logger.info(f"Fetched {len(all_events)} events across {len(event_types)} types")
        return all_events

    def _parse_stage_change(self, event: dict) -> Optional[dict]:
        after = event.get('value_after', [{}])
        before = event.get('value_before', [{}])
        if not after or not before:
            return None

        a = after[0].get('lead_status', {})
        b = before[0].get('lead_status', {})
        if not a and not b:
            return None

        new_pid = str(a.get('pipeline_id', ''))
        new_sid = str(a.get('id', ''))
        old_pid = str(b.get('pipeline_id', ''))
        old_sid = str(b.get('id', ''))

        return {
            'lead_id': event.get('entity_id'),
            'event_id': event.get('id'),
            'old_pipeline_id': b.get('pipeline_id'),
            'old_pipeline_name': self.mappings.get('pipelines', {}).get(old_pid, {}).get('name', ''),
            'old_status_id': b.get('id'),
            'old_stage_name': self.mappings.get('pipelines', {}).get(old_pid, {}).get('stages', {}).get(old_sid, {}).get('name', ''),
            'new_pipeline_id': a.get('pipeline_id'),
            'new_pipeline_name': self.mappings.get('pipelines', {}).get(new_pid, {}).get('name', ''),
            'new_status_id': a.get('id'),
            'new_stage_name': self.mappings.get('pipelines', {}).get(new_pid, {}).get('stages', {}).get(new_sid, {}).get('name', ''),
            'changed_by': event.get('created_by', 0),
            'changed_by_name': self.mappings.get('users', {}).get(str(event.get('created_by', '')), {}).get('name', ''),
            'changed_at': datetime.fromtimestamp(event['created_at']) if event.get('created_at') else None,
        }
