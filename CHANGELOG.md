# Changelog

Todos los cambios notables de este proyecto se documentaran en este archivo.

## [1.0.0] - 2026-04-01

### Agregado
- **Scraper v3** production-grade con retries, anti-ban delays, error recovery
- **7 tablas PostgreSQL** optimizadas:
  - `kommo_contacts` - nombre, teléfono, email
  - `kommo_leads` - pipeline, stage, tags, responsable, custom fields (JSONB)
  - `kommo_chats` - analytics: bot/human counts, attention_status, interactions
  - `kommo_messages` - author, is_bot, bot_name, sender_type, timestamps reales
  - `kommo_stage_changes` - historial de cambios de etapa
  - `kommo_conversations_compiled` - conversación JSON + texto plano para LLM
  - `kommo_daily_metrics` - métricas agregadas por día
- **API Enrichment module** con rate limiting (6 req/s) y batch fetching
- **Detección Bot vs Humano**: author contiene "SalesBot(nombre)" o "TamiBot"
- **Attention status**: attended, pending_response, bot_only, outbound_only
- **Conversation compiler**: JSON estructurado + texto plano por cliente
- **10+ bots identificados**: TamiBot, RENTAS BOT IA, INICIO MODO, etc.

### Métricas extraídas
- Conteo de interacciones (cambios de dirección IN/OUT)
- Punto de takeover humano (en qué mensaje interviene el agente)
- Estado de atención (atendido, pendiente, solo bot)
- Tipo de media (image, video, file, audio, pdf, sticker)
- Agentes humanos identificados por nombre
- Tags del lead (RENTAS, stop_ai, etc.)

## [0.3.0] - 2026-04-01

### Agregado
- Selectores DOM verificados para scraping de chats de Kommo
- Extraccion via inyeccion JavaScript (sin depender de CSS selectors genericos)
- Soporte para expandir mensajes colapsados ("Más X de Y")
- Descarga de resultados como JSON desde el browser
- Test exitoso: 5 chats, 71 mensajes extraidos con direccion IN/OUT

### Selectores DOM clave
- `.feed-note-wrapper-amojo` - wrapper de cada mensaje
- `.feed-note__talk-outgoing` - flag de mensaje saliente
- `.feed-note__message_paragraph` - texto del mensaje
- `.feed-note__talk-outgoing-number` - timestamp
- `a[href*="/chats/"][href*="/leads/detail/"]` - links de chat en sidebar

## [0.2.0] - 2026-04-01

### Agregado
- Cliente API v4 de Kommo (`src/kommo/api_client.py`)
  - Retry automatico con backoff exponencial
  - Rate limit handling (429)
  - Paginacion de leads, talks, events
  - Batch fetch de leads por ID (50 por batch)
- Scraper de chats via Selenium (`src/kommo/chat_scraper.py`)
  - Navegacion a vista de chats con filtros de fecha/status
  - Scroll para cargar todos los chats del sidebar
  - Click en cada chat y extraccion de mensajes
  - Soporte para texto, imagenes, audio, archivos
  - Fallback con extraccion JavaScript
- Orquestador principal (`main.py`)
  - Modos: --api-only, --scrape-only, completo
  - Filtros: --date (current_day, yesterday, week, month)
  - Merge de datos API + scraping
  - Export a JSON y CSV
- Script de extraccion de mapeos (`scripts/extract_mappings.py`)
  - Pipelines y etapas
  - Campos personalizados de leads (171) y contactos (22)
  - Usuarios (7)
- Mapeos de cuenta guardados en `config/kommo_mappings.json`

### Descubierto
- API v4 NO expone contenido de mensajes de chat
- El endpoint /talks/{id}/messages requiere scope adicional
- La API amojo requiere HMAC-SHA1 con channel_secret
- El subdomain debe ser propertamibotcom.kommo.com (no api-c)
- Hay 250+ talks activos por dia (alto volumen WhatsApp)

## [0.1.0] - 2026-04-01

### Agregado
- Inicializacion del proyecto
- Estructura base de directorios
- Archivos de configuracion (README, CLAUDE.md, .env.example)
- Configuracion de .gitignore
- Template de credenciales
