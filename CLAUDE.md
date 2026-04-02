# CLAUDE.md - Kommo Chat Scrapper

## Proyecto
Scrapper de chats de Kommo CRM con enfoque hibrido: API v4 + Selenium browser automation.

## Stack
- Python 3.9+ (stdlib urllib para HTTP, no requests)
- Kommo API v4 (REST, Bearer token)
- Selenium 4.x para browser automation
- Google APIs (futuro: export a Sheets/Drive)

## Cuenta Kommo
- Account: Proper Tamibot (ID: 30050693)
- Subdomain: propertamibotcom
- Amojo ID: 46db3794-cd6c-4506-a0a6-6205b2f546e9
- API Domain: propertamibotcom.kommo.com (NO api-c.kommo.com)
- Canal principal: WhatsApp Business API (waba)

## Arquitectura
- `main.py` - Orquestador con argparse (--api-only, --scrape-only, --date, --max-chats, etc.)
- `src/kommo/api_client.py` - Cliente API v4 con retry, rate limit handling, paginacion
- `src/kommo/chat_scraper.py` - Selenium scraper para vista de chats
- `config/kommo_mappings.json` - Mapeos de pipelines, stages, custom fields, usuarios
- `scripts/extract_mappings.py` - Script para regenerar los mapeos

## API Endpoints que funcionan
- GET /api/v4/account?with=amojo_id
- GET /api/v4/leads?filter[id][]={id}&with=contacts
- GET /api/v4/leads/pipelines
- GET /api/v4/leads/custom_fields
- GET /api/v4/contacts/custom_fields
- GET /api/v4/talks?limit=250 (metadata de chats, NO mensajes)
- GET /api/v4/events (incoming_chat_message, outgoing_chat_message)
- GET /api/v4/users

## Lo que NO funciona via API v4
- Contenido real de mensajes de chat (requiere amojo API con HMAC-SHA1)
- /api/v4/talks/{id}/messages (403 Invalid scope)
- api-c.kommo.com (401 Account not found, usar subdomain directo)

## Convenciones
- Credenciales en .env, nunca hardcodear
- Salida en output/YYYY-MM-DD_HHMMSS/
- Logging a logs/app.log + stdout
- HTTP con urllib.request (stdlib), no requiere pip install para API
- Selenium solo se importa cuando se necesita (scrape mode)

## DOM Selectors (verificados 2026-04-01)
- Chat list links: `a[href*="/chats/"][href*="/leads/detail/"]`
- URL pattern: `/chats/{talk_id}/leads/detail/{lead_id}`
- Message wrappers: `.feed-note-wrapper-amojo`
- Outgoing flag: `.feed-note__talk-outgoing` (dentro del wrapper)
- Message text: `.feed-note__message_paragraph`
- Timestamps: `.feed-note__talk-outgoing-number`
- Expand collapsed: links con texto "Más X de Y"
- Conversation ID: `.feed-note__talk-outgoing-title` -> "Conversación № AXXXXXX"

## Comandos utiles
```bash
# Scraper v3 (produccion)
python scripts/scrape_v3.py                        # ayer, todos los chats
python scripts/scrape_v3.py --date current_day     # hoy
python scripts/scrape_v3.py --max-chats 15         # test con 15
python scripts/scrape_v3.py --skip-enrich          # sin API enrichment
python scripts/scrape_v3.py --from-date 2026-03-25 --to-date 2026-03-31  # historico

# Otros
python main.py --api-only          # Solo API, rapido
python scripts/extract_mappings.py # Regenerar mapeos
```

## Base de datos PostgreSQL (10 tablas)
- `kommo_contacts` - nombre, telefono, email
- `kommo_leads` - pipeline, stage, tags[], responsable, custom_fields JSONB
- `kommo_chats` - analytics: bot/human counts, attention_status, interactions
- `kommo_messages` - author, is_bot, bot_name, sender_type, timestamps reales
- `kommo_stage_changes` - historial de cambios de etapa (via events API)
- `kommo_events` - TODOS los eventos relevantes (tags, links, creaciones)
- `kommo_conversations_compiled` - JSON + texto plano por cliente para LLM
- `kommo_daily_metrics` - metricas agregadas por dia
- `kommo_scrape_errors` - errores de scraping (non-blocking)
- `kommo_no_reply_tracking` - chats sin respuesta del cliente

## Login Selenium (sin 2FA)
- Usuario: soporte.corretaje@proper.com.pe
- Session dir: /tmp/kommo_scraper_session
- Anti-ban: delays aleatorios 2-4s entre chats
