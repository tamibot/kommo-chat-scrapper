#!/usr/bin/env python3
"""
Kommo Scraper v3 - Production-grade daily chat extraction.

Features:
- Robust Selenium with retries, anti-ban delays, error recovery
- API enrichment: leads, contacts (phone/email), tags, stage changes
- Compiled conversations per client (JSON for LLM)
- Daily metrics aggregation
- PostgreSQL storage with full analytics
- Rate-limited API calls (max 6/s, safe under 7/s limit)

Usage:
    python scripts/scrape_v3.py                        # yesterday, all chats
    python scripts/scrape_v3.py --date current_day     # today
    python scripts/scrape_v3.py --max-chats 15         # test with 15
    python scripts/scrape_v3.py --skip-enrich          # skip API enrichment
    python scripts/scrape_v3.py --skip-compile         # skip conversation compilation
"""
import argparse, json, os, random, sys, time
from datetime import datetime, date, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

from src.kommo.enrichment import KommoEnrichment
from src.kommo.database import KommoDB

# ── Config ───────────────────────────────────────────────────────────
ENV = {}
with open(os.path.join(os.path.dirname(__file__), '..', '.env')) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1); ENV[k.strip()] = v.strip()

SESSION_DIR = '/tmp/kommo_scraper_session'
SUBDOMAIN = 'propertamibotcom'

# ── Anti-ban config ──────────────────────────────────────────────────
MIN_DELAY = 1.5       # min seconds between chat navigations
MAX_DELAY = 2.5       # max seconds (randomized)
EXPAND_WAIT = 1.0     # wait after clicking "Más"
SCROLL_WAIT = 0.5     # wait between scroll iterations

# ── JS Scripts ───────────────────────────────────────────────────────

JS_EXTRACT = """
return (function() {
    var notes = document.querySelectorAll('.feed-note-wrapper-amojo');
    var msgs = []; var convIds = new Set();

    for (var i = 0; i < notes.length; i++) {
        var n = notes[i];

        // === DIRECTION: use feed-note CSS classes ===
        // Kommo adds 'feed-note-incoming' to the inner .feed-note for client messages
        // For outgoing (bot/agent), the .feed-note does NOT have 'feed-note-incoming'
        // The .feed-note__talk-outgoing block is a CONVERSATION FOOTER (not per-message direction)
        var feedNote = n.querySelector('.feed-note.feed-note-external');
        var hasIncoming = feedNote && feedNote.className.indexOf('feed-note-incoming') >= 0;
        var dir = hasIncoming ? 'IN' : 'OUT';

        // === TIMESTAMP: works for both IN and OUT ===
        var dateEl = n.querySelector('.js-feed-note__date, .feed-note__date');
        var timestamp = dateEl ? dateEl.textContent.trim() : '';

        // === AUTHOR: works for both IN and OUT ===
        var authorEl = n.querySelector('.feed-note__amojo-user, .js-amojo-author');
        var author = authorEl ? authorEl.textContent.trim() : '';

        // === CONVERSATION ID: from outgoing title (only in OUT, normal) ===
        var convId = '';
        var titleEl = n.querySelector('.feed-note__talk-outgoing-title, .feed-note__talk-outgoing-title_opened, .info-bubble__text');
        if (titleEl) {
            var cm = titleEl.textContent.match(/A(\\d+)/);
            if (cm) { convId = cm[1]; convIds.add(cm[1]); }
        }

        // === DELIVERY STATUS: Read/Delivered (only on OUT, normal) ===
        var statusEl = n.querySelector('.message_delivery-status_checkmark, .feed-note__delivery-status');
        var deliveryStatus = statusEl ? statusEl.textContent.trim() : '';

        // === MESSAGE TEXT: join ALL paragraph elements (some msgs have multiple) ===
        var msgParts = n.querySelectorAll('.feed-note__message_paragraph');
        var msg = '';
        if (msgParts.length > 0) {
            var texts = [];
            msgParts.forEach(function(p) {
                // Skip quoted/reply text (inside quotation containers)
                if (!p.closest('.quotation__message-text')) {
                    texts.push(p.textContent.trim());
                }
            });
            msg = texts.join('\\n').substring(0, 2000);
        }

        // === BOT DETECTION: only on OUT messages ===
        var isBot = false; var botName = '';
        if (dir === 'OUT') {
            var authorLower = author.toLowerCase();
            if (authorLower.indexOf('salesbot') >= 0) {
                isBot = true;
                var bm = author.match(/SalesBot\\s*\\((.+?)\\)/i);
                botName = bm ? bm[1] : 'SalesBot';
            } else if (authorLower.indexOf('tami bot') >= 0 || authorLower.indexOf('tamibot') >= 0) {
                isBot = true; botName = 'TamiBot';
            } else if (authorLower.indexOf('bot ') >= 0 || authorLower.indexOf(' bot') >= 0) {
                isBot = true; botName = author;
            }
        }

        // === SENDER TYPE: improved logic ===
        var senderType;
        if (dir === 'OUT') {
            if (isBot) {
                senderType = 'bot';
            } else if (author === 'WhatsApp Business' || author === 'TikTok') {
                // These are channel names, not agents - treat as system/channel
                senderType = 'system';
            } else {
                senderType = 'agent';
            }
        } else {
            senderType = 'contact';
        }

        // === MEDIA TYPE DETECTION ===
        var mediaType = 'text';
        if (n.querySelectorAll('[class*="sticker"]').length) mediaType = 'sticker';
        else if (n.querySelectorAll('[class*="audio"],[class*="voice"]').length) mediaType = 'audio';
        else if (n.querySelectorAll('[class*="video"]').length) mediaType = 'video';
        else if (n.querySelectorAll('img[src*="file"],[class*="image"],[class*="photo"],[class*="picture"]').length) mediaType = 'image';
        else if (n.querySelectorAll('[class*="file"],[class*="attach"],[class*="document"]').length) mediaType = 'file';
        else if (n.querySelectorAll('[class*="location"],[class*="map"]').length) mediaType = 'location';
        else if (n.querySelectorAll('[class*="rich-link"]').length) mediaType = 'link';

        if (msg || mediaType !== 'text') {
            msgs.push({
                dir: dir, timestamp: timestamp, author: author,
                sender_type: senderType, is_bot: isBot, bot_name: botName,
                conv_id: convId, delivery_status: deliveryStatus,
                type: mediaType, text: msg
            });
        }
    }
    return {messages:msgs, conversation_ids:Array.from(convIds), msg_count:msgs.length};
})()
"""

