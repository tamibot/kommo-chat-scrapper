"""
Analytics engine for Kommo Chat Scrapper.
Computes derived metrics, detects attention issues, and populates summary tables.
"""
import logging
import re
from datetime import datetime, date, timedelta, timezone
from typing import Optional

import psycopg2

logger = logging.getLogger(__name__)

PERU = timezone(timedelta(hours=-5))


def parse_kommo_timestamp(ts: str, reference_date: date = None) -> Optional[datetime]:
    """Parse Kommo timestamp formats into datetime.
    Formats: 'DD.MM.YYYY HH:MM', 'Yesterday HH:MM', 'Today HH:MM'"""
    if not ts:
        return None

    now = datetime.now(PERU)
    if reference_date is None:
        reference_date = now.date()

    # DD.MM.YYYY HH:MM
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})', ts)
    if m:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)),
                       int(m.group(4)), int(m.group(5)), tzinfo=PERU)

    # DD.MM.YYYY (no time)
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})$', ts)
    if m:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=PERU)

    # Yesterday HH:MM
    m = re.match(r'Yesterday\s+(\d{2}):(\d{2})', ts)
    if m:
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                                second=0, microsecond=0)

    # Today HH:MM
    m = re.match(r'Today\s+(\d{2}):(\d{2})', ts)
    if m:
        return now.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                          second=0, microsecond=0)

    return None


def compute_chat_deep_analytics(conn, chat_date: date = None):
    """Compute deep analytics for chats: response times, consecutive counts, etc."""
    cur = conn.cursor()

    date_filter = "WHERE c.chat_date = %s" if chat_date else ""
    params = (chat_date,) if chat_date else ()

    # 1. Parse timestamps and update parsed_at
    logger.info("Parsing message timestamps...")
    cur.execute(f"""
        SELECT m.id, m.msg_timestamp, m.chat_date, m.msg_type, m.msg_text
        FROM kommo_messages m
        {f"WHERE m.chat_date = %s AND" if chat_date else "WHERE"} m.parsed_at IS NULL
        LIMIT 5000
    """, params)

    updated = 0
    for row in cur.fetchall():
        msg_id, ts, cd, mtype, mtext = row
        parsed = parse_kommo_timestamp(ts, cd)
        has_media = mtype != 'text'
        if parsed:
            cur.execute("UPDATE kommo_messages SET parsed_at=%s, has_media=%s WHERE id=%s",
                       (parsed, has_media, msg_id))
            updated += 1
    conn.commit()
    logger.info(f"  Parsed {updated} timestamps")

    # 2. Update chat-level fields from lead data
    logger.info("Enriching chats with lead data...")
    cur.execute(f"""
        UPDATE kommo_chats c SET
            responsible_user = COALESCE(l.responsible_user_name, ''),
            pipeline_name = COALESCE(l.pipeline_name, ''),
            stage_name = COALESCE(l.stage_name, ''),
            tags = l.tags
        FROM kommo_leads l
        WHERE c.lead_id = l.lead_id
        {f"AND c.chat_date = %s" if chat_date else ""}
    """, params)
    conn.commit()

    # 3. Compute consecutive messages at end of chat
    logger.info("Computing consecutive message counts...")
    cur.execute(f"""
        SELECT c.id, c.talk_id, c.chat_date
        FROM kommo_chats c {date_filter}
    """, params)

    for chat_id, talk_id, cd in cur.fetchall():
        # Get last 10 messages to check consecutive pattern
        cur.execute("""
            SELECT direction, msg_timestamp FROM kommo_messages
            WHERE talk_id=%s AND chat_date=%s
            ORDER BY msg_index DESC LIMIT 10
        """, (talk_id, cd))
        msgs = cur.fetchall()

        if not msgs:
            continue

        # Count consecutive OUT at end
        consec_out = 0
        last_out_ts = ''
        for d, ts in msgs:
            if d == 'OUT':
                consec_out += 1
                if not last_out_ts:
                    last_out_ts = ts or ''
            else:
                break

        # Count consecutive IN at end
        consec_in = 0
        last_in_ts = ''
        for d, ts in msgs:
            if d == 'IN':
                consec_in += 1
                if not last_in_ts:
                    last_in_ts = ts or ''
            else:
                break

        cur.execute("""
            UPDATE kommo_chats SET
                consecutive_out_end=%s, consecutive_in_end=%s,
                last_out_timestamp=%s, last_in_timestamp=%s
            WHERE id=%s
        """, (consec_out, consec_in, last_out_ts, last_in_ts, chat_id))

    conn.commit()
    logger.info("  Done")


