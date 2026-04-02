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


def get_db():
    return psycopg2.connect(DB_URL)


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
    """Main dashboard."""
    setup = get_setting('setup_completed')
    if setup != 'true':
        return redirect(url_for('onboarding'))

    # Get daily metrics
    metrics = query("""
        SELECT * FROM kommo_daily_metrics ORDER BY metric_date DESC LIMIT 14
    """)

    # Get today's summary
    today = query("""
        SELECT attention_status, COUNT(*) as cnt
        FROM kommo_chats
        WHERE chat_date = (SELECT MAX(chat_date) FROM kommo_chats)
        GROUP BY attention_status
    """)

    # Latest date
    latest = query("SELECT MAX(chat_date) as d FROM kommo_chats", fetchone=True)
    latest_date = latest['d'] if latest else None

    # Table counts
    counts = {}
    for t in ['kommo_contacts', 'kommo_leads', 'kommo_chats', 'kommo_messages',
              'kommo_stage_changes', 'kommo_events', 'kommo_conversations_compiled',
              'kommo_no_reply_tracking', 'kommo_scrape_errors']:
        r = query(f"SELECT COUNT(*) as c FROM {t}", fetchone=True)
        counts[t] = r['c'] if r else 0

    return render_template('dashboard.html',
                          metrics=metrics or [],
                          today_status=today or [],
                          latest_date=latest_date,
                          counts=counts)


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
    """Chat list view."""
    chat_date = request.args.get('date', '')
    if not chat_date:
        r = query("SELECT MAX(chat_date) as d FROM kommo_chats", fetchone=True)
        chat_date = str(r['d']) if r and r.get('d') else ''

    chats_data = query("""
        SELECT c.talk_id, c.lead_id, c.total_messages, c.total_bot, c.total_human,
               c.attention_status, c.bot_names, c.human_agents,
               c.first_contact_time, c.last_message_time,
               l.name as lead_name, l.pipeline_name, l.stage_name,
               l.responsible_user_name, l.tags,
               ct.name as contact_name, ct.phone
        FROM kommo_chats c
        LEFT JOIN kommo_leads l ON c.lead_id = l.lead_id
        LEFT JOIN kommo_contacts ct ON l.contact_id = ct.contact_id
        WHERE c.chat_date = %s
        ORDER BY c.total_messages DESC
    """, (chat_date,))

    # Available dates
    dates = query("SELECT DISTINCT chat_date FROM kommo_chats ORDER BY chat_date DESC LIMIT 30")

    return render_template('chats.html',
                          chats=chats_data or [],
                          current_date=chat_date,
                          dates=dates or [])


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
               l.responsible_user_name, l.tags,
               ct.name as contact_name, ct.phone
        FROM kommo_chats c
        LEFT JOIN kommo_leads l ON c.lead_id = l.lead_id
        LEFT JOIN kommo_contacts ct ON l.contact_id = ct.contact_id
        WHERE c.talk_id = %s
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
    """App settings page."""
    if request.method == 'POST':
        for key in request.form:
            set_setting(key, request.form[key])
        flash('Settings saved', 'success')
        return redirect(url_for('settings'))

    all_settings = query("SELECT key, value, updated_at FROM kommo_app_settings ORDER BY key")
    return render_template('settings.html',
                          settings=all_settings or [])


@app.route('/api/stats')
def api_stats():
    """JSON API for dashboard stats."""
    metrics = query("SELECT * FROM kommo_daily_metrics ORDER BY metric_date DESC LIMIT 14")
    return jsonify(metrics or [])


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', False))