# ── Driver ───────────────────────────────────────────────────────────

def create_driver():
    options = Options()
    options.add_argument(f"--user-data-dir={SESSION_DIR}")
    options.add_argument("--profile-directory=Scraper")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    d = webdriver.Chrome(options=options)
    d.set_page_load_timeout(30)
    return d


def login(driver):
    for attempt in range(3):
        try:
            driver.get(f"https://{SUBDOMAIN}.kommo.com/")
            time.sleep(4)
            if 'Authorization' not in driver.title and 'Autorización' not in driver.title:
                return True
            driver.find_element(By.CSS_SELECTOR, 'input[type="text"]').send_keys(ENV['KOMMO_LOGIN_EMAIL'])
            driver.find_element(By.CSS_SELECTOR, 'input[type="password"]').send_keys(ENV['KOMMO_LOGIN_PASSWORD'])
            driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(6)
            if 'Authorization' not in driver.title and 'Autorización' not in driver.title:
                return True
        except Exception as e:
            print(f"  Login attempt {attempt+1} failed: {e}")
            time.sleep(3)
    return False


def get_day_unix_range(target_date):
    """Get Unix timestamp range for a single day in Peru time (UTC-5).
    Matches exactly what Kommo UI uses: filter[date][from]=X&filter[date][to]=Y
    Example: Apr 1 -> from=1775019600 to=1775105999"""
    PERU = timezone(timedelta(hours=-5))
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=PERU)
    day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=PERU)
    return int(day_start.timestamp()), int(day_end.timestamp())


