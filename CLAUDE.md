# CLAUDE.md - Kommo Chat Scrapper

## Proyecto
Scrapper de chats de Kommo CRM con enfoque hibrido: API v4 + Selenium browser automation.

## Stack
- Python 3.9+ (stdlib urllib para HTTP, no requests)
- Kommo API v4 (REST, Bearer token)
- Selenium 4.x para browser automation
- PostgreSQL (psycopg2-binary)
- Flask + Gunicorn para dashboard web
- Chart.js para graficos
- Bootstrap 5 para UI

## Cuenta Kommo (Proper Tamibot)
- Account: Proper Tamibot (ID: 30050693)
- Subdomain: propertamibotcom
- Amojo ID: 46db3794-cd6c-4506-a0a6-6205b2f546e9
- API Domain: propertamibotcom.kommo.com (NO api-c.kommo.com)
- Canal principal: WhatsApp Business API (waba)

## Arquitectura
- `scripts/scrape_v3.py` - Scraper principal (produccion)
- `scripts/setup_account.py` - Discovery de cuenta nueva
- `scripts/validate_setup.py` - Validacion de credenciales
- `src/kommo/api_client.py` - Cliente API v4 con retry, rate limit
- `src/kommo/enrichment.py` - Enrichment con rate limiting (6 req/s)
- `src/kommo/database.py` - PostgreSQL operations (10 tablas)
- `src/kommo/chat_scraper.py` - Selenium scraper (clase reutilizable)
- `web/app.py` - Flask dashboard web
- `config/kommo_mappings.json` - Mapeos de pipelines, stages, custom fields, usuarios

## API Endpoints que funcionan
- GET /api/v4/account?with=amojo_id
- GET /api/v4/leads?filter[id][]={id}&with=contacts (batch 50)
- GET /api/v4/contacts?filter[id][]={id} (batch 50)
- GET /api/v4/leads/pipelines
- GET /api/v4/leads/custom_fields
- GET /api/v4/contacts/custom_fields
- GET /api/v4/leads/tags
- GET /api/v4/talks?limit=250 (metadata de chats, NO mensajes)
- GET /api/v4/events (filtrar por tipo y fecha)
- GET /api/v4/users

## Tipos de eventos utiles
- incoming_chat_message - mensaje entrante (tiene talk_id + lead_id)
- outgoing_chat_message - mensaje saliente
- lead_status_changed - cambio de etapa (tiene before/after pipeline+status)
- entity_tag_added - tag agregado (tiene nombre del tag)
- entity_linked - vinculacion lead-contacto
- lead_added - lead creado
- contact_added - contacto creado
- talk_created - nueva conversacion

## Lo que NO funciona via API v4
- Contenido real de mensajes de chat (requiere amojo API con HMAC-SHA1)
- /api/v4/talks/{id}/messages (403 Invalid scope - necesita scope "chats")
- api-c.kommo.com (401 Account not found, usar subdomain directo)

## DOM Selectors (verificados 2026-04-01)
- Chat list links: `a[href*="/chats/"][href*="/leads/detail/"]`
- URL pattern: `/chats/{talk_id}/leads/detail/{lead_id}`
- Message wrappers: `.feed-note-wrapper-amojo`
- Outgoing flag: `.feed-note__talk-outgoing` (dentro del wrapper)
- Message text: `.feed-note__message_paragraph`
- Real timestamps: `.js-feed-note__date` o `.feed-note__date`
- Author/sender: `.feed-note__amojo-user` o `.js-amojo-author`
- Delivery status: `.message_delivery-status_checkmark`
- Expand collapsed: links con texto "Mas X de Y"
- Conversation ID: `.feed-note__talk-outgoing-title` -> "Conversacion No AXXXXXX"

## Filtros de fecha en URL
- Preset: `filter[date][date_preset]=yesterday` (yesterday, current_day, previous_week, current_week)
- Unix range: `filter[date][from]=UNIX&filter[date][to]=UNIX` (mas preciso, por dia)
- Midnight Peru (UTC-5) = 5:00 UTC. Ejemplo: 2026-04-01 = from=1775019600 to=1775105999

## Analisis de volumenes (descubierto)
- Events API muestra TODOS los chats con actividad (incluye masivos)
- Selenium "opened" muestra solo chats activos (~95/dia)
- Conversaciones reales (IN+OUT) ~300/dia
- Envios masivos: dias con 4,000+ leads (solo OUT 1-2 msgs = follow-up bot)

## Login Selenium (sin 2FA)
- Usuario: soporte.corretaje@proper.com.pe
- Session dir: /tmp/kommo_scraper_session
- Anti-ban: delays aleatorios 1.5-2.5s entre chats

## Troubleshooting: reCAPTCHA
Si Kommo muestra "Please check reCaptcha" al hacer login headless:
1. Borrar la sesion: `rm -rf /tmp/kommo_scraper_session`
2. Cambiar la clave del usuario en Kommo
3. Esperar unos minutos y volver a intentar
4. Si persiste, hacer login manual desde Chrome real una vez
Causa: muchos intentos de login headless seguidos activan captcha

## Convenciones
- Credenciales en .env, nunca hardcodear
- Salida en output/YYYY-MM-DD_HHMMSS/
- Logging a stdout
- HTTP con urllib.request (stdlib), no requiere pip install para API
- Selenium solo se importa cuando se necesita
- Rate limit API: max 6 req/s (7/s es el limite de Kommo)

## Comandos utiles
```bash
# Setup inicial
python scripts/setup_account.py         # Descubrir cuenta
python scripts/validate_setup.py        # Validar todo

# Scraper v3 (produccion)
python scripts/scrape_v3.py                        # ayer, todos los chats
python scripts/scrape_v3.py --date current_day     # hoy
python scripts/scrape_v3.py --max-chats 15         # test con 15
python scripts/scrape_v3.py --skip-enrich          # sin API enrichment
python scripts/scrape_v3.py --from-date 2026-03-25 --to-date 2026-03-31  # historico
python scripts/scrape_v3.py --date previous_week   # semana pasada (7 dias)
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

## Dashboard Web (Flask)
- `/` - Dashboard con graficos Chart.js, stats, tags, bots, agentes
- `/chats` - Lista de chats con filtros por fecha y estado clickeables
- `/chat/{id}` - Detalle con burbujas estilo WhatsApp + links a Kommo
- `/pending` - Pendientes NUESTROS (cliente escribio, no respondimos)
- `/no-reply` - Sin respuesta del CLIENTE (nosotros escribimos, no respondio)
- `/stages` - Cambios de etapa con top destinos
- `/settings` - Config con validacion de token API
- `/api/health` - Health check JSON
- `/api/validate-token` - Validar token API
