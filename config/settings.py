import os
from dotenv import load_dotenv

load_dotenv()

# Kommo
KOMMO_BASE_URL = os.getenv("KOMMO_BASE_URL", "")
KOMMO_ACCESS_TOKEN = os.getenv("KOMMO_ACCESS_TOKEN", "")
KOMMO_CLIENT_ID = os.getenv("KOMMO_CLIENT_ID", "")
KOMMO_CLIENT_SECRET = os.getenv("KOMMO_CLIENT_SECRET", "")
KOMMO_REDIRECT_URI = os.getenv("KOMMO_REDIRECT_URI", "")

# Google
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")

# App
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
SCRAPPER_INTERVAL_SECONDS = int(os.getenv("SCRAPPER_INTERVAL_SECONDS", "300"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