def collect_targets_via_api(target_date, filter_mode='conversations'):
    """Get chat targets for a day using Events API.

    filter_mode:
        'all' - all leads with any chat activity
        'conversations' - only leads with both IN and OUT (real conversations)
        'conversations+pending' - conversations + leads with only IN (pending our response)

    Returns list of {talk_id, lead_id, contact_id, in_events, out_events, category}
    """
    import ssl, urllib.request, urllib.error
    env = {}
    with open(os.path.join(os.path.dirname(__file__), '..', '.env')) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1); env[k.strip()] = v.strip()

    token = env.get('KOMMO_ACCESS_TOKEN', '')
    base = env.get('KOMMO_BASE_URL', f'https://{SUBDOMAIN}.kommo.com')
    ctx = ssl.create_default_context()

    ts_from, ts_to = get_day_unix_range(target_date)

    # Phase 1: Collect all events and group by lead_id
    leads = {}  # lead_id -> {talk_ids, in, out, contact_id}
    page = 1
    while True:
        try:
            url = (f"{base}/api/v4/events?limit=250&page={page}"
                   f"&filter[type][]=incoming_chat_message"
                   f"&filter[type][]=outgoing_chat_message"
                   f"&filter[created_at][from]={ts_from}"
                   f"&filter[created_at][to]={ts_to}")
            req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                data = json.loads(resp.read())
            events = data.get('_embedded', {}).get('events', [])
            if not events:
                break
            for e in events:
                lid = e.get('entity_id')
                if lid not in leads:
                    leads[lid] = {'talk_ids': {}, 'in': 0, 'out': 0, 'contact_id': None, 'origins': set()}
                if e['type'] == 'incoming_chat_message':
                    leads[lid]['in'] += 1
                else:
                    leads[lid]['out'] += 1
                va = e.get('value_after', [{}])
                if va and va[0].get('message'):
                    msg = va[0]['message']
                    tid = msg.get('talk_id')
                    origin = msg.get('origin', '')
                    if tid:
                        leads[lid]['talk_ids'][tid] = origin  # talk_id -> origin mapping
                        if origin:
                            leads[lid]['origins'].add(origin)
                emb = e.get('_embedded', {}).get('entity', {})
                if emb.get('linked_talk_contact_id'):
                    leads[lid]['contact_id'] = emb['linked_talk_contact_id']
            if len(events) < 250:
                break
            page += 1
            time.sleep(0.15)
        except Exception as ex:
            print(f"    API error page {page}: {ex}")
            break

    # Phase 2: Classify and filter
    targets = []
    stats = {'conversations': 0, 'pending': 0, 'follow_up': 0, 'masivo': 0}

    for lid, act in leads.items():
        if act['in'] > 0 and act['out'] > 0:
            category = 'conversation'
            stats['conversations'] += 1
        elif act['in'] > 0 and act['out'] == 0:
            category = 'pending'
            stats['pending'] += 1
        elif act['out'] <= 2:
            category = 'follow_up'
            stats['follow_up'] += 1
            continue  # Skip follow-ups
        else:
            category = 'masivo'
            stats['masivo'] += 1
            continue  # Skip masivos

        # Apply filter
        include = False
        if filter_mode == 'all':
            include = True
        elif filter_mode == 'conversations' and category == 'conversation':
            include = True
        elif filter_mode == 'conversations+pending' and category in ('conversation', 'pending'):
            include = True

        if include:
            # Use the most recent talk_id for this lead (highest talk_id)
            talk_items = sorted(act['talk_ids'].items(), key=lambda x: int(x[0]), reverse=True)
            if talk_items:
                tid, origin = talk_items[0]
                targets.append({
                    'talk_id': str(tid),
                    'lead_id': str(lid),
                    'contact_id': act['contact_id'],
                    'origin': origin,  # waba, instagram_business, tiktok_kommo, facebook
                    'origins_all': list(act['origins']),  # all channels this lead uses
                    'in_events': act['in'],
                    'out_events': act['out'],
                    'category': category,
                })

    print(f"    Events: {page} pages | Leads: {len(leads)} | Conv: {stats['conversations']} | "
          f"Pending: {stats['pending']} | Follow-up: {stats['follow_up']} | Masivo: {stats['masivo']}")

    return targets


