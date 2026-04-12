#!/usr/bin/env python3
"""
Full project health check - verifies EVERY component is working.
Run this after setup, after scraping, or anytime you want to verify status.

Usage:
    python scripts/health_check.py
"""
import json
import os
import sys
import time

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
WARN = "\033[93m[WARN]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

def check(name, ok, detail=""):
    icon = PASS if ok else FAIL
    print(f"  {icon} {name}: {detail}")
    return ok


def main():
    print("=" * 65)
    print("  KOMMO CHAT SCRAPPER - FULL HEALTH CHECK")
    print("=" * 65)

    errors = 0

    # ── 1. Environment ──────────────────────────────────────────────
    print("\n[1/8] Environment & Config")
    env = {}
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
        check(".env file", True, "Found")
    else:
        check(".env file", False, "Missing! Run: cp .env.example .env")
        errors += 1
        print("\n  Cannot continue without .env. Exiting.")
        return

    required = ['KOMMO_BASE_URL', 'KOMMO_ACCESS_TOKEN', 'KOMMO_LOGIN_EMAIL',
                'KOMMO_LOGIN_PASSWORD', 'DATABASE_URL']
    for var in required:
        if env.get(var):
            check(var, True, "Set")
        else:
            check(var, False, "MISSING")
            errors += 1

    # ── 2. Dependencies ─────────────────────────────────────────────
    print("\n[2/8] Python Dependencies")
    for mod, pip in [('selenium', 'selenium'), ('psycopg2', 'psycopg2-binary'),
                     ('flask', 'flask')]:
        try:
            __import__(mod)
            check(mod, True, "Installed")
        except ImportError:
            check(mod, False, f"Missing! pip install {pip}")
            errors += 1

    # ── 3. Chrome ────────────────────────────────────────────────────
    print("\n[3/8] Chrome Headless")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        d = webdriver.Chrome(options=options)
        ver = d.capabilities.get('browserVersion', '?')
        d.quit()
        check("Chrome headless", True, f"v{ver}")
    except Exception as e:
        check("Chrome headless", False, str(e)[:60])
        errors += 1

    # ── 4. Kommo API ─────────────────────────────────────────────────
    print("\n[4/8] Kommo API")
    import ssl, urllib.request
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(
            f"{env['KOMMO_BASE_URL']}/api/v4/account?with=amojo_id",
            headers={'Authorization': f"Bearer {env['KOMMO_ACCESS_TOKEN']}"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read())
            check("API connection", True, f"{data['name']} (ID: {data['id']})")
    except Exception as e:
        check("API connection", False, str(e)[:60])
        errors += 1

    # ── 5. Database ──────────────────────────────────────────────────
    print("\n[5/8] PostgreSQL Database")
    import psycopg2
    try:
        conn = psycopg2.connect(env['DATABASE_URL'])
        cur = conn.cursor()
        check("Connection", True, "Connected")

        # Check tables
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
        tables = cur.fetchone()[0]
        check(f"Tables", tables >= 10, f"{tables} tables")

        # Check data
        data_checks = {
            'kommo_chats': 'Chats',
            'kommo_messages': 'Messages',
            'kommo_leads': 'Leads',
            'kommo_contacts': 'Contacts',
            'kommo_daily_metrics': 'Daily metrics',
        }
        for table, label in data_checks.items():
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                check(label, count > 0, f"{count} rows")
            except:
                check(label, False, "Table missing")
                conn.rollback()

        # Check dates
        cur.execute("SELECT MIN(chat_date), MAX(chat_date), COUNT(DISTINCT chat_date) FROM kommo_chats")
        r = cur.fetchone()
        if r[0]:
            check("Date range", True, f"{r[0]} to {r[1]} ({r[2]} days)")
        else:
            check("Date range", False, "No data yet")

        cur.close()
        conn.close()
    except Exception as e:
        check("Connection", False, str(e)[:60])
        errors += 1

    # ── 6. Mappings ──────────────────────────────────────────────────
    print("\n[6/8] Account Mappings")
    mappings_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'kommo_mappings.json')
    if os.path.exists(mappings_path):
        with open(mappings_path) as f:
            m = json.load(f)
        check("Mappings file", True, "Found")
        check("Pipelines", len(m.get('pipelines', {})) > 0, f"{len(m.get('pipelines', {}))} pipelines")
        check("Users", len(m.get('users', {})) > 0, f"{len(m.get('users', {}))} users")
    else:
        check("Mappings file", False, "Missing! Run: python scripts/setup_account.py")
        errors += 1

    # ── 7. Web Dashboard ─────────────────────────────────────────────
    print("\n[7/8] Web Dashboard (local test)")
    try:
        os.environ['DATABASE_URL'] = env['DATABASE_URL']
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'web'))
        from app import app
        client = app.test_client()

        routes = ['/', '/chats', '/no-reply', '/pending', '/stages', '/settings', '/api/health']
        for route in routes:
            r = client.get(route)
            check(f"GET {route}", r.status_code == 200, f"HTTP {r.status_code}")
            if r.status_code != 200:
                errors += 1
    except Exception as e:
        check("Flask app", False, str(e)[:60])
        errors += 1

    # ── 8. Scraper Login ─────────────────────────────────────────────
    print("\n[8/8] Scraper Login Test")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        options = Options()
        options.add_argument("--user-data-dir=/tmp/kommo_health_check")
        options.add_argument("--profile-directory=HealthCheck")
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        d = webdriver.Chrome(options=options)
        d.get(env['KOMMO_BASE_URL'])
        time.sleep(4)
        if 'Authorization' not in d.title and 'Autorización' not in d.title:
            check("Login", True, "Session active")
        else:
            d.find_element(By.CSS_SELECTOR, 'input[type="text"]').send_keys(env['KOMMO_LOGIN_EMAIL'])
            d.find_element(By.CSS_SELECTOR, 'input[type="password"]').send_keys(env['KOMMO_LOGIN_PASSWORD'])
            d.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(6)
            if 'Authorization' not in d.title and 'Autorización' not in d.title:
                check("Login", True, "Login successful")
            else:
                code_inputs = d.find_elements(By.CSS_SELECTOR, 'input[type="tel"]')
                if code_inputs:
                    check("Login", False, "2FA REQUIRED! User must NOT have 2FA enabled")
                else:
                    check("Login", False, "Login failed - check credentials or reCAPTCHA")
                errors += 1
        d.quit()
    except Exception as e:
        check("Login", False, str(e)[:60])
        errors += 1

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    if errors == 0:
        print(f"  {PASS} ALL CHECKS PASSED - System is fully operational")
        print(f"  Next: python scripts/scrape_v3.py --max-chats 5")
    else:
        print(f"  {FAIL} {errors} check(s) FAILED - Fix the issues above")
    print(f"{'=' * 65}")


if __name__ == '__main__':
    main()
