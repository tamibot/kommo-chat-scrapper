"""
Database module for Kommo Chat Scrapper.
Handles all PostgreSQL operations: insert, upsert, compiled conversations, daily metrics.
"""
import json
import logging
import os
import psycopg2
import psycopg2.extras
from datetime import date, datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class KommoDB:
    """PostgreSQL interface for Kommo data."""

    def __init__(self, db_url: str = None):
        if not db_url:
            env = {}
            ep = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
            with open(ep) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        env[k.strip()] = v.strip()
            db_url = env.get('DATABASE_URL', '')
        self.conn = psycopg2.connect(db_url)
        self.conn.autocommit = False
        self.conn.autocommit = False

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ── Contacts ─────────────────────────────────────────────────────

    def _safe_rollback(self):
        try:
            self.conn.rollback()
        except:
            pass

    def upsert_contacts(self, contacts: Dict[int, dict]):
        cur = self.conn.cursor()
        for cid, c in contacts.items():
            cur.execute("""
                INSERT INTO kommo_contacts (contact_id, name, phone, email, created_at, updated_at, custom_fields)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (contact_id) DO UPDATE SET
                    name=EXCLUDED.name, phone=EXCLUDED.phone, email=EXCLUDED.email,
                    updated_at=EXCLUDED.updated_at, custom_fields=EXCLUDED.custom_fields,
                    fetched_at=NOW()
            """, (cid, c.get('name',''), c.get('phone',''), c.get('email',''),
                  c.get('created_at'), c.get('updated_at'),
                  json.dumps(c.get('custom_fields', {}))))
        self.conn.commit()
        logger.info(f"Upserted {len(contacts)} contacts")

    # ── Leads ────────────────────────────────────────────────────────

    def upsert_leads(self, leads: Dict[int, dict]):
        cur = self.conn.cursor()
        for lid, l in leads.items():
            cur.execute("""
                INSERT INTO kommo_leads (lead_id, name, contact_id, responsible_user_id,
                    responsible_user_name, pipeline_id, pipeline_name, status_id, stage_name,
                    price, tags, source, created_at, updated_at, closed_at, custom_fields)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (lead_id) DO UPDATE SET
                    name=EXCLUDED.name, responsible_user_name=EXCLUDED.responsible_user_name,
                    pipeline_name=EXCLUDED.pipeline_name, stage_name=EXCLUDED.stage_name,
                    price=EXCLUDED.price, tags=EXCLUDED.tags,
                    updated_at=EXCLUDED.updated_at, closed_at=EXCLUDED.closed_at,
                    custom_fields=EXCLUDED.custom_fields, fetched_at=NOW()
            """, (lid, l.get('name',''), l.get('contact_id'), l.get('responsible_user_id'),
                  l.get('responsible_user_name',''), l.get('pipeline_id'), l.get('pipeline_name',''),
                  l.get('status_id'), l.get('stage_name',''), l.get('price', 0),
                  l.get('tags', []), l.get('source', ''),
                  l.get('created_at'), l.get('updated_at'), l.get('closed_at'),
                  json.dumps(l.get('custom_fields', {}))))
        self.conn.commit()
        logger.info(f"Upserted {len(leads)} leads")

    # ── Chats + Messages ─────────────────────────────────────────────

    def upsert_chat(self, chat: dict, chat_date: date):
        """Insert or update a chat with its analytics."""
        cur = self.conn.cursor()
        a = chat.get('analytics', {})

        # Determine attention status
        last_msg = chat['messages'][-1] if chat.get('messages') else {}
        last_dir = last_msg.get('dir', '')
        last_sender = last_msg.get('sender_type', '')

        if not chat.get('messages'):
            attn = 'empty'
        elif a.get('has_human_response') and last_dir == 'OUT':
            attn = 'attended'
        elif a.get('has_human_response') and last_dir == 'IN':
            attn = 'pending_response'
        elif not a.get('has_human_response') and a.get('in_count', 0) > 0:
            attn = 'bot_only'
        elif a.get('in_count', 0) == 0:
            attn = 'outbound_only'
        else:
            attn = 'unknown'

        cur.execute("""
            INSERT INTO kommo_chats (talk_id, lead_id, contact_id, chat_date, conversation_ids,
                total_messages, total_in, total_out, total_bot, total_human, total_media,
                interactions, has_bot_response, has_human_response, is_bot_only,
                human_takeover_at_msg, bot_names, human_agents,
                attention_status, last_message_direction, last_message_sender_type,
                first_contact_time, first_bot_time, first_human_time, last_message_time,
                media_types)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (talk_id, chat_date) DO UPDATE SET
                total_messages=EXCLUDED.total_messages, total_in=EXCLUDED.total_in,
                total_out=EXCLUDED.total_out, total_bot=EXCLUDED.total_bot,
                total_human=EXCLUDED.total_human, total_media=EXCLUDED.total_media,
                interactions=EXCLUDED.interactions, has_human_response=EXCLUDED.has_human_response,
                attention_status=EXCLUDED.attention_status,
                last_message_direction=EXCLUDED.last_message_direction,
                human_agents=EXCLUDED.human_agents, bot_names=EXCLUDED.bot_names,
                scraped_at=NOW()
        """, (
            int(chat['talk_id']), int(chat['lead_id']),
            chat.get('contact_id'), chat_date,
            chat.get('conversation_ids', []),
            a.get('total_messages', 0), a.get('in_count', 0), a.get('out_count', 0),
            a.get('bot_count', 0), a.get('human_count', 0), a.get('media_count', 0),
            a.get('interactions', 0),
            a.get('bot_count', 0) > 0, a.get('has_human_response', False),
            not a.get('has_human_response', False) and a.get('bot_count', 0) > 0,
            a.get('human_takeover_at_msg'),
            a.get('bot_names', []), a.get('human_agents', []),
            attn, last_dir, last_sender,
            a.get('first_contact_time', ''), a.get('first_bot_time', ''),
            a.get('first_human_time', ''),
            last_msg.get('timestamp', ''),
            a.get('media_types', []),
        ))

        # Insert messages
        for idx, msg in enumerate(chat.get('messages', [])):
            cur.execute("""
                INSERT INTO kommo_messages (talk_id, lead_id, contact_id, chat_date, msg_index,
                    direction, sender_type, author, is_bot, bot_name, channel,
                    conversation_id, delivery_status, msg_type, msg_text, msg_timestamp)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (talk_id, chat_date, msg_index) DO UPDATE SET
                    msg_text=EXCLUDED.msg_text, sender_type=EXCLUDED.sender_type,
                    author=EXCLUDED.author, is_bot=EXCLUDED.is_bot,
                    msg_timestamp=EXCLUDED.msg_timestamp
            """, (
                int(chat['talk_id']), int(chat['lead_id']),
                chat.get('contact_id'), chat_date, idx,
                msg['dir'], msg.get('sender_type',''), msg.get('author',''),
                msg.get('is_bot', False), msg.get('bot_name',''),
                msg.get('channel',''), msg.get('conv_id',''),
                msg.get('delivery_status',''), msg['type'],
                msg.get('text',''), msg.get('timestamp',''),
            ))
        self.conn.commit()

    # ── Stage Changes ────────────────────────────────────────────────

    def upsert_stage_changes(self, changes: List[dict]):
        cur = self.conn.cursor()
        for c in changes:
            cur.execute("""
                INSERT INTO kommo_stage_changes (lead_id, event_id,
                    old_pipeline_id, old_pipeline_name, old_status_id, old_stage_name,
                    new_pipeline_id, new_pipeline_name, new_status_id, new_stage_name,
                    changed_by, changed_by_name, changed_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (event_id) DO NOTHING
            """, (
                c['lead_id'], c['event_id'],
                c.get('old_pipeline_id'), c.get('old_pipeline_name',''),
                c.get('old_status_id'), c.get('old_stage_name',''),
                c.get('new_pipeline_id'), c.get('new_pipeline_name',''),
                c.get('new_status_id'), c.get('new_stage_name',''),
                c.get('changed_by'), c.get('changed_by_name',''),
                c.get('changed_at'),
            ))
        self.conn.commit()
        logger.info(f"Upserted {len(changes)} stage changes")

    # ── Compiled Conversations ───────────────────────────────────────

    def compile_conversation(self, lead_id: int, chat_date: date = None):
        """Compile all messages for a lead into a single conversation for LLM analysis."""
        cur = self.conn.cursor()

        # Get lead + contact info
        cur.execute("""
            SELECT l.name, l.responsible_user_name, l.pipeline_name, l.stage_name, l.tags,
                   c.name, c.phone
            FROM kommo_leads l
            LEFT JOIN kommo_contacts c ON l.contact_id = c.contact_id
            WHERE l.lead_id = %s
        """, (lead_id,))
        row = cur.fetchone()
        if not row:
            return

        lead_name, responsible, pipeline, stage, tags, contact_name, phone = row

        # Get all messages for this lead, ordered
        date_filter = "AND m.chat_date = %s" if chat_date else ""
        params = [lead_id, chat_date] if chat_date else [lead_id]

        cur.execute(f"""
            SELECT m.direction, m.sender_type, m.author, m.is_bot, m.bot_name,
                   m.channel, m.msg_type, m.msg_text, m.msg_timestamp, m.chat_date
            FROM kommo_messages m
            WHERE m.lead_id = %s {date_filter}
            ORDER BY m.chat_date, m.msg_index
        """, params)

        messages = cur.fetchall()
        if not messages:
            return

        # Build structured conversation
        conversation = []
        plain_text_lines = []
        channels = set()
        bots = set()
        agents = set()
        dates = set()

        for dir_, stype, author, is_bot, bot_name, channel, mtype, text, ts, cdate in messages:
            dates.add(cdate)
            if channel:
                channels.add(channel)
            if is_bot and bot_name:
                bots.add(bot_name)
            if stype == 'agent' and author:
                agents.add(author)

            entry = {
                'direction': dir_,
                'sender_type': stype,
                'author': author or '',
                'is_bot': is_bot,
                'type': mtype,
                'text': text or f'[{mtype}]',
                'timestamp': ts or '',
            }
            conversation.append(entry)

            # Plain text for LLM
            sender_label = f"[BOT:{bot_name}]" if is_bot else f"[{stype.upper()}:{author}]" if author else f"[{dir_}]"
            media_note = f" [{mtype}]" if mtype != 'text' else ''
            plain_text_lines.append(f"{ts} {sender_label}: {text or f'({mtype})'}{media_note}")

        total_bot = sum(1 for m in messages if m[3])
        total_human = sum(1 for m in messages if m[1] == 'agent')
        total_contact = sum(1 for m in messages if m[1] == 'contact')

        has_human = total_human > 0
        if has_human and messages[-1][0] == 'OUT':
            attn = 'attended'
        elif has_human and messages[-1][0] == 'IN':
            attn = 'pending_response'
        elif not has_human:
            attn = 'bot_only'
        else:
            attn = 'unknown'

        sorted_dates = sorted(dates)

        cur.execute("""
            INSERT INTO kommo_conversations_compiled (
                lead_id, contact_id, contact_name, contact_phone,
                responsible_user, pipeline_name, stage_name,
                conversation_json, conversation_text,
                total_messages, total_bot_msgs, total_human_msgs, total_contact_msgs,
                date_range_start, date_range_end,
                channels, bots_used, agents_involved,
                attention_status, has_human_attention)
            VALUES (%s, (SELECT contact_id FROM kommo_leads WHERE lead_id=%s),
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lead_id) DO UPDATE SET
                conversation_json=EXCLUDED.conversation_json,
                conversation_text=EXCLUDED.conversation_text,
                total_messages=EXCLUDED.total_messages,
                total_bot_msgs=EXCLUDED.total_bot_msgs,
                total_human_msgs=EXCLUDED.total_human_msgs,
                total_contact_msgs=EXCLUDED.total_contact_msgs,
                attention_status=EXCLUDED.attention_status,
                has_human_attention=EXCLUDED.has_human_attention,
                compiled_at=NOW()
        """, (
            lead_id, lead_id,
            contact_name or '', phone or '', responsible or '',
            pipeline or '', stage or '',
            json.dumps(conversation, ensure_ascii=False),
            '\n'.join(plain_text_lines),
            len(messages), total_bot, total_human, total_contact,
            sorted_dates[0] if sorted_dates else None,
            sorted_dates[-1] if sorted_dates else None,
            list(channels), list(bots), list(agents),
            attn, has_human,
        ))
        self.conn.commit()

    # ── Daily Metrics ────────────────────────────────────────────────

    def compute_daily_metrics(self, metric_date: date):
        """Compute aggregated metrics for a given date."""
        cur = self.conn.cursor()

        cur.execute("""
            INSERT INTO kommo_daily_metrics (
                metric_date, total_chats, total_messages, total_in, total_out,
                total_bot, total_human, total_media,
                chats_with_human, chats_bot_only, chats_unanswered,
                avg_interactions, unique_contacts, unique_agents)
            SELECT
                %s,
                COUNT(*),
                SUM(total_messages), SUM(total_in), SUM(total_out),
                SUM(total_bot), SUM(total_human), SUM(total_media),
                SUM(CASE WHEN has_human_response THEN 1 ELSE 0 END),
                SUM(CASE WHEN is_bot_only THEN 1 ELSE 0 END),
                SUM(CASE WHEN attention_status='pending_response' THEN 1 ELSE 0 END),
                AVG(interactions),
                COUNT(DISTINCT contact_id),
                (SELECT COUNT(DISTINCT author) FROM kommo_messages
                 WHERE chat_date=%s AND sender_type='agent' AND author != '')
            FROM kommo_chats
            WHERE chat_date = %s
            ON CONFLICT (metric_date) DO UPDATE SET
                total_chats=EXCLUDED.total_chats, total_messages=EXCLUDED.total_messages,
                total_in=EXCLUDED.total_in, total_out=EXCLUDED.total_out,
                total_bot=EXCLUDED.total_bot, total_human=EXCLUDED.total_human,
                chats_with_human=EXCLUDED.chats_with_human,
                chats_bot_only=EXCLUDED.chats_bot_only,
                avg_interactions=EXCLUDED.avg_interactions,
                computed_at=NOW()
        """, (metric_date, metric_date, metric_date))
        self.conn.commit()
        logger.info(f"Computed daily metrics for {metric_date}")

    # ── Events ────────────────────────────────────────────────────────

    def upsert_events(self, events: List[dict]):
        cur = self.conn.cursor()
        for ev in events:
            d = ev.get('created_at')
            cur.execute("""
                INSERT INTO kommo_events (event_id, event_type, entity_type, entity_id,
                    value_before, value_after, created_by, created_at, event_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (event_id) DO NOTHING
            """, (
                ev['event_id'], ev['event_type'], ev.get('entity_type',''),
                ev.get('entity_id'),
                json.dumps(ev.get('value_before', [])),
                json.dumps(ev.get('value_after', [])),
                ev.get('created_by', 0), d,
                d.date() if d else None,
            ))
        self.conn.commit()
        logger.info(f"Upserted {len(events)} events")

    # ── Scrape Errors ────────────────────────────────────────────────

    def log_error(self, talk_id: int, lead_id: int, chat_date: date,
                  error_type: str, error_msg: str):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO kommo_scrape_errors (talk_id, lead_id, chat_date, error_type, error_message)
            VALUES (%s,%s,%s,%s,%s)
        """, (talk_id, lead_id, chat_date, error_type, error_msg[:500]))
        self.conn.commit()

    # ── No-Reply Tracking ────────────────────────────────────────────

    def detect_no_reply_chats(self, chat_date: date):
        """Detect chats where the last N messages are all OUT with no IN response."""
        try:
            self.conn.rollback()
        except:
            pass
        cur = self.conn.cursor()
        # Find chats where last message direction is OUT and there are multiple consecutive OUTs
        cur.execute("""
            WITH last_msgs AS (
                SELECT talk_id, lead_id, direction, msg_timestamp, msg_text, sender_type,
                       ROW_NUMBER() OVER (PARTITION BY talk_id ORDER BY msg_index DESC) as rn
                FROM kommo_messages
                WHERE chat_date = %s
            ),
            consecutive_out AS (
                SELECT talk_id, lead_id, COUNT(*) as out_count,
                       MAX(msg_timestamp) as last_out_time,
                       MAX(msg_text) as last_out_text
                FROM last_msgs
                WHERE direction = 'OUT' AND rn <= 5  -- last 5 messages
                GROUP BY talk_id, lead_id
                HAVING COUNT(*) >= 2  -- at least 2 consecutive OUTs at the end
            )
            SELECT co.talk_id, co.lead_id, co.out_count, co.last_out_time, co.last_out_text,
                   l.name, l.pipeline_name, l.stage_name, l.responsible_user_name,
                   c.name, c.phone
            FROM consecutive_out co
            JOIN kommo_chats ch ON co.talk_id = ch.talk_id AND ch.chat_date = %s
            LEFT JOIN kommo_leads l ON co.lead_id = l.lead_id
            LEFT JOIN kommo_contacts c ON l.contact_id = c.contact_id
            WHERE ch.last_message_direction = 'OUT'
        """, (chat_date, chat_date))

        results = cur.fetchall()
        for r in results:
            cur.execute("""
                INSERT INTO kommo_no_reply_tracking (
                    lead_id, contact_id, contact_name, contact_phone,
                    consecutive_out, last_out_date, last_out_text,
                    status, pipeline_name, stage_name, responsible_user)
                VALUES (%s, (SELECT contact_id FROM kommo_leads WHERE lead_id=%s),
                        %s, %s, %s, %s, %s, 'no_reply', %s, %s, %s)
                ON CONFLICT (lead_id) DO UPDATE SET
                    consecutive_out=EXCLUDED.consecutive_out,
                    last_out_date=EXCLUDED.last_out_date,
                    last_out_text=EXCLUDED.last_out_text,
                    detected_at=NOW()
            """, (r[1], r[1], r[9] or '', r[10] or '', r[2], r[3], (r[4] or '')[:200],
                  r[6] or '', r[7] or '', r[8] or ''))
        self.conn.commit()
        logger.info(f"Detected {len(results)} no-reply chats")
        return len(results)

    # ── Queries ──────────────────────────────────────────────────────

    def get_stats(self, chat_date: date) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM kommo_daily_metrics WHERE metric_date=%s", (chat_date,))
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        return {}