def collect_targets(driver, date_preset, status, target_date=None):
    """Scroll virtual list and accumulate ALL chat targets.
    If target_date is provided, uses Unix timestamp filter (more reliable)."""
    if target_date:
        from_ts, to_ts = get_day_unix_range(target_date)
        url = (f"https://{SUBDOMAIN}.kommo.com/chats/"
               f"?filter%5Bdate%5D%5Bfrom%5D={from_ts}"
               f"&filter%5Bdate%5D%5Bto%5D={to_ts}"
               f"&filter%5Bstatus%5D%5B%5D={status}")
    else:
        url = (f"https://{SUBDOMAIN}.kommo.com/chats/"
               f"?filter%5Bdate%5D%5Bdate_preset%5D={date_preset}"
               f"&filter%5Bstatus%5D%5B%5D={status}")
    driver.get(url)
    time.sleep(6)

    driver.execute_script("window.__ac = {};")
    prev = 0; stale = 0
    for i in range(500):  # Support up to ~1000+ chats
        count = driver.execute_script("""
            var ls = document.querySelectorAll('a[href*="/chats/"][href*="/leads/detail/"]');
            for (var a of ls) {
                var m = a.href.match(/chats\\/(\\d+)\\/leads\\/detail\\/(\\d+)/);
                if (m) window.__ac[m[1]] = m[2];
            }
            if (ls.length > 0) ls[ls.length-1].scrollIntoView({block:'end'});
            return Object.keys(window.__ac).length;
        """)
        if count == prev:
            stale += 1
            # For large lists, be more patient: wait 12 stale rounds
            if stale >= 12: break
        else:
            stale = 0
            if count % 100 == 0:
                print(f"    {count} chats loaded...", flush=True)
        prev = count
        time.sleep(SCROLL_WAIT)

    return driver.execute_script("""
        var out = [];
        for (var t in window.__ac) out.push({talk_id:t, lead_id:window.__ac[t]});
        return out;
    """)


def extract_chat_robust(driver, talk_id, lead_id, max_retries=2):
    """Extract chat with retries and error recovery."""
    for attempt in range(max_retries):
        try:
            url = f"https://{SUBDOMAIN}.kommo.com/chats/{talk_id}/leads/detail/{lead_id}"
            driver.get(url)
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            time.sleep(delay)

            # Expand collapsed messages (up to 5 rounds)
            for _ in range(5):
                expanded = driver.execute_script("""
                    var c=0;
                    document.querySelectorAll('a,span,div').forEach(function(el){
                        if(el.innerText && el.innerText.trim().match(/^Más \\d+ de \\d+$/)){el.click();c++;}
                    });
                    return c;
                """)
                if expanded:
                    time.sleep(EXPAND_WAIT)
                else:
                    break

            result = driver.execute_script(JS_EXTRACT)
            if result and result.get('messages') is not None:
                return result
            return {'messages': [], 'conversation_ids': [], 'msg_count': 0}

        except WebDriverException as e:
            if attempt < max_retries - 1:
                time.sleep(3)
            else:
                return {'messages': [], 'conversation_ids': [], 'msg_count': 0}


def parse_chat_date_from_messages(messages):
    """Extract the actual date from message timestamps.
    Kommo formats: 'DD.MM.YYYY HH:MM', 'Yesterday HH:MM', 'Today HH:MM'"""
    import re
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc) - timedelta(hours=5)  # Peru time

    for msg in messages:
        ts = msg.get('timestamp', '')
        if not ts:
            continue

        # Try DD.MM.YYYY format (absolute date from older chats)
        m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})', ts)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(year, month, day)

        # "Yesterday" = now - 1 day
        if ts.startswith('Yesterday'):
            return (now - timedelta(days=1)).date()

        # "Today" = now
        if ts.startswith('Today'):
            return now.date()

    # Fallback: return today
    return now.date()


