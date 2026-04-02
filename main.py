#!/usr/bin/env python3
"""
Kommo Chat Scrapper - Main entry point.

Extracts chat conversations from Kommo CRM using:
1. API v4 for structured data (leads, contacts, pipelines, talks metadata)
2. Browser automation (Selenium) for actual chat message content

Usage:
    python main.py                          # Scrape today's open chats
    python main.py --date yesterday         # Yesterday's chats
    python main.py --date current_week      # This week's chats
    python main.py --api-only               # Only extract API data (no browser)
    python main.py --max-chats 10           # Limit to 10 chats
    python main.py --headless               # Run browser in headless mode
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime

# Setup logging
os.makedirs('logs', exist_ok=True)
os.makedirs('output', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler('logs/app.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def extract_api_data(client, output_dir: str):
    """Extract structured data from Kommo API v4."""
    logger.info("=== Extracting API data ===")

    # Get recent active talks (first page = 250 most recent)
    logger.info("Fetching recent active talks (max 250)...")
    talks_data = client.get_talks(limit=250)
    talks = talks_data.get('_embedded', {}).get('talks', [])
    logger.info(f"  Found {len(talks)} active talks")

    # Get unique lead IDs and contact IDs from talks
    lead_ids = set()
    contact_ids = set()
    for talk in talks:
        if talk.get('entity_type') == 'lead' and talk.get('entity_id'):
            lead_ids.add(talk['entity_id'])
        if talk.get('contact_id'):
            contact_ids.add(talk['contact_id'])

    # Fetch lead details in batches using filter
    logger.info(f"Fetching {len(lead_ids)} leads in batches...")
    leads_data = []
    lead_id_list = list(lead_ids)
    batch_size = 50
    for i in range(0, len(lead_id_list), batch_size):
        batch = lead_id_list[i:i+batch_size]
        filter_params = '&'.join(f'filter[id][]={lid}' for lid in batch)
        try:
            data = client.get(f'/api/v4/leads?{filter_params}&with=contacts&limit=250')
            batch_leads = data.get('_embedded', {}).get('leads', [])
            leads_data.extend(batch_leads)
            logger.info(f"  Batch {i//batch_size+1}: fetched {len(batch_leads)} leads")
        except Exception as e:
            logger.warning(f"  Batch failed: {e}")
        import time as _time
        _time.sleep(0.5)

    # Fetch recent chat events
    logger.info("Fetching recent chat events...")
    events_data = client.get('/api/v4/events?limit=100')
    chat_events = [
        e for e in events_data.get('_embedded', {}).get('events', [])
        if 'chat_message' in e.get('type', '')
    ]
    logger.info(f"  Found {len(chat_events)} chat events")

    # Save all API data
    api_output = {
        'extracted_at': datetime.now().isoformat(),
        'talks': talks,
        'leads': leads_data,
        'chat_events': chat_events,
        'stats': {
            'total_talks': len(talks),
            'total_leads': len(leads_data),
            'total_chat_events': len(chat_events),
            'unique_contacts': len(contact_ids),
        }
    }

    path = os.path.join(output_dir, 'api_data.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(api_output, f, indent=2, ensure_ascii=False)
    logger.info(f"API data saved to {path}")

    return api_output


def scrape_chats(args, output_dir: str):
    """Scrape chat messages via browser automation."""
    from src.kommo.chat_scraper import KommoChatScraper

    logger.info("=== Scraping chat messages via browser ===")

    scraper = KommoChatScraper(
        subdomain="propertamibotcom",
        headless=args.headless,
        chrome_profile_path=args.chrome_profile,
    )

    try:
        scraper.start_browser()
        conversations = scraper.scrape_all_chats(
            date_preset=args.date,
            status=args.status,
            max_chats=args.max_chats,
            load_full_history=not args.no_history,
        )

        # Save results
        output_path = os.path.join(output_dir, 'chat_messages.json')
        scraper.save_to_json(output_path)

        return conversations

    finally:
        scraper.stop_browser()


def merge_data(api_data: dict, conversations: list, output_dir: str):
    """Merge API data with scraped chat messages into a unified dataset."""
    logger.info("=== Merging API + scraped data ===")

    # Build a lookup of talks by lead_id
    talks_by_lead = {}
    for talk in api_data.get('talks', []):
        lid = talk.get('entity_id')
        if lid:
            talks_by_lead.setdefault(lid, []).append(talk)

    # Build a lookup of leads
    leads_by_id = {}
    for lead in api_data.get('leads', []):
        leads_by_id[lead.get('id')] = lead

    # Load mappings
    mappings_path = os.path.join('config', 'kommo_mappings.json')
    mappings = {}
    if os.path.exists(mappings_path):
        with open(mappings_path) as f:
            mappings = json.load(f)

    # Enrich conversations with API data
    enriched = []
    for conv in conversations:
        lead_id = conv.get('metadata', {}).get('lead_id', '')
        if lead_id and lead_id.isdigit():
            lead_id_int = int(lead_id)
            lead = leads_by_id.get(lead_id_int, {})
            talk_list = talks_by_lead.get(lead_id_int, [])

            # Add pipeline/stage names from mappings
            pipeline_id = str(lead.get('pipeline_id', ''))
            status_id = str(lead.get('status_id', ''))
            pipeline_info = mappings.get('pipelines', {}).get(pipeline_id, {})
            stage_info = pipeline_info.get('stages', {}).get(status_id, {})

            conv['lead_data'] = {
                'id': lead.get('id'),
                'name': lead.get('name'),
                'price': lead.get('price'),
                'pipeline_id': lead.get('pipeline_id'),
                'pipeline_name': pipeline_info.get('name', ''),
                'status_id': lead.get('status_id'),
                'stage_name': stage_info.get('name', ''),
                'responsible_user_id': lead.get('responsible_user_id'),
                'responsible_user': mappings.get('users', {}).get(
                    str(lead.get('responsible_user_id', '')), {}
                ).get('name', ''),
                'custom_fields': lead.get('custom_fields_values', []),
                'created_at': lead.get('created_at'),
                'updated_at': lead.get('updated_at'),
            }
            conv['talks'] = talk_list
        enriched.append(conv)

    # Save merged output
    output = {
        'generated_at': datetime.now().isoformat(),
        'total_conversations': len(enriched),
        'stats': api_data.get('stats', {}),
        'conversations': enriched,
    }

    path = os.path.join(output_dir, 'full_export.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"Full export saved to {path}")

    # Also save a CSV-friendly summary
    save_summary_csv(enriched, output_dir)

    return output


def save_summary_csv(conversations: list, output_dir: str):
    """Save a CSV summary of conversations."""
    import csv

    path = os.path.join(output_dir, 'summary.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Lead ID', 'Lead Name', 'Pipeline', 'Stage', 'Responsible',
            'Message Count', 'Last Message Time', 'Chat Origin',
        ])
        for conv in conversations:
            lead = conv.get('lead_data', {})
            talks = conv.get('talks', [])
            origin = talks[0].get('origin', '') if talks else ''
            writer.writerow([
                lead.get('id', conv.get('metadata', {}).get('lead_id', '')),
                lead.get('name', conv.get('metadata', {}).get('lead_name', '')),
                lead.get('pipeline_name', ''),
                lead.get('stage_name', ''),
                lead.get('responsible_user', ''),
                conv.get('message_count', 0),
                conv.get('metadata', {}).get('time', ''),
                origin,
            ])
    logger.info(f"Summary CSV saved to {path}")


def main():
    parser = argparse.ArgumentParser(description='Kommo Chat Scrapper')
    parser.add_argument('--date', default='current_day',
                        choices=['current_day', 'yesterday', 'current_week', 'current_month'],
                        help='Date filter for chats')
    parser.add_argument('--status', default='opened',
                        choices=['opened', 'closed', ''],
                        help='Chat status filter')
    parser.add_argument('--max-chats', type=int, default=0,
                        help='Maximum chats to scrape (0=unlimited)')
    parser.add_argument('--api-only', action='store_true',
                        help='Only extract API data, no browser scraping')
    parser.add_argument('--scrape-only', action='store_true',
                        help='Only scrape browser, skip API')
    parser.add_argument('--headless', action='store_true',
                        help='Run browser in headless mode')
    parser.add_argument('--no-history', action='store_true',
                        help='Do not scroll to load full chat history')
    parser.add_argument('--chrome-profile', type=str, default=None,
                        help='Path to Chrome profile directory')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Output directory (default: output/YYYY-MM-DD_HHMMSS)')

    args = parser.parse_args()

    # Create timestamped output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        output_dir = os.path.join('output', timestamp)
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Kommo Chat Scrapper - {datetime.now().isoformat()}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Date filter: {args.date} | Status: {args.status}")

    api_data = {}
    conversations = []

    # Step 1: API data extraction
    if not args.scrape_only:
        from src.kommo.api_client import KommoAPIClient
        client = KommoAPIClient.from_env()
        api_data = extract_api_data(client, output_dir)

    # Step 2: Browser scraping
    if not args.api_only:
        conversations = scrape_chats(args, output_dir)

    # Step 3: Merge if both are available
    if api_data and conversations:
        merge_data(api_data, conversations, output_dir)

    logger.info("=== Done ===")


if __name__ == '__main__':
    main()
