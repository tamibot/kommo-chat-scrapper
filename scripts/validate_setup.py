#!/usr/bin/env python3
"""
Validates all credentials, connections, and dependencies.
Run this after configuring .env to verify everything works.

Usage:
    python scripts/validate_setup.py
"""
import os, sys, json, time

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

def check(name, status, detail=""):
    icon = {"PASS": "✓", "FAIL": "✗", "WARN": "!"}[status]
    color = {"PASS": "\033[92m", "FAIL": "\033[91m", "WARN": "\033[93m"}[status]
    reset = "\033[0m"
    print(f"  {color}[{icon}]{reset} {name}: {detail}")
    return status != FAIL


def load_env():
    env = {}
    ep = os.path.join(os.path.dirname(__file__), '..', '.env')
    if not os.path.exists(ep):
        return None
    with open(ep) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env


def main():
    print("=" * 55)
    print("  KOMMO SCRAPER - SETUP VALIDATION")
    print("=" * 55)
    errors = 0

    # 1. .env file
    print("\n[1/6] Environment file (.env)")
    env = load_env()
    if not env:
        check(".env file", FAIL, "Not found. Run: cp .env.example .env")
        errors += 1
        return
    check(".env file", PASS, "Found")

    # Check required vars
    required = ['KOMMO_BASE_URL', 'KOMMO_ACCESS_TOKEN', 'KOMMO_LOGIN_EMAIL', 'KOMMO_LOGIN_PASSWORD', 'DATABASE_URL']
    for var in required:
        if env.get(var):
            check(var, PASS, f"{env[var][:30]}..." if len(env.get(var, '')) > 30 else env[var])
        else:
            check(var, FAIL, "Missing! Add to .env")
            errors += 1

    # 2. Python dependencies
    print("\n[2/6] Python dependencies")
    deps = {'selenium': 'selenium', 'psycopg2': 'psycopg2-binary', 'flask': 'flask'}
    for module, pip_name in deps.items():
        try:
            __import__(module)
            check(module, PASS, "Installed")
        except ImportError:
            check(module, FAIL, f"Not installed. Run: pip install {pip_name}")
            errors += 1

    # 3. Chrome / ChromeDriver
    print("\n[3/6] Chrome browser")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)
        version = driver.capabilities.get('browserVersion', 'unknown')
        driver.quit()
        check("Chrome headless", PASS, f"Version {version}")
    except Exception as e:
        check("Chrome headless", FAIL, f"Error: {e}")
        errors += 1

    # 4. Kommo API
    print("\n[4/6] Kommo API connection")
    if env.get('KOMMO_BASE_URL') and env.get('KOMMO_ACCESS_TOKEN'):
        import ssl, urllib.request
        ctx = ssl.create_default_context()
        try:
            req = urllib.request.Request(
                f"{env['KOMMO_BASE_URL']}/api/v4/account?with=amojo_id",
                headers={'Authorization': f"Bearer {env['KOMMO_ACCESS_TOKEN']}"}
            )
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = json.loads(resp.read())
                check("API connection", PASS, f"Account: {data['name']} (ID: {data['id']})")
                check("Amojo ID", PASS, data.get('amojo_id', 'N/A'))
        except Exception as e:
            check("API connection", FAIL, str(e)[:80])
            errors += 1
    else:
        check("API connection", WARN, "Skipped - missing credentials")

    # 5. Kommo Login (Selenium)
    print("\n[5/6] Kommo web login")
    if env.get('KOMMO_LOGIN_EMAIL') and env.get('KOMMO_LOGIN_PASSWORD'):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By

            options = Options()
            options.add_argument("--user-data-dir=/tmp/kommo_scraper_session")
            options.add_argument("--profile-directory=Scraper")
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            driver = webdriver.Chrome(options=options)

            driver.get(env['KOMMO_BASE_URL'])
            time.sleep(4)

            if 'Authorization' not in driver.title and 'Autorización' not in driver.title:
                check("Web login", PASS, "Session active (already logged in)")
            else:
                driver.find_element(By.CSS_SELECTOR, 'input[type="text"]').send_keys(env['KOMMO_LOGIN_EMAIL'])
                driver.find_element(By.CSS_SELECTOR, 'input[type="password"]').send_keys(env['KOMMO_LOGIN_PASSWORD'])
                driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
                time.sleep(6)

                if 'Authorization' not in driver.title and 'Autorización' not in driver.title:
                    check("Web login", PASS, f"Logged in as {env['KOMMO_LOGIN_EMAIL']}")
                else:
                    # Check if 2FA required
                    code_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="tel"]')
                    if code_inputs:
                        check("Web login", FAIL, "2FA required! Use a user WITHOUT 2-factor authentication")
                        errors += 1
                    else:
                        check("Web login", FAIL, "Login failed - check credentials")
                        errors += 1
            driver.quit()
        except Exception as e:
            check("Web login", FAIL, str(e)[:80])
            errors += 1
    else:
        check("Web login", WARN, "Skipped - missing login credentials")

    # 6. PostgreSQL
    print("\n[6/6] PostgreSQL connection")
    if env.get('DATABASE_URL'):
        try:
            import psycopg2
            conn = psycopg2.connect(env['DATABASE_URL'])
            cur = conn.cursor()
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            check("PostgreSQL", PASS, version[:60])

            # Check if tables exist
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
            table_count = cur.fetchone()[0]
            if table_count >= 7:
                check("Tables", PASS, f"{table_count} tables found")
            elif table_count > 0:
                check("Tables", WARN, f"Only {table_count} tables. Run scraper to create all.")
            else:
                check("Tables", WARN, "No tables yet. First scrape will create them.")

            cur.close()
            conn.close()
        except Exception as e:
            check("PostgreSQL", FAIL, str(e)[:80])
            errors += 1
    else:
        check("PostgreSQL", WARN, "Skipped - missing DATABASE_URL")

    # Summary
    print(f"\n{'=' * 55}")
    if errors == 0:
        print("  All checks passed! Ready to scrape.")
        print("  Run: python scripts/scrape_v3.py --max-chats 5")
    else:
        print(f"  {errors} check(s) failed. Fix the issues above.")
    print(f"{'=' * 55}")


if __name__ == '__main__':
    main()