def detect_pending_attention(conn, chat_date: date = None):
    """Detect chats where WE need to respond (client wrote, no human reply)."""
    cur = conn.cursor()

    date_filter = "AND c.chat_date = %s" if chat_date else ""
    params = (chat_date,) if chat_date else ()

    # Use DISTINCT ON to avoid duplicate lead_id+talk_id pairs
    cur.execute(f"""
        INSERT INTO kommo_pending_attention (
            lead_id, contact_id, talk_id, contact_name, contact_phone,
            responsible_user, responsible_user_id, pipeline_name, stage_name, tags, origin,
            last_client_msg_time, last_client_msg_text,
            last_our_msg_time, last_our_msg_type,
            client_msgs_waiting, has_bot_responded, has_human_responded,
            urgency, attention_needed
        )
        SELECT DISTINCT ON (c.lead_id, c.talk_id)
            c.lead_id, c.contact_id, c.talk_id,
            COALESCE(ct.name, ''), COALESCE(ct.phone, ''),
            COALESCE(l.responsible_user_name, ''), l.responsible_user_id,
            COALESCE(l.pipeline_name, ''), COALESCE(l.stage_name, ''),
            l.tags, COALESCE(c.origin, ''),
            c.last_in_timestamp, '',
            c.last_out_timestamp, '',
            c.consecutive_in_end,
            c.has_bot_response, c.has_human_response,
            CASE
                WHEN c.consecutive_in_end >= 3 THEN 'high'
                WHEN c.consecutive_in_end >= 2 THEN 'medium'
                ELSE 'normal'
            END,
            CASE
                WHEN NOT c.has_human_response THEN 'first_human_contact'
                ELSE 'follow_up'
            END
        FROM kommo_chats c
        LEFT JOIN kommo_leads l ON c.lead_id = l.lead_id
        LEFT JOIN kommo_contacts ct ON l.contact_id = ct.contact_id
        WHERE c.last_message_direction = 'IN'
          AND c.consecutive_in_end >= 1
          {date_filter}
        ORDER BY c.lead_id, c.talk_id, c.chat_date DESC
        ON CONFLICT (lead_id, talk_id) DO UPDATE SET
            client_msgs_waiting = EXCLUDED.client_msgs_waiting,
            last_client_msg_time = EXCLUDED.last_client_msg_time,
            urgency = EXCLUDED.urgency,
            detected_at = NOW()
    """, params)

    count = cur.rowcount
    conn.commit()
    logger.info(f"Pending attention: {count} chats needing our response")
    return count


def detect_no_reply_improved(conn, chat_date: date = None):
    """Detect chats where CLIENT hasn't replied (we sent, they're silent)."""
    cur = conn.cursor()

    date_filter = "AND c.chat_date = %s" if chat_date else ""
    params = (chat_date,) if chat_date else ()

    cur.execute(f"""
        INSERT INTO kommo_no_reply_tracking (
            lead_id, contact_id, contact_name, contact_phone,
            consecutive_out, last_out_date, last_out_text,
            status, pipeline_name, stage_name, responsible_user,
            origin, tags, lead_name, last_in_timestamp
        )
        SELECT DISTINCT ON (c.lead_id)
            c.lead_id, c.contact_id,
            COALESCE(ct.name, ''), COALESCE(ct.phone, ''),
            c.consecutive_out_end, c.last_out_timestamp, '',
            'no_reply', COALESCE(l.pipeline_name, ''), COALESCE(l.stage_name, ''),
            COALESCE(l.responsible_user_name, ''),
            COALESCE(c.origin, ''), l.tags, COALESCE(l.name, ''),
            c.last_in_timestamp
        FROM kommo_chats c
        LEFT JOIN kommo_leads l ON c.lead_id = l.lead_id
        LEFT JOIN kommo_contacts ct ON l.contact_id = ct.contact_id
        WHERE c.last_message_direction = 'OUT'
          AND c.consecutive_out_end >= 2
          {date_filter}
        ORDER BY c.lead_id, c.chat_date DESC
        ON CONFLICT (lead_id) DO UPDATE SET
            consecutive_out = EXCLUDED.consecutive_out,
            last_out_date = EXCLUDED.last_out_date,
            origin = EXCLUDED.origin,
            tags = EXCLUDED.tags,
            detected_at = NOW()
    """, params)

    count = cur.rowcount
    conn.commit()
    logger.info(f"No-reply: {count} chats where client hasn't responded")
    return count


