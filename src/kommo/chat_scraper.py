"""
Kommo Chat Scraper - Extracts chat conversations via browser automation.

Uses Selenium with a dedicated Chrome profile (logged in once, session persists).
Injects JavaScript to extract messages from the Kommo DOM.

DOM Structure (verified 2026-04-01):
- Chat list sidebar: a[href*="/chats/"][href*="/leads/detail/"]
- Message wrappers: .feed-note-wrapper-amojo
- Outgoing messages: .feed-note__talk-outgoing
- Message text: .feed-note__message_paragraph
- Timestamps: .feed-note__talk-outgoing-number
- Load more button: a text matching "Más X de Y"
- Conversation ID: .feed-note__talk-outgoing-title (contains "Conversación № AXXXXXX")
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, StaleElementReferenceException,
        ElementClickInterceptedException, WebDriverException
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium not installed. pip install selenium")


# JavaScript to extract messages from the current chat panel
JS_EXTRACT_MESSAGES = """
(function() {
    var notes = document.querySelectorAll('.feed-note-wrapper-amojo');
    var msgs = [];
    for (var i = 0; i < notes.length; i++) {
        var n = notes[i];
        var isOut = n.querySelector('.feed-note__talk-outgoing') !== null;
        var dateEl = n.querySelector('.feed-note__talk-outgoing-number');
        var dateT = dateEl ? dateEl.innerText.trim() : '';
        var msgEl = n.querySelector('.feed-note__message_paragraph');
        var msg = msgEl ? msgEl.innerText.substring(0, 1500) : '';
        if (msg) {
            msgs.push({dir: isOut ? 'OUT' : 'IN', date: dateT, text: msg});
        }
    }
    return msgs;
})()
"""

# JavaScript to click all "Más X de Y" expand buttons
JS_CLICK_MORE = """
(function() {
    var links = document.querySelectorAll('a');
    var clicked = 0;
    for (var i = 0; i < links.length; i++) {
        if (links[i].innerText.match(/Más \\d+ de \\d+/)) {
            links[i].click();
            clicked++;
        }
    }
    return clicked;
})()
"""

# JavaScript to get all chat links from the sidebar
JS_GET_CHAT_LINKS = """
(function() {
    var links = document.querySelectorAll('a[href*="/chats/"][href*="/leads/detail/"]');
    var chats = [];
    for (var i = 0; i < links.length; i++) {
        var a = links[i];
        var href = a.getAttribute('href');
        var talkMatch = href.match(/\\/chats\\/(\\d+)\\//);
        var leadMatch = href.match(/\\/leads\\/detail\\/(\\d+)/);
        if (talkMatch && leadMatch) {
            var title = a.innerText.replace(/\\n/g, ' | ').substring(0, 200);
            chats.push({href: href, talk_id: talkMatch[1], lead_id: leadMatch[1], title: title});
        }
    }
    return chats;
})()
"""

# JavaScript to scroll the chat sidebar to load more items
JS_SCROLL_SIDEBAR = """
(function() {
    var scroller = document.querySelector('.notes-wrapper__scroller, .custom-scroll, [class*="feed-list"]');
    if (!scroller) {
        var divs = document.querySelectorAll('div');
        for (var i = 0; i < divs.length; i++) {
            if (divs[i].scrollHeight > 800 && divs[i].offsetWidth < 500 && divs[i].offsetWidth > 200) {
                scroller = divs[i];
                break;
            }
        }
    }
    if (scroller) {
        scroller.scrollTop = scroller.scrollHeight;
        return 'scrolled';
    }
    return 'no_scroller';
})()
"""


class KommoChatScraper:
    """Scrapes chat conversations from Kommo CRM web interface."""

    CHATS_URL = (
        "https://{subdomain}.kommo.com/chats/"
        "?filter%5Bdate%5D%5Bdate_preset%5D={date_preset}"
        "&filter%5Bstatus%5D%5B%5D={status}"
    )

    def __init__(
        self,
        subdomain: str = "tu-dominio",
        session_dir: str = None,
        headless: bool = False,
        wait_timeout: int = 10,
    ):
        if not SELENIUM_AVAILABLE:
            raise ImportError("pip install selenium")

        self.subdomain = subdomain
        self.headless = headless
        self.wait_timeout = wait_timeout
        self.session_dir = session_dir or os.path.join(
            os.path.dirname(__file__), '..', '..', '.chrome_session'
        )
        self.driver = None
        self.conversations = []

    def start_browser(self):
        """Start Chrome with persistent session profile."""
        options = Options()
        options.add_argument(f"--user-data-dir={os.path.abspath(self.session_dir)}")
        options.add_argument("--profile-directory=KommoScraper")
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        self.driver.implicitly_wait(3)
        logger.info("Browser started")

    def stop_browser(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Browser closed")

    def is_logged_in(self) -> bool:
        """Check if we're logged into Kommo."""
        title = self.driver.title.lower()
        return 'autorización' not in title and 'authorization' not in title

    def navigate_to_chats(self, date_preset: str = "current_day", status: str = "opened"):
        """Navigate to chats view with filters."""
        url = self.CHATS_URL.format(
            subdomain=self.subdomain,
            date_preset=date_preset,
            status=status,
        )
        logger.info(f"Navigating to: {url}")
        self.driver.get(url)
        time.sleep(5)

        if not self.is_logged_in():
            raise RuntimeError(
                "Not logged in. Run login_and_save_session.py first, "
                "or create a user without 2FA."
            )
        logger.info("Chat list loaded")

    def get_chat_links(self) -> List[Dict]:
        """Get all chat links from the sidebar."""
        return self.driver.execute_script(JS_GET_CHAT_LINKS) or []

    def scroll_sidebar_to_load_all(self, max_scrolls: int = 30) -> int:
        """Scroll sidebar to load all chat items. Returns total loaded."""
        prev_count = 0
        for i in range(max_scrolls):
            links = self.get_chat_links()
            count = len(links)
            if count == prev_count and i > 2:
                break
            prev_count = count
            self.driver.execute_script(JS_SCROLL_SIDEBAR)
            time.sleep(1.5)
            logger.debug(f"Scroll {i+1}: {count} chats loaded")
        final = len(self.get_chat_links())
        logger.info(f"Sidebar loaded: {final} chats total")
        return final

    def extract_messages(self) -> List[Dict]:
        """Extract all messages from the currently open chat panel."""
        # First expand any "Más X de Y" collapsed sections
        expanded = self.driver.execute_script(JS_CLICK_MORE)
        if expanded:
            time.sleep(2)
            # Click again in case more appeared
            self.driver.execute_script(JS_CLICK_MORE)
            time.sleep(1)

        return self.driver.execute_script(JS_EXTRACT_MESSAGES) or []

    def scrape_chats(
        self,
        date_preset: str = "current_day",
        status: str = "opened",
        max_chats: int = 0,
        scroll_sidebar: bool = True,
    ) -> List[Dict]:
        """
        Scrape all chats for given date/status filter.

        Args:
            date_preset: 'current_day', 'yesterday', 'current_week', 'current_month'
            status: 'opened' or 'closed'
            max_chats: 0 = unlimited
            scroll_sidebar: scroll to load all chats in sidebar

        Returns:
            List of conversation dicts
        """
        self.navigate_to_chats(date_preset=date_preset, status=status)

        if scroll_sidebar:
            self.scroll_sidebar_to_load_all()

        chat_links = self.get_chat_links()
        total = len(chat_links)
        if max_chats > 0:
            total = min(total, max_chats)

        logger.info(f"Scraping {total} of {len(chat_links)} chats...")
        self.conversations = []

        for idx in range(total):
            chat_info = chat_links[idx]
            talk_id = chat_info['talk_id']
            lead_id = chat_info['lead_id']
            title = chat_info['title']

            logger.info(f"[{idx+1}/{total}] Talk {talk_id} Lead {lead_id}")

            # Navigate to this chat
            chat_url = f"https://{self.subdomain}.kommo.com{chat_info['href']}"
            self.driver.get(chat_url)
            time.sleep(3)

            # Extract messages
            messages = self.extract_messages()
            logger.info(f"  -> {len(messages)} messages")

            self.conversations.append({
                'index': idx,
                'talk_id': talk_id,
                'lead_id': lead_id,
                'title': title.split('|')[0].strip() if title else '',
                'messages': messages,
                'msg_count': len(messages),
                'scraped_at': datetime.now().isoformat(),
            })

            # Re-fetch chat links if we navigated away
            if idx < total - 1:
                chat_links = self.get_chat_links()
                if not chat_links:
                    # Navigate back to chat list
                    self.navigate_to_chats(date_preset=date_preset, status=status)
                    time.sleep(2)
                    chat_links = self.get_chat_links()

        logger.info(f"Done: {len(self.conversations)} chats, "
                     f"{sum(c['msg_count'] for c in self.conversations)} messages")
        return self.conversations

    def save_results(self, output_path: str):
        """Save results to JSON."""
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        output = {
            'scraped_at': datetime.now().isoformat(),
            'total_chats': len(self.conversations),
            'total_messages': sum(c['msg_count'] for c in self.conversations),
            'conversations': self.conversations,
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved to {output_path}")

    def download_via_browser(self, filename: str = 'kommo_scrape.json'):
        """Trigger a download of results from within the browser."""
        data_json = json.dumps(self.conversations, ensure_ascii=False)
        self.driver.execute_script(f"""
            var blob = new Blob([{json.dumps(data_json)}], {{type: 'application/json'}});
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = '{filename}';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        """)
        logger.info(f"Download triggered: {filename}")