def compute_analytics(messages):
    """Compute chat analytics from message list."""
    if not messages:
        return {
            'total_messages': 0, 'in_count': 0, 'out_count': 0,
            'bot_count': 0, 'human_count': 0, 'media_count': 0,
            'interactions': 0, 'has_human_response': False,
            'human_takeover_at_msg': None, 'bot_names': [],
            'human_agents': [], 'media_types': [],
            'first_contact_time': '', 'first_bot_time': '', 'first_human_time': '',
        }

    in_msgs = [m for m in messages if m['dir'] == 'IN']
    bot_msgs = [m for m in messages if m.get('is_bot')]
    human_msgs = [m for m in messages if m['dir'] == 'OUT' and not m.get('is_bot')]
    media_msgs = [m for m in messages if m['type'] != 'text']

    # Interactions (direction changes)
    interactions = 0
    prev_dir = None
    for m in messages:
        if m['dir'] != prev_dir and prev_dir:
            interactions += 1
        prev_dir = m['dir']

    # Human takeover point
    takeover = None
    for i, m in enumerate(messages):
        if m['dir'] == 'OUT' and not m.get('is_bot'):
            takeover = i
            break

    first_contact = next((m for m in messages if m['dir'] == 'IN'), None)
    first_bot = next((m for m in messages if m.get('is_bot')), None)
    first_human = next((m for m in messages if m['dir'] == 'OUT' and not m.get('is_bot')), None)

    return {
        'total_messages': len(messages),
        'in_count': len(in_msgs),
        'out_count': len(messages) - len(in_msgs),
        'bot_count': len(bot_msgs),
        'human_count': len(human_msgs),
        'media_count': len(media_msgs),
        'interactions': interactions,
        'has_human_response': len(human_msgs) > 0,
        'human_takeover_at_msg': takeover,
        'bot_names': list(set(m.get('bot_name','') for m in bot_msgs if m.get('bot_name'))),
        'human_agents': list(set(m.get('author','') for m in human_msgs if m.get('author'))),
        'media_types': list(set(m['type'] for m in media_msgs)),
        'first_contact_time': first_contact['timestamp'] if first_contact else '',
        'first_bot_time': first_bot['timestamp'] if first_bot else '',
        'first_human_time': first_human['timestamp'] if first_human else '',
    }


# ── Main ─────────────────────────────────────────────────────────────

