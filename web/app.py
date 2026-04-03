"""
Kommo Chat Scrapper - Web Dashboard & Onboarding
Flask app for Railway deployment.
"""
import json
import os
import psycopg2
import psycopg2.extras
from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'kommo-scrapper-2026')

DB_URL = os.environ.get('DATABASE_URL', '')

if not DB_URL:
    print("WARNING: DATABASE_URL not set!")


def get_db():
    if not DB_URL:
        raise Exception("DATABASE_URL environment variable not set")
    return psycopg2.connect(DB_URL)


def init_db():
    """Create tables if they don't exist."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kommo_app_settings (
                id SERIAL PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS kommo_contacts (contact_id BIGINT PRIMARY KEY, name TEXT, phone TEXT, email TEXT, created_at TIMESTAMP, updated_at TIMESTAMP, custom_fields JSONB DEFAULT '{}', fetched_at TIMESTAMP DEFAULT NOW());
            CREATE TABLE IF NOT EXISTS kommo_leads (lead_id BIGINT PRIMARY KEY, name TEXT, contact_id BIGINT, responsible_user_id BIGINT, responsible_user_name TEXT, pipeline_id BIGINT, pipeline_name TEXT, status_id BIGINT, stage_name TEXT, price NUMERIC DEFAULT 0, tags TEXT[], loss_reason TEXT, source TEXT, created_at TIMESTAMP, updated_at TIMESTAMP, closed_at TIMESTAMP, custom_fields JSONB DEFAULT '{}', fetched_at TIMESTAMP DEFAULT NOW());
            CREATE TABLE IF NOT EXISTS kommo_chats (id SERIAL PRIMARY KEY, talk_id BIGINT NOT NULL, lead_id BIGINT NOT NULL, contact_id BIGINT, chat_date DATE NOT NULL, conversation_ids TEXT[], total_messages INT DEFAULT 0, total_in INT DEFAULT 0, total_out INT DEFAULT 0, total_bot INT DEFAULT 0, total_human INT DEFAULT 0, total_media INT DEFAULT 0, interactions INT DEFAULT 0, has_bot_response BOOLEAN DEFAULT FALSE, has_human_response BOOLEAN DEFAULT FALSE, is_bot_only BOOLEAN DEFAULT FALSE, human_takeover_at_msg INT, bot_names TEXT[], human_agents TEXT[], attention_status TEXT DEFAULT 'unknown', last_message_direction TEXT, last_message_sender_type TEXT, first_contact_time TEXT, first_bot_time TEXT, first_human_time TEXT, last_message_time TEXT, bot_response_time_min NUMERIC, human_response_time_min NUMERIC, media_types TEXT[], scraped_at TIMESTAMP DEFAULT NOW(), UNIQUE(talk_id, chat_date));
            CREATE TABLE IF NOT EXISTS kommo_messages (id SERIAL PRIMARY KEY, talk_id BIGINT NOT NULL, lead_id BIGINT NOT NULL, contact_id BIGINT, chat_date DATE NOT NULL, msg_index INT NOT NULL, direction TEXT NOT NULL, sender_type TEXT, author TEXT, is_bot BOOLEAN DEFAULT FALSE, bot_name TEXT, channel TEXT, conversation_id TEXT, delivery_status TEXT, msg_type TEXT DEFAULT 'text', msg_text TEXT, msg_timestamp TEXT, created_at TIMESTAMP DEFAULT NOW(), UNIQUE(talk_id, chat_date, msg_index));
            CREATE TABLE IF NOT EXISTS kommo_stage_changes (id SERIAL PRIMARY KEY, lead_id BIGINT NOT NULL, event_id TEXT UNIQUE, old_pipeline_id BIGINT, old_pipeline_name TEXT, old_status_id BIGINT, old_stage_name TEXT, new_pipeline_id BIGINT, new_pipeline_name TEXT, new_status_id BIGINT, new_stage_name TEXT, changed_by BIGINT, changed_by_name TEXT, changed_at TIMESTAMP, created_at TIMESTAMP DEFAULT NOW());
            CREATE TABLE IF NOT EXISTS kommo_events (id SERIAL PRIMARY KEY, event_id TEXT UNIQUE, event_type TEXT NOT NULL, entity_type TEXT, entity_id BIGINT, value_before JSONB, value_after JSONB, created_by BIGINT, created_at TIMESTAMP, event_date DATE, fetched_at TIMESTAMP DEFAULT NOW());
            CREATE TABLE IF NOT EXISTS kommo_conversations_compiled (id SERIAL PRIMARY KEY, lead_id BIGINT NOT NULL UNIQUE, contact_id BIGINT, contact_name TEXT, contact_phone TEXT, responsible_user TEXT, pipeline_name TEXT, stage_name TEXT, conversation_json JSONB NOT NULL, conversation_text TEXT, total_messages INT DEFAULT 0, total_bot_msgs INT DEFAULT 0, total_human_msgs INT DEFAULT 0, total_contact_msgs INT DEFAULT 0, date_range_start DATE, date_range_end DATE, channels TEXT[], bots_used TEXT[], agents_involved TEXT[], attention_status TEXT, has_human_attention BOOLEAN DEFAULT FALSE, compiled_at TIMESTAMP DEFAULT NOW());
            CREATE TABLE IF NOT EXISTS kommo_daily_metrics (id SERIAL PRIMARY KEY, metric_date DATE NOT NULL UNIQUE, total_chats INT DEFAULT 0, total_messages INT DEFAULT 0, total_in INT DEFAULT 0, total_out INT DEFAULT 0, total_bot INT DEFAULT 0, total_human INT DEFAULT 0, total_media INT DEFAULT 0, chats_with_human INT DEFAULT 0, chats_bot_only INT DEFAULT 0, chats_unanswered INT DEFAULT 0, avg_interactions NUMERIC, avg_bot_response_min NUMERIC, avg_human_response_min NUMERIC, unique_contacts INT DEFAULT 0, unique_agents INT DEFAULT 0, top_bots JSONB DEFAULT '[]', top_agents JSONB DEFAULT '[]', computed_at TIMESTAMP DEFAULT NOW());
            CREATE TABLE IF NOT EXISTS kommo_scrape_errors (id SERIAL PRIMARY KEY, talk_id BIGINT, lead_id BIGINT, chat_date DATE, error_type TEXT, error_message TEXT, retry_count INT DEFAULT 0, resolved BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW());
            CREATE TABLE IF NOT EXISTS kommo_no_reply_tracking (id SERIAL PRIMARY KEY, lead_id BIGINT NOT NULL UNIQUE, contact_id BIGINT, contact_name TEXT, contact_phone TEXT, consecutive_out INT DEFAULT 0, last_out_date TEXT, last_out_text TEXT, days_without_reply INT DEFAULT 0, status TEXT DEFAULT 'no_reply', pipeline_name TEXT, stage_name TEXT, responsible_user TEXT, detected_at TIMESTAMP DEFAULT NOW());
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Database tables initialized")
    except Exception as e:
        print(f"DB init error: {e}")


def query(sql, params=None, fetchone=False):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        if fetchone:
            result = cur.fetchone()
        else:
            result = cur.fetchall()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"DB error: {e}")
        if fetchone:
            return None
        return []


def execute(sql, params=None):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        return str(e)


def get_setting(key):
    r = query("SELECT value FROM kommo_app_settings WHERE key=%s", (key,), fetchone=True)
    if r and 'value' in r:
        return r['value'] or ''
    return ''


def set_setting(key, value):
    execute("""
        INSERT INTO kommo_app_settings (key, value, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
    """, (key, value))


# ── Routes ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Main dashboard with charts and analytics."""
    setup = get_setting('setup_completed')
    has_data = query("SELECT COUNT(*) as c FROM kommo_chats", fetchone=True)
    if setup != 'true' and (not has_data or has_data.get('c', 0) == 0):
        return redirect(url_for('onboarding'))

    metrics = query("SELECT * FROM kommo_daily_metrics ORDER BY metric_date DESC LIMIT 14")
    latest = query("SELECT MAX(chat_date) as d FROM kommo_chats", fetchone=True)
    latest_date = latest['d'] if latest else None

    today_status = query("""
        SELECT attention_status, COUNT(*) as cnt
        FROM kommo_chats WHERE chat_date = (SELECT MAX(chat_date) FROM kommo_chats)
        GROUP BY attention_status
    """)

    counts = {}
    for t in ['kommo_contacts','kommo_leads','kommo_chats','kommo_messages',
              'kommo_stage_changes','kommo_events','kommo_conversations_compiled',
              'kommo_no_reply_tracking','kommo_scrape_errors']:
        r = query(f"SELECT COUNT(*) as c FROM {t}", fetchone=True)
        counts[t] = r['c'] if r else 0

    # Tag distribution
    tags = query("""
        SELECT unnest(tags) as tag, COUNT(*) as cnt
        FROM kommo_leads WHERE tags IS NOT NULL AND array_length(tags,1) > 0
        GROUP BY tag ORDER BY cnt DESC LIMIT 15
    """)

    # Top bots
    top_bots = query("""
        SELECT bot_name, COUNT(*) as cnt FROM kommo_messages
        WHERE is_bot=true AND bot_name != '' GROUP BY bot_name ORDER BY cnt DESC LIMIT 8
    """)

    # Top agents
    top_agents = query("""
        SELECT author, COUNT(*) as cnt FROM kommo_messages
        WHERE sender_type='agent' AND author != '' AND author != 'WhatsApp Business'
        GROUP BY author ORDER BY cnt DESC LIMIT 8
    """)

    # Pipeline distribution
    pipelines = query("""
        SELECT pipeline_name, COUNT(*) as cnt FROM kommo_leads
        WHERE pipeline_name != '' GROUP BY pipeline_name ORDER BY cnt DESC
    """)

    return render_template('dashboard.html',
                          metrics=metrics or [], today_status=today_status or [],
                          latest_date=latest_date, counts=counts,
                          tags=tags or [], top_bots=top_bots or [],
                          top_agents=top_agents or [], pipelines=pipelines or [])


@app.route('/onboarding', methods=['GET', 'POST'])
def onboarding():
    """Setup wizard for credentials."""
    if request.method == 'POST':
        fields = ['kommo_base_url', 'kommo_access_token', 'kommo_login_email',
                   'kommo_login_password']
        for f in fields:
            val = request.form.get(f, '').strip()
            if val:
                set_setting(f, val)

        # Test API connection
        import ssl, urllib.request
        token = request.form.get('kommo_access_token', '').strip()
        base = request.form.get('kommo_base_url', '').strip()
        if token and base:
            try:
                ctx = ssl.create_default_context()
                req = urllib.request.Request(
                    f"{base}/api/v4/account?with=amojo_id",
                    headers={'Authorization': f'Bearer {token}'}
                )
                with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                    data = json.loads(resp.read())
                    set_setting('kommo_account_name', data.get('name', ''))
                    set_setting('kommo_amojo_id', data.get('amojo_id', ''))
                    set_setting('setup_completed', 'true')
                    flash(f"Conectado a: {data['name']} (ID: {data['id']})", 'success')
                    return redirect(url_for('index'))
            except Exception as e:
                flash(f"Error de conexion API: {str(e)[:100]}", 'error')
        else:
            flash("Completa al menos la URL y el token", 'error')

    # Load current settings
    settings = {}
    for k in ['kommo_base_url', 'kommo_access_token', 'kommo_login_email',
              'kommo_login_password', 'kommo_account_name']:
        settings[k] = get_setting(k)

    return render_template('onboarding.html', settings=settings)


@app.route('/chats')
def chats():
    """Chat list view with status filter."""
    chat_date = request.args.get('date', '')
    status_filter = request.args.get('status', '')

    if not chat_date:
        r = query("SELECT MAX(chat_date) as d FROM kommo_chats", fetchone=True)
        chat_date = str(r['d']) if r and r.get('d') else ''

    status_clause = ""
    params = [chat_date]
    if status_filter:
        status_clause = "AND c.attention_status = %s"
        params.append(status_filter)

    chats_data = query(f"""
        SELECT c.talk_id, c.lead_id, c.total_messages, c.total_bot, c.total_human,
               c.attention_status, c.bot_names, c.human_agents,
               c.first_contact_time, c.last_message_time, c.total_in, c.total_out,
               l.name as lead_name, l.pipeline_name, l.stage_name,
               l.responsible_user_name, l.tags,
               ct.name as contact_name, ct.phone
        FROM kommo_chats c
        LEFT JOIN kommo_leads l ON c.lead_id = l.lead_id
        LEFT JOIN kommo_contacts ct ON l.contact_id = ct.contact_id
        WHERE c.chat_date = %s {status_clause}
        ORDER BY c.total_messages DESC
    """, params)

    dates = query("SELECT DISTINCT chat_date FROM kommo_chats ORDER BY chat_date DESC LIMIT 30")

    # Status counts for filter buttons
    status_counts = query("""
        SELECT attention_status, COUNT(*) as cnt FROM kommo_chats
        WHERE chat_date = %s GROUP BY attention_status
    """, (chat_date,))

    return render_template('chats.html',
                          chats=chats_data or [], current_date=chat_date,
                          dates=dates or [], status_filter=status_filter,
                          status_counts=status_counts or [])


@app.route('/chat/<int:talk_id>')
def chat_detail(talk_id):
    """Single chat conversation view."""
    chat_date = request.args.get('date', '')
    messages = query("""
        SELECT direction, sender_type, author, is_bot, bot_name,
               msg_type, msg_text, msg_timestamp, delivery_status
        FROM kommo_messages
        WHERE talk_id = %s AND (%s = '' OR chat_date = %s::date)
        ORDER BY msg_index
    """, (talk_id, chat_date, chat_date if chat_date else '2000-01-01'))

    chat_info = query("""
        SELECT c.*, l.name as lead_name, l.pipeline_name, l.stage_name,
               l.responsible_user_name, l.tags, l.price, l.source,
               l.created_at as lead_created, l.updated_at as lead_updated,
               ct.name as contact_name, ct.phone, ct.email
        FROM kommo_chats c
        LEFT JOIN kommo_leads l ON c.lead_id = l.lead_id
        LEFT JOIN kommo_contacts ct ON l.contact_id = ct.contact_id
        WHERE c.talk_id = %s
        ORDER BY c.chat_date DESC
        LIMIT 1
    """, (talk_id,), fetchone=True)

    return render_template('chat_detail.html',
                          messages=messages or [],
                          chat=chat_info or {})


@app.route('/no-reply')
def no_reply():
    """Chats without client response."""
    data = query("""
        SELECT * FROM kommo_no_reply_tracking
        WHERE status = 'no_reply'
        ORDER BY consecutive_out DESC
    """)
    return render_template('no_reply.html',
                          chats=data or [])


@app.route('/stages')
def stages():
    """Stage change history."""
    changes = query("""
        SELECT lead_id, old_pipeline_name, old_stage_name,
               new_pipeline_name, new_stage_name,
               changed_by_name, changed_at
        FROM kommo_stage_changes
        ORDER BY changed_at DESC
        LIMIT 100
    """)

    summary = query("""
        SELECT new_stage_name, COUNT(*) as cnt
        FROM kommo_stage_changes
        GROUP BY new_stage_name
        ORDER BY cnt DESC
        LIMIT 15
    """)

    return render_template('stages.html',
                          changes=changes or [],
                          summary=summary or [])


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """App settings page with credential validation."""
    if request.method == 'POST':
        for key in request.form:
            set_setting(key, request.form[key])
        flash('Settings saved', 'success')
        return redirect(url_for('settings'))

    all_settings = query("SELECT key, value, updated_at FROM kommo_app_settings ORDER BY key")

    # Group settings for better display
    groups = {
        'api': {'title': 'Kommo API', 'icon': 'cloud', 'keys': ['kommo_base_url', 'kommo_access_token', 'kommo_account_name', 'kommo_amojo_id']},
        'login': {'title': 'Login Scraping (sin 2FA)', 'icon': 'person-lock', 'keys': ['kommo_login_email', 'kommo_login_password']},
        'scrape': {'title': 'Scraping Config', 'icon': 'gear', 'keys': ['scrape_default_date', 'scrape_status_filter']},
        'system': {'title': 'Sistema', 'icon': 'cpu', 'keys': ['setup_completed']},
    }

    return render_template('settings.html', settings=all_settings or [], groups=groups)


@app.route('/api/validate-token', methods=['POST'])
def validate_token():
    """Validate Kommo API token."""
    import ssl, urllib.request
    token = get_setting('kommo_access_token')
    base = get_setting('kommo_base_url')
    if not token or not base:
        return jsonify({'ok': False, 'error': 'Token o URL no configurados'})
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(f"{base}/api/v4/account?with=amojo_id",
            headers={'Authorization': f'Bearer {token}'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read())
            set_setting('kommo_account_name', data.get('name', ''))
            set_setting('kommo_amojo_id', data.get('amojo_id', ''))
            return jsonify({'ok': True, 'account': data.get('name'), 'id': data.get('id')})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)[:100]})


@app.route('/api/stats')
def api_stats():
    """JSON API for dashboard stats."""
    metrics = query("SELECT * FROM kommo_daily_metrics ORDER BY metric_date DESC LIMIT 14")
    return jsonify(metrics or [])


@app.route('/api/health')
def api_health():
    """Health check - shows DB connection status and table counts."""
    result = {'db_url_set': bool(DB_URL), 'db_url_preview': DB_URL[:40] + '...' if DB_URL else 'NOT SET'}
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
        result['tables'] = cur.fetchone()[0]
        for t in ['kommo_chats', 'kommo_messages', 'kommo_leads', 'kommo_app_settings']:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                result[t] = cur.fetchone()[0]
            except:
                result[t] = 'TABLE_MISSING'
                conn.rollback()
        cur.close()
        conn.close()
        result['status'] = 'connected'
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)[:200]
    return jsonify(result)


# ── Main ─────────────────────────────────────────────────────────────

# Initialize DB on startup
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', False))