def compute_lead_summary(conn):
    """Compute aggregated per-lead metrics across all dates."""
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO kommo_lead_summary (
            lead_id, contact_id, contact_name, contact_phone,
            responsible_user, pipeline_name, stage_name, tags, origin,
            first_chat_date, last_chat_date,
            total_chats, total_messages, total_in, total_out,
            total_bot, total_human, total_media,
            total_interactions, avg_messages_per_chat,
            has_ever_had_human, is_only_bot,
            current_attention_status, consecutive_out_without_reply,
            last_message_direction, last_message_time,
            is_hot, hot_reason
        )
        SELECT
            c.lead_id,
            MAX(c.contact_id),
            MAX(ct.name), MAX(ct.phone),
            MAX(l.responsible_user_name), MAX(l.pipeline_name), MAX(l.stage_name),
            MAX(l.tags), MAX(c.origin),
            MIN(c.chat_date), MAX(c.chat_date),
            COUNT(DISTINCT c.id),
            SUM(c.total_messages), SUM(c.total_in), SUM(c.total_out),
            SUM(c.total_bot), SUM(c.total_human), SUM(c.total_media),
            SUM(c.interactions),
            AVG(c.total_messages),
            BOOL_OR(c.has_human_response),
            BOOL_AND(c.is_bot_only),
            -- Current status from most recent chat
            (SELECT attention_status FROM kommo_chats
             WHERE lead_id=c.lead_id ORDER BY chat_date DESC, id DESC LIMIT 1),
            -- Consecutive OUTs from most recent chat
            (SELECT consecutive_out_end FROM kommo_chats
             WHERE lead_id=c.lead_id ORDER BY chat_date DESC, id DESC LIMIT 1),
            (SELECT last_message_direction FROM kommo_chats
             WHERE lead_id=c.lead_id ORDER BY chat_date DESC, id DESC LIMIT 1),
            (SELECT last_message_time FROM kommo_chats
             WHERE lead_id=c.lead_id ORDER BY chat_date DESC, id DESC LIMIT 1),
            -- Hot lead: recent activity + in active pipeline stage
            CASE WHEN MAX(l.stage_name) IN (
                'HORARIO INDICADO', 'VISITA MODO', 'INTERACTUANDO',
                'INTERESADO', 'DEFINIENDO PROPIEDAD', 'LLAMADA AGENDADA',
                'INV: DATOS (REUNION)', 'LEAD NUEVO'
            ) THEN TRUE ELSE FALSE END,
            CASE WHEN MAX(l.stage_name) IN (
                'HORARIO INDICADO', 'VISITA MODO', 'INTERACTUANDO',
                'INTERESADO', 'DEFINIENDO PROPIEDAD', 'LLAMADA AGENDADA'
            ) THEN 'hot_stage'
            WHEN MAX(l.stage_name) IN ('INV: DATOS (REUNION)', 'LEAD NUEVO')
            THEN 'new_lead'
            ELSE '' END
        FROM kommo_chats c
        LEFT JOIN kommo_leads l ON c.lead_id = l.lead_id
        LEFT JOIN kommo_contacts ct ON l.contact_id = ct.contact_id
        GROUP BY c.lead_id
        ON CONFLICT (lead_id) DO UPDATE SET
            contact_name = EXCLUDED.contact_name,
            contact_phone = EXCLUDED.contact_phone,
            responsible_user = EXCLUDED.responsible_user,
            pipeline_name = EXCLUDED.pipeline_name,
            stage_name = EXCLUDED.stage_name,
            tags = EXCLUDED.tags,
            last_chat_date = EXCLUDED.last_chat_date,
            total_chats = EXCLUDED.total_chats,
            total_messages = EXCLUDED.total_messages,
            total_in = EXCLUDED.total_in,
            total_out = EXCLUDED.total_out,
            total_bot = EXCLUDED.total_bot,
            total_human = EXCLUDED.total_human,
            current_attention_status = EXCLUDED.current_attention_status,
            consecutive_out_without_reply = EXCLUDED.consecutive_out_without_reply,
            last_message_direction = EXCLUDED.last_message_direction,
            last_message_time = EXCLUDED.last_message_time,
            is_hot = EXCLUDED.is_hot,
            hot_reason = EXCLUDED.hot_reason,
            computed_at = NOW()
    """)

    count = cur.rowcount
    conn.commit()
    logger.info(f"Lead summary: {count} leads computed")

    # Update leads table too
    cur.execute("""
        UPDATE kommo_leads l SET
            total_chats = s.total_chats,
            total_messages = s.total_messages,
            is_hot = s.is_hot,
            last_activity_date = s.last_chat_date
        FROM kommo_lead_summary s
        WHERE l.lead_id = s.lead_id
    """)
    conn.commit()

    return count


def run_all_analytics(conn, chat_date: date = None):
    """Run the full analytics pipeline."""
    logger.info(f"=== Running analytics pipeline {'for ' + str(chat_date) if chat_date else '(all dates)'} ===")

    compute_chat_deep_analytics(conn, chat_date)
    detect_pending_attention(conn, chat_date)
    detect_no_reply_improved(conn, chat_date)
    compute_lead_summary(conn)

    logger.info("=== Analytics pipeline complete ===")