def run_single_day(args, chat_date, date_preset, use_unix_date=False):
    """Run scraper for a single day. Core logic extracted for historical reuse.
    If use_unix_date=True, uses exact Unix timestamp filter instead of preset."""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'output', f'{date_preset}_{ts}')
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  KOMMO SCRAPER v3 - {chat_date}")
    print(f"  Filter: {date_preset} | Max: {args.max_chats or 'all'}")
    print(f"{'='*60}")

    t0 = time.time()

    # PHASE 1: Scrape
    print(f"\n[1/6] Login...")
    driver = create_driver()
    if not login(driver):
        print("  FAILED. Skipping."); driver.quit(); return None
    print("  OK")

    print(f"[2/6] Collecting chat targets...")
    t_collect = time.time()

    # Primary: Events API (fast, gets real conversations)
    targets = collect_targets_via_api(chat_date, filter_mode='conversations+pending')

    if targets:
        print(f"  API: {len(targets)} targets in {time.time()-t_collect:.1f}s")
    else:
        # Fallback: Selenium scroll
        print(f"  API returned 0, fallback to Selenium...")
        targets = collect_targets(driver, date_preset, args.status,
                                  target_date=chat_date if use_unix_date else None)
        print(f"  Selenium: {len(targets)} targets in {time.time()-t_collect:.1f}s")

    total = len(targets) if args.max_chats == 0 else min(args.max_chats, len(targets))
    print(f"  Will scrape {total}")

    if total == 0:
        print("  No chats found. Skipping.")
        driver.quit()
        return None

    print(f"[3/6] Scraping {total} chats...")
    results = []
    total_msgs = 0
    errors = 0

    for idx in range(total):
        t = targets[idx]
        data = extract_chat_robust(driver, t['talk_id'], t['lead_id'])
        analytics = compute_analytics(data['messages'])
        total_msgs += data['msg_count']
        if data['msg_count'] == 0:
            errors += 1

        # Use the filter date (the day we're scraping) as chat_date
        # This is correct because we filter by day, so the chat had activity on this day
        results.append({
            'talk_id': t['talk_id'],
            'lead_id': t['lead_id'],
            'contact_id': t.get('contact_id'),
            'chat_date': str(chat_date),
            'origin': t.get('origin', ''),
            'origins_all': t.get('origins_all', []),
            'category': t.get('category', ''),
            'in_events': t.get('in_events', 0),
            'out_events': t.get('out_events', 0),
            'conversation_ids': data['conversation_ids'],
            'msg_count': data['msg_count'],
            'analytics': analytics,
            'messages': data['messages'],
        })

        if (idx+1) % 10 == 0 or idx == total-1:
            elapsed = time.time() - t0
            bot = sum(r['analytics']['bot_count'] for r in results)
            hum = sum(r['analytics']['human_count'] for r in results)
            rate = (idx+1) / elapsed * 60
            print(f"  [{idx+1}/{total}] {total_msgs} msgs (B:{bot} H:{hum}) | {elapsed:.0f}s | {rate:.0f}/min | err:{errors}")

    driver.quit()

    # PHASE 2: Enrichment
    leads_map = {}
    contacts_map = {}
    stage_changes = []
    all_events = []

    if not args.skip_enrich:
        print(f"\n[4/6] API enrichment...")
        enricher = KommoEnrichment()
        lead_ids = list(set(int(r['lead_id']) for r in results))
        leads_map = enricher.fetch_leads_batch(lead_ids)
        contact_ids = list(set(l['contact_id'] for l in leads_map.values() if l.get('contact_id')))
        contacts_map = enricher.fetch_contacts_batch(contact_ids)
        for r in results:
            lid = int(r['lead_id'])
            r['contact_id'] = leads_map.get(lid, {}).get('contact_id')

        from datetime import timezone as tz
        day_start = datetime.combine(chat_date, datetime.min.time()).replace(tzinfo=tz.utc)
        day_end = datetime.combine(chat_date, datetime.max.time()).replace(tzinfo=tz.utc)
        ts_from = int(day_start.timestamp()) - 5*3600
        ts_to = int(day_end.timestamp()) - 5*3600

        if not args.skip_stages:
            stage_changes = enricher.fetch_stage_changes_by_date(ts_from, ts_to)
        all_events = enricher.fetch_all_events_by_date(ts_from, ts_to, event_types=[
            'lead_status_changed', 'entity_tag_added', 'entity_linked',
            'lead_added', 'contact_added', 'talk_created',
        ])
        print(f"  Leads: {len(leads_map)} | Contacts: {len(contacts_map)} | Stages: {len(stage_changes)} | Events: {len(all_events)}")

    # PHASE 3: Save to DB
    print(f"[5/6] Saving to PostgreSQL...")
    db = KommoDB()
    if contacts_map:
        db.upsert_contacts(contacts_map)
    if leads_map:
        db.upsert_leads(leads_map)
    for r in results:
        try:
            real_d = date.fromisoformat(r['chat_date']) if r.get('chat_date') else chat_date
            db.upsert_chat(r, real_d)
        except Exception as e:
            db.log_error(int(r['talk_id']), int(r['lead_id']), chat_date, 'db_insert', str(e))
    if stage_changes:
        db.upsert_stage_changes(stage_changes)
    if all_events:
        db.upsert_events(all_events)
    if not args.skip_compile:
        compiled = 0
        for r in results:
            try:
                real_d2 = date.fromisoformat(r['chat_date']) if r.get('chat_date') else chat_date
                db.compile_conversation(int(r['lead_id']), real_d2)
                compiled += 1
            except Exception:
                pass
        print(f"  Compiled {compiled} conversations")
    no_reply = db.detect_no_reply_chats(chat_date)
    db.compute_daily_metrics(chat_date)
    print(f"  No-reply: {no_reply} | Events: {len(all_events)}")

    # PHASE 4: JSON
    print(f"[6/6] Saving JSON...")
    summary = {
        'bot_messages': sum(r['analytics']['bot_count'] for r in results),
        'human_messages': sum(r['analytics']['human_count'] for r in results),
        'contact_messages': sum(r['analytics']['in_count'] for r in results),
        'with_human': sum(1 for r in results if r['analytics']['has_human_response']),
        'bot_only': sum(1 for r in results if not r['analytics']['has_human_response'] and r['analytics']['bot_count'] > 0),
        'no_reply': no_reply,
        'errors': errors,
        'stage_changes': len(stage_changes),
        'events': len(all_events),
    }
    output = {
        'version': '3.0', 'chat_date': str(chat_date),
        'scraped_at': datetime.now().isoformat(),
        'elapsed_seconds': round(time.time() - t0, 1),
        'total_chats': len(results), 'total_messages': total_msgs,
        'summary': summary, 'conversations': results,
    }
    with open(os.path.join(out_dir, 'chats.json'), 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    db.close()
    elapsed = time.time() - t0
    print(f"  Done: {len(results)} chats, {total_msgs} msgs in {elapsed:.0f}s")
    return summary


def main():
    parser = argparse.ArgumentParser(description='Kommo Scraper v3')
    parser.add_argument('--date', default='yesterday')
    parser.add_argument('--status', default='opened')
    parser.add_argument('--max-chats', type=int, default=0)
    parser.add_argument('--skip-enrich', action='store_true')
    parser.add_argument('--skip-compile', action='store_true')
    parser.add_argument('--skip-stages', action='store_true')
    # Historical range
    parser.add_argument('--from-date', type=str, help='Start date YYYY-MM-DD for historical scrape')
    parser.add_argument('--to-date', type=str, help='End date YYYY-MM-DD for historical scrape')
    args = parser.parse_args()

    # Historical range mode
    if args.from_date:
        from_d = date.fromisoformat(args.from_date)
        to_d = date.fromisoformat(args.to_date) if args.to_date else from_d
        print(f"{'='*60}")
        print(f"  HISTORICAL SCRAPE: {from_d} to {to_d}")
        print(f"  Days: {(to_d - from_d).days + 1}")
        print(f"{'='*60}")

        now = datetime.now(timezone.utc) - timedelta(hours=5)
        current = from_d
        day_results = []
        while current <= to_d:
            delta = (now.date() - current).days
            if delta == 0:
                preset = 'current_day'
            elif delta == 1:
                preset = 'yesterday'
            else:
                # For older dates, use custom date filter via URL
                preset = f'custom_{current.isoformat()}'

            summary = run_single_day(args, current, preset, use_unix_date=True)
            if summary:
                day_results.append({'date': str(current), 'summary': summary})
            current += timedelta(days=1)

        print(f"\n{'='*60}")
        print(f"  HISTORICAL COMPLETE: {len(day_results)} days processed")
        for d in day_results:
            s = d['summary']
            print(f"    {d['date']}: {s.get('bot_messages',0)+s.get('human_messages',0)+s.get('contact_messages',0)} msgs | H:{s.get('with_human',0)} B:{s.get('bot_only',0)}")
        print(f"{'='*60}")
        return

    # Multi-day presets
    now = datetime.now(timezone.utc) - timedelta(hours=5)

    if args.date == 'previous_week':
        # Scrape each day of last week individually (more reliable)
        today = now.date()
        last_monday = today - timedelta(days=today.weekday() + 7)
        print(f"{'='*60}")
        print(f"  PREVIOUS WEEK: {last_monday} to {last_monday + timedelta(days=6)}")
        print(f"  Scraping 7 days individually with Unix timestamp filters")
        print(f"{'='*60}")
        for i in range(7):
            day = last_monday + timedelta(days=i)
            run_single_day(args, day, f'day_{day}', use_unix_date=True)

    elif args.date == 'current_week':
        today = now.date()
        monday = today - timedelta(days=today.weekday())
        days_so_far = (today - monday).days + 1
        print(f"{'='*60}")
        print(f"  CURRENT WEEK: {monday} to {today} ({days_so_far} days)")
        print(f"{'='*60}")
        for i in range(days_so_far):
            day = monday + timedelta(days=i)
            run_single_day(args, day, f'day_{day}', use_unix_date=True)

    elif args.date == 'yesterday':
        chat_date = (now - timedelta(days=1)).date()
        run_single_day(args, chat_date, 'yesterday', use_unix_date=True)

    elif args.date == 'current_day':
        run_single_day(args, now.date(), 'current_day')

    else:
        run_single_day(args, now.date(), args.date)


if __name__ == '__main__':
    main()
