"""Kommo CRM API v4 client for leads, contacts, talks, and events."""
import json
import logging
import os
import ssl
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class KommoAPIClient:
    """Client for Kommo CRM REST API v4."""

    def __init__(self, base_url: str, access_token: str, max_retries: int = 3):
        self.base_url = base_url.rstrip('/')
        self.access_token = access_token
        self.max_retries = max_retries
        self._ssl_ctx = ssl.create_default_context()

    @classmethod
    def from_env(cls, env_path: str = None):
        """Create client from .env file."""
        if env_path is None:
            env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
        env_vars = {}
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    env_vars[key.strip()] = val.strip()
        return cls(
            base_url=env_vars['KOMMO_BASE_URL'],
            access_token=env_vars['KOMMO_ACCESS_TOKEN'],
            max_retries=int(env_vars.get('MAX_RETRIES', '3')),
        )

    def _request(self, method: str, path: str, body: dict = None) -> dict:
        """Make HTTP request with retry logic and rate limit handling."""
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body else None
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }

        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=30) as resp:
                    if resp.status == 204:
                        return {'_embedded': {}}
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    retry_after = int(e.headers.get('Retry-After', 2))
                    logger.warning(f"Rate limited, waiting {retry_after}s (attempt {attempt+1})")
                    time.sleep(retry_after)
                    continue
                elif e.code == 204:
                    return {'_embedded': {}}
                else:
                    body_text = e.read().decode() if e.fp else ''
                    logger.error(f"HTTP {e.code} on {method} {path}: {body_text[:200]}")
                    if attempt < self.max_retries - 1 and e.code >= 500:
                        time.sleep(2 ** attempt)
                        continue
                    raise
            except Exception as e:
                logger.error(f"Request failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

    def get(self, path: str) -> dict:
        return self._request('GET', path)

    # ---- Account ----
    def get_account(self) -> dict:
        return self.get('/api/v4/account?with=amojo_id,users_groups,version')

    # ---- Leads ----
    def get_leads(self, limit: int = 250, page: int = 1, filters: dict = None, with_: str = None) -> dict:
        params = {'limit': limit, 'page': page}
        if with_:
            params['with'] = with_
        if filters:
            for k, v in filters.items():
                params[k] = v
        qs = urllib.parse.urlencode(params, doseq=True)
        return self.get(f'/api/v4/leads?{qs}')

    def get_all_leads(self, filters: dict = None, with_: str = 'contacts') -> list:
        """Paginate through all leads matching filters."""
        all_leads = []
        page = 1
        while True:
            data = self.get_leads(limit=250, page=page, filters=filters, with_=with_)
            leads = data.get('_embedded', {}).get('leads', [])
            if not leads:
                break
            all_leads.extend(leads)
            if '_links' not in data or 'next' not in data['_links']:
                break
            page += 1
            time.sleep(0.3)  # respect rate limits
        return all_leads

    # ---- Contacts ----
    def get_contact(self, contact_id: int) -> dict:
        return self.get(f'/api/v4/contacts/{contact_id}?with=leads')

    # ---- Talks (active chats) ----
    def get_talks(self, limit: int = 250, page: int = 1, filters: dict = None) -> dict:
        params = {'limit': limit, 'page': page}
        if filters:
            for k, v in filters.items():
                params[k] = v
        qs = urllib.parse.urlencode(params, doseq=True)
        return self.get(f'/api/v4/talks?{qs}')

    def get_all_talks(self, filters: dict = None) -> list:
        """Paginate through all talks."""
        all_talks = []
        page = 1
        while True:
            data = self.get_talks(limit=250, page=page, filters=filters)
            talks = data.get('_embedded', {}).get('talks', [])
            if not talks:
                break
            all_talks.extend(talks)
            if len(talks) < 250:
                break
            page += 1
            time.sleep(0.3)
        return all_talks

    # ---- Events (chat messages metadata) ----
    def get_events(self, limit: int = 100, page: int = 1, filters: dict = None) -> dict:
        params = {'limit': limit, 'page': page}
        if filters:
            for k, v in filters.items():
                params[k] = v
        qs = urllib.parse.urlencode(params, doseq=True)
        return self.get(f'/api/v4/events?{qs}')

    def get_chat_events(self, limit: int = 100, page: int = 1) -> list:
        """Get events filtered to chat messages only."""
        all_events = []
        data = self.get_events(limit=limit, page=page)
        for event in data.get('_embedded', {}).get('events', []):
            if 'chat_message' in event.get('type', ''):
                all_events.append(event)
        return all_events

    # ---- Notes (for leads/contacts) ----
    def get_lead_notes(self, lead_id: int, limit: int = 250) -> list:
        try:
            data = self.get(f'/api/v4/leads/{lead_id}/notes?limit={limit}')
            return data.get('_embedded', {}).get('notes', [])
        except Exception:
            return []

    # ---- Pipelines ----
    def get_pipelines(self) -> dict:
        return self.get('/api/v4/leads/pipelines')

    # ---- Users ----
    def get_users(self) -> list:
        data = self.get('/api/v4/users?limit=250')
        return data.get('_embedded', {}).get('users', [])


def get_today_timestamp_range():
    """Get start/end timestamps for today (UTC-5 Peru time)."""
    from datetime import timedelta
    now = datetime.now(timezone.utc) - timedelta(hours=5)  # Peru is UTC-5
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    start_ts = int(start.timestamp()) + 5 * 3600  # convert back
    end_ts = int(end.timestamp()) + 5 * 3600
    return start_ts, end_ts
