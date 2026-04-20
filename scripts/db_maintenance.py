#!/usr/bin/env python3
"""
DB Maintenance: cleanup, consistency checks, auto-fix.
Run periodically to keep the database healthy.

Usage:
    python scripts/db_maintenance.py          # Full check + fix
    python scripts/db_maintenance.py --dry    # Check only, no changes
"""
import os
import sys
import psycopg2

DRY_RUN = '--dry' in sys.argv


def load_db_url():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    with open(env_path) as f:
        for line in f:
            if line.startswith('DATABASE_URL='):
                return line.split('=', 1)[1].strip()
    raise RuntimeError("DATABASE_URL not found in .env")


def main():
    conn = psycopg2.connect(load_db_url())
    cur = conn.cursor()

    print("=" * 60)
    print(f"  DB MAINTENANCE {'(DRY RUN)' if DRY_RUN else ''}")
    print("=" * 60)

    total_issues = 0
    total_fixed = 0

    # ── 1. Orphan chats (no messages + no metadata) ─────────────────
    print("\n[1/5] Orphan chats (no messages + no category/origin)")
    cur.execute("""
        SELECT COUNT(*) FROM kommo_chats
        WHERE total_messages = 0 AND (category IS NULL OR category = '')
    """)
    count = cur.fetchone()[0]
    print(f"  Found: {count}")
    total_issues += count
    if count and not DRY_RUN:
        cur.execute("""
            DELETE FROM kommo_messages WHERE talk_id IN (
                SELECT talk_id FROM kommo_chats
                WHERE total_messages = 0 AND (category IS NULL OR category = '')
            )
        """)
        cur.execute("""
            DELETE FROM kommo_chats
            WHERE total_messages = 0 AND (category IS NULL OR category = '')
        """)
        total_fixed += count
        print(f"  Deleted: {count}")

    # ── 2. Mismatched message counts ────────────────────────────────
    print("\n[2/5] Chat total_messages vs actual count")
    cur.execute("""
        SELECT COUNT(*) FROM kommo_chats c WHERE total_messages != (
            SELECT COUNT(*) FROM kommo_messages m
            WHERE m.talk_id=c.talk_id AND m.chat_date=c.chat_date
        )
    """)
    count = cur.fetchone()[0]
    print(f"  Mismatches: {count}")
    total_issues += count
    if count and not DRY_RUN:
        # Case A: chats WITH messages - sync counts
        cur.execute("""
            UPDATE kommo_chats c SET
                total_messages = subq.cnt,
                total_in = subq.in_cnt,
                total_out = subq.out_cnt,
                total_bot = subq.bot_cnt,
                total_human = subq.human_cnt,
                total_media = subq.media_cnt
            FROM (
                SELECT talk_id, chat_date, COUNT(*) as cnt,
                    SUM(CASE WHEN direction='IN' THEN 1 ELSE 0 END) as in_cnt,
                    SUM(CASE WHEN direction='OUT' THEN 1 ELSE 0 END) as out_cnt,
                    SUM(CASE WHEN is_bot THEN 1 ELSE 0 END) as bot_cnt,
                    SUM(CASE WHEN direction='OUT' AND NOT is_bot AND sender_type IN ('agent','system') THEN 1 ELSE 0 END) as human_cnt,
                    SUM(CASE WHEN msg_type != 'text' THEN 1 ELSE 0 END) as media_cnt
                FROM kommo_messages GROUP BY talk_id, chat_date
            ) subq
            WHERE c.talk_id=subq.talk_id AND c.chat_date=subq.chat_date
              AND c.total_messages != subq.cnt
        """)
        fixed_a = cur.rowcount

        # Case B: chats claiming messages but have 0 actual -> reset counts
        cur.execute("""
            UPDATE kommo_chats c SET
                total_messages = 0, total_in = 0, total_out = 0,
                total_bot = 0, total_human = 0, total_media = 0
            WHERE total_messages > 0 AND NOT EXISTS (
                SELECT 1 FROM kommo_messages m
                WHERE m.talk_id=c.talk_id AND m.chat_date=c.chat_date
            )
        """)
        fixed_b = cur.rowcount

        total_fixed += fixed_a + fixed_b
        print(f"  Fixed (sync): {fixed_a}")
        print(f"  Fixed (reset to 0): {fixed_b}")

    # ── 3. IN messages incorrectly marked as bot ────────────────────
    print("\n[3/5] IN messages marked as bot (should be 0)")
    cur.execute("SELECT COUNT(*) FROM kommo_messages WHERE direction='IN' AND is_bot=true")
    count = cur.fetchone()[0]
    print(f"  Found: {count}")
    total_issues += count
    if count and not DRY_RUN:
        cur.execute("""
            UPDATE kommo_messages SET is_bot=false, bot_name='', sender_type='contact'
            WHERE direction='IN' AND is_bot=true
        """)
        total_fixed += cur.rowcount
        print(f"  Fixed: {cur.rowcount}")

    # ── 4. WhatsApp Business marked as agent (should be system) ─────
    print("\n[4/5] WhatsApp Business marked as agent")
    cur.execute("""
        SELECT COUNT(*) FROM kommo_messages
        WHERE direction='OUT' AND author='WhatsApp Business' AND sender_type='agent'
    """)
    count = cur.fetchone()[0]
    print(f"  Found: {count}")
    total_issues += count
    if count and not DRY_RUN:
        cur.execute("""
            UPDATE kommo_messages SET sender_type='system'
            WHERE direction='OUT' AND author='WhatsApp Business' AND sender_type='agent'
        """)
        total_fixed += cur.rowcount
        print(f"  Fixed: {cur.rowcount}")

    # ── 5. Lead summary staleness ───────────────────────────────────
    print("\n[5/5] Lead summary (compared to chat counts)")
    cur.execute("SELECT COUNT(DISTINCT lead_id) FROM kommo_chats")
    chat_leads = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM kommo_lead_summary")
    summary_leads = cur.fetchone()[0]
    diff = chat_leads - summary_leads
    print(f"  Leads in chats: {chat_leads}, in summary: {summary_leads}, diff: {diff}")
    if diff != 0:
        print(f"  Run: python -c 'import sys; sys.path.insert(0,\".\"); from src.kommo.analytics import run_all_analytics; import psycopg2; run_all_analytics(psycopg2.connect(open(\".env\").read().split(\"DATABASE_URL=\")[1].split(chr(10))[0]))'")

    if not DRY_RUN:
        conn.commit()

    print(f"\n{'=' * 60}")
    print(f"  Total issues: {total_issues} | Fixed: {total_fixed}")
    if DRY_RUN:
        print("  (DRY RUN - no changes applied)")
    print(f"{'=' * 60}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
