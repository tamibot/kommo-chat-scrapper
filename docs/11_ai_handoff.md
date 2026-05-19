# 11. AI Handoff - Compilación Completa del Proyecto

> Este documento permite a cualquier IA (Claude, GPT, Gemini, Cursor, etc.) retomar el proyecto desde donde se quedó. Es la fuente de verdad del estado actual, decisiones tomadas, lecciones aprendidas y trabajo pendiente.

**Última actualización:** 2026-05-19

---

## 1. ¿Qué es este proyecto?

**Kommo Chat Scrapper V4** - Sistema híbrido que extrae conversaciones de WhatsApp/Instagram/TikTok/Facebook desde Kommo CRM y las analiza con métricas de negocio.

**El problema central:** Kommo CRM no expone los mensajes de chat por API oficial. Solo da metadata de "talks" pero no el contenido. Necesitamos los mensajes para analizar la atención al cliente.

**La solución:** Flujo híbrido en 5 fases:
1. **Events API** → identifica leads con actividad de chat el día X
2. **Clasificación** → filtra: conversaciones reales vs follow-ups vs masivos
3. **Selenium headless** → navega directo a cada chat por URL y extrae mensajes del DOM
4. **API Enrichment** → agrega leads, contactos, pipelines, tags, stage changes
5. **PostgreSQL + Analytics** → guarda en 13 tablas, computa KPIs, expone vía Flask web

---

## 2. Estado Actual (Snapshot)

### Datos en PostgreSQL (Railway):
| Tabla | Registros |
|-------|-----------|
| kommo_chats | 976 |
| kommo_messages | 32,423 |
| kommo_leads | 949 |
| kommo_contacts | 937 |
| kommo_stage_changes | 2,235 |
| kommo_events | 7,476 |
| kommo_pending_attention | 304 |
| kommo_no_reply_tracking | 441 |
| kommo_lead_summary | 828 |
| kommo_scrape_errors | 0 |

### Días scrapeados:
| Fecha | Chats | Mensajes |
|-------|-------|----------|
| 2026-03-29 | 110 | 1,991 |
| 2026-03-30 | 303 | 11,100 |
| 2026-03-31 | 276 | 11,085 |
| 2026-04-02 | 10 | 265 ⚠️ |
| 2026-04-03 | 10 | 224 ⚠️ |
| 2026-04-04 | 178 | 6,039 |
| 2026-04-05 | 79 | 1,516 |
| 2026-04-27 | 5 | 143 ⚠️ |
| 2026-04-28 | 5 | 60 ⚠️ |

⚠️ = scrape parcial, necesita completarse

### Pendientes inmediatos:
1. Re-scrape Apr 1 (no tiene data), Apr 2, 3 (solo 10 chats cada uno)
2. Scrape de Apr 6-28 (3 semanas faltantes)
3. Scrape de Mar 24-28 (días con masivos, no scrapeados)

---

## 3. Arquitectura Técnica

### Stack
- **Python 3.9+** con stdlib `urllib` (no `requests`)
- **Selenium 4.x** headless Chrome para DOM scraping
- **PostgreSQL** (Railway) para storage
- **Flask + Gunicorn** para web dashboard
- **Chart.js + Bootstrap 5** para UI

### Cuenta Kommo de Prueba (Proper Tamibot)
- Account ID: `30050693`
- Subdomain: `propertamibotcom`
- Amojo ID: `46db3794-cd6c-4506-a0a6-6205b2f546e9`
- URL: `https://propertamibotcom.kommo.com`

### Credenciales (en .env, ya en repo privado)
```bash
KOMMO_BASE_URL=https://propertamibotcom.kommo.com
KOMMO_ACCESS_TOKEN=<JWT, 1082 chars, exp 2028>
KOMMO_LOGIN_EMAIL=soporte.corretaje@proper.com.pe  # SIN 2FA
KOMMO_LOGIN_PASSWORD=Tami12345$
DATABASE_URL=postgresql://postgres:RSXXjDgg...@gondola.proxy.rlwy.net:52491/railway
```

### Web Dashboard
- **URL producción**: https://kommo-chat-scrapper-kommo-scrapper.up.railway.app
- **Repo**: https://github.com/tamibot/kommo-chat-scrapper (privado)
- **Deploy**: Railway auto-deploy desde GitHub

---

## 4. Estructura de Archivos

```
kommo_chat_scrapper/
├── scripts/
│   ├── scrape_v3.py          # ⭐ Scraper principal (1100+ líneas)
│   ├── setup_account.py      # Discovery de cuenta (pipelines, fields)
│   ├── validate_setup.py     # 6 checks básicos
│   ├── health_check.py       # 26 checks completos
│   ├── db_maintenance.py     # Cleanup + consistency fixes
│   └── extract_mappings.py   # Regenera kommo_mappings.json
│
├── src/kommo/
│   ├── api_client.py         # Cliente REST API v4
│   ├── enrichment.py         # Batch fetch leads/contacts + rate limit
│   ├── analytics.py          # Motor de análisis (pending, no-reply, hot leads)
│   ├── database.py           # PostgreSQL operations
│   └── chat_scraper.py       # Clase Selenium reutilizable
│
├── web/
│   ├── app.py                # Flask app con 9 rutas
│   └── templates/            # 9 plantillas Bootstrap + Chart.js
│
├── docs/                     # 12 documentos detallados
├── config/
│   ├── kommo_mappings.json   # Auto-generado por setup_account.py
│   └── kommo_mappings.example.json
│
├── .claude/agents/           # 3 agentes para Claude Code
├── .codex/agents/            # Espejo para Codex/OpenAI
├── AGENTS.md                 # Spec agnóstica de agentes
├── CLAUDE.md                 # Contexto técnico
├── CHANGELOG.md              # Bugs corregidos
├── README.md                 # Overview público
├── Procfile + railway.json   # Deploy Railway
├── requirements.txt          # Deps: selenium, psycopg2, flask, gunicorn
├── .env                      # Credenciales (incluido en repo privado)
└── .gitignore                # Permite .env en repo privado
```

---

## 5. Decisiones Técnicas Críticas (Lecciones Aprendidas)

### 5.1 Por qué API + Selenium (no solo uno)
- **API v4 NO da contenido de mensajes** (requiere scope "chats" + HMAC amojo)
- **Selenium solo es lento** (60s+ scroll vs 5s API events)
- **Híbrido**: API descubre QUIÉN habló (rápido), Selenium extrae QUÉ dijo (necesario)

### 5.2 Detección de dirección IN/OUT (BUG HISTÓRICO)
**Bug original:** Usábamos `.feed-note__talk-outgoing` como indicador → ERA EL FOOTER, no la dirección.

**Solución correcta:**
```javascript
// El elemento .feed-note tiene clase 'feed-note-incoming' para mensajes del cliente
var feedNote = n.querySelector('.feed-note.feed-note-external');
var hasIncoming = feedNote && feedNote.className.indexOf('feed-note-incoming') >= 0;
var dir = hasIncoming ? 'IN' : 'OUT';
```

### 5.3 Bot Detection (solo en mensajes OUT)
**Bug:** Mensajes IN con author "Tami Bot" se marcaban como bot.

**Solución:** Bot detection SOLO si `dir === 'OUT'`:
```javascript
if (dir === 'OUT') {
    if (author.match(/salesbot/i)) { isBot=true; botName=match[1]; }
    else if (author.match(/tami.*bot/i)) { isBot=true; botName='TamiBot'; }
}
```

### 5.4 WhatsApp Business no es agente humano
**Bug:** Author "WhatsApp Business" se contaba en top agents.

**Solución:** `sender_type = 'system'` cuando author == 'WhatsApp Business' || 'TikTok'. Y para "Top Agentes" leer de `kommo_leads.responsible_user_name`, no del author de mensajes.

### 5.5 Timestamps con timezone correcto
**Bug:** `datetime(y,m,d,5,0,0).timestamp()` daba offset incorrecto.

**Solución:**
```python
from datetime import timezone, timedelta
PERU = timezone(timedelta(hours=-5))
day_start = datetime(y, m, d, 0, 0, 0, tzinfo=PERU)
from_ts = int(day_start.timestamp())  # Match exacto con Kommo UI
```

### 5.6 Events API limit
**Era 100, debe ser 250** (max de la API). Cortó las requests a la mitad.

### 5.7 Selenium se cuelga en background
**Solución:**
- `set_page_load_timeout(20)`, `set_script_timeout(15)`
- `restart_driver()` cuando hay timeout → recrea + re-login
- Force flush stdout para ver progreso en tasks background
- Anti-ban delays 1.5-2.5s randomizados

### 5.8 reCAPTCHA después de muchos logins
**Solución:**
1. `rm -rf /tmp/kommo_scraper_session`
2. Cambiar contraseña del usuario en Kommo
3. Esperar 5-10 min
4. Si persiste: login manual desde Chrome real

### 5.9 Subdomain hardcodeado
**Bug:** `SUBDOMAIN = 'propertamibotcom'` en código.

**Solución:**
```python
_base_url = ENV.get('KOMMO_BASE_URL', '')
SUBDOMAIN = _base_url.replace('https://', '').split('.')[0]
```

### 5.10 Clasificación de leads para evitar scrapear masivos
Del Events API agrupamos por lead_id:
- **conversation**: tiene IN + OUT → SCRAPE
- **pending**: solo IN → SCRAPE (cliente esperando)
- **follow_up**: 1-2 OUT solo → SKIP (bot follow-up)
- **masivo**: 3+ OUT sin IN → SKIP (campaña masiva)

Esto reduce de ~4000 leads/día a ~300 conversaciones reales.

---

## 6. DOM Selectors (Kommo Web Verificados 2026-04-01)

```javascript
// Chats list (sidebar)
'a[href*="/chats/"][href*="/leads/detail/"]'  // Links de chat
// URL pattern: /chats/{talk_id}/leads/detail/{lead_id}

// Mensajes en panel derecho
'.feed-note-wrapper-amojo'                  // Wrapper de cada mensaje
'.feed-note.feed-note-external'             // El .feed-note interno
'.feed-note.feed-note-external.feed-note-incoming' // SOLO IN
'.feed-note__talk-outgoing'                 // Footer (NO indica dirección!)

// Contenido
'.feed-note__amojo-user, .js-amojo-author'  // Author (común IN/OUT)
'.js-feed-note__date, .feed-note__date'     // Timestamp (común)
'.feed-note__message_paragraph'             // Texto del mensaje
'.message_delivery-status_checkmark'        // Read/Delivered (solo OUT)

// Conversation ID
'.feed-note__talk-outgoing-title'           // "Conversación № A261387"

// Expand collapsed
// Buscar <a> con texto matching /^Más \d+ de \d+$/
```

---

## 7. API Endpoints (Kommo v4)

```
GET /api/v4/account?with=amojo_id
GET /api/v4/leads?filter[id][]={id}&with=contacts        # Batch hasta 50
GET /api/v4/contacts?filter[id][]={id}                    # Batch hasta 50
GET /api/v4/leads/pipelines
GET /api/v4/leads/custom_fields?limit=250
GET /api/v4/contacts/custom_fields?limit=250
GET /api/v4/leads/tags
GET /api/v4/talks?limit=250                               # Metadata, NO mensajes
GET /api/v4/events?limit=250                              # Max es 250 NO 100
GET /api/v4/users

# Event types útiles
filter[type][]=incoming_chat_message
filter[type][]=outgoing_chat_message
filter[type][]=lead_status_changed
filter[type][]=entity_tag_added
filter[type][]=talk_created

# Filtro por fecha (Unix timestamps Peru UTC-5)
filter[created_at][from]=UNIX
filter[created_at][to]=UNIX
```

### Rate Limit
- Max 7 req/seg (Kommo). Usar 6 para seguridad.
- 429 → backoff exponencial, max 3 retries.

### Lo que NO funciona
- `/api/v4/talks/{id}/messages` → 403 Invalid scope (necesita scope "chats")
- `api-c.kommo.com` → 401 Account not found (usar subdomain directo)

---

## 8. Schema PostgreSQL (13 tablas)

### Principales
```sql
kommo_messages       -- Cada mensaje individual con dir, sender_type, is_bot
kommo_chats          -- Resumen por chat/día con analytics
kommo_leads          -- Lead enrichment con pipeline, tags, custom_fields JSONB
kommo_contacts       -- Nombre, phone, email
kommo_stage_changes  -- Historial vía events API
kommo_events         -- Eventos del día (tags, links, creations)
```

### Analytics (computadas)
```sql
kommo_pending_attention   -- Chats donde NOSOTROS debemos responder
kommo_no_reply_tracking   -- Chats sin respuesta del CLIENTE
kommo_lead_summary        -- Métricas agregadas por lead (hot detection)
kommo_conversations_compiled -- JSON + texto plano para LLM
kommo_daily_metrics       -- Agregados por día
```

### Operacionales
```sql
kommo_app_settings   -- Config UI dinámica (token, URL, etc.)
kommo_scrape_errors  -- Errores no-blocking del scraper
```

### Campos importantes en kommo_messages
```
direction       'IN' | 'OUT'
sender_type     'contact' | 'bot' | 'agent' | 'system'
is_bot          boolean (solo true en OUT con SalesBot/TamiBot)
author          Nombre que muestra Kommo
bot_name        Si is_bot, nombre del bot
msg_type        'text' | 'image' | 'video' | 'audio' | 'file' | 'sticker'
delivery_status 'Read' | 'Delivered' | '' (solo en OUT)
msg_timestamp   Formato Kommo "DD.MM.YYYY HH:MM" o "Yesterday HH:MM"
parsed_at       timestamp UTC parseado
origin          'waba' | 'instagram_business' | 'tiktok_kommo' | 'facebook'
```

### Campos importantes en kommo_chats
```
attention_status   'attended' | 'pending_response' | 'bot_only' | 'outbound_only' | 'empty'
consecutive_out_end  Mensajes OUT consecutivos al final
consecutive_in_end   Mensajes IN consecutivos al final
human_takeover_at_msg  En qué msg # intervino un humano
bot_names[]          Lista de bots que participaron
human_agents[]       Lista de agentes humanos
category           'conversation' | 'pending' | 'follow_up' | 'masivo'
```

---

## 9. Comandos Operacionales

```bash
# Setup inicial (solo primera vez)
python scripts/setup_account.py        # Descubre pipelines, campos, usuarios
python scripts/validate_setup.py       # 6 checks rápidos
python scripts/health_check.py         # 26 checks completos

# Scraping diario
python scripts/scrape_v3.py                              # ayer
python scripts/scrape_v3.py --date current_day           # hoy
python scripts/scrape_v3.py --max-chats 15               # test con 15
python scripts/scrape_v3.py --from-date 2026-04-01 --to-date 2026-04-05

# Mantenimiento
python scripts/db_maintenance.py --dry  # Check only
python scripts/db_maintenance.py        # Fix automático
```

---

## 10. Trabajo Pendiente (Roadmap)

### Inmediato
- [ ] Re-scrape Apr 1, 2, 3 con la lógica corregida
- [ ] Scrape Apr 6-28 (3 semanas)
- [ ] Scrape Mar 24-28 con detección de masivos

### Mejoras técnicas
- [ ] **Batch insert** a PostgreSQL (actualmente inserción 1 por 1, lento con 10k+ msgs)
- [ ] Auto-restart del scraper en cron diario a las 6am
- [ ] Alertas cuando hay chats pendientes de alta urgencia (Telegram/email)
- [ ] Mejorar Top Agentes cruzando con canales WhatsApp Business

### Features
- [ ] Conexión a LLM (Claude/GPT) usando `kommo_conversations_compiled`
- [ ] Score automático de calidad de atención por conversación
- [ ] Detección de oportunidades perdidas (interés del cliente sin follow-up)
- [ ] Export a Google Sheets para gerencia

### Mantenimiento
- [ ] Token API expira 2028 - configurar rotación automática
- [ ] Implementar tests E2E del flujo completo
- [ ] Documentar cómo agregar nuevos canales (Telegram, Email)

---

## 11. Cómo Continuar (Para la próxima IA)

### Primera vez en el proyecto:
```bash
cd /Users/pruebacomprador/Desktop/Antigratity-google/kommo_chat_scrapper
git pull origin main
python scripts/health_check.py    # Verifica que todo funciona
```

### Si el scraper falla:
1. `pkill -f kommo_scraper && pkill -f chromedriver`
2. `rm -rf /tmp/kommo_scraper_session`
3. Verifica reCAPTCHA → cambiar contraseña en Kommo si necesario
4. `python scripts/health_check.py` para diagnosticar

### Si la DB tiene problemas:
```bash
python scripts/db_maintenance.py --dry   # Detecta issues
python scripts/db_maintenance.py         # Auto-fix
```

### Lectura recomendada (en orden):
1. `docs/00_master_index.md` - Mapa general
2. **Este documento (`docs/11_ai_handoff.md`)** - Estado actual
3. `docs/09_onboarding_guide.md` - Setup de cero
4. `docs/04_scraper_engine.md` - Cómo funciona el scraper
5. `CLAUDE.md` - Reglas técnicas concretas
6. `CHANGELOG.md` - Bugs corregidos y cuándo

### Convenciones del proyecto:
- ❌ NO usar `requests`, usar `urllib.request` (stdlib)
- ❌ NO hardcodear credentials, leer de `.env`
- ❌ NO hacer print sin `flush=True` en scraper (background)
- ✅ Logging a stdout, no a archivos
- ✅ UPSERT en todas las tablas (re-ejecutar es idempotente)
- ✅ Salidas en `output/YYYY-MM-DD_HHMMSS/`
- ✅ Selenium se importa lazy (solo cuando se necesita)
- ✅ Rate limit API: max 6 req/seg

---

## 12. Contacto y Soporte

- **Repo privado**: https://github.com/tamibot/kommo-chat-scrapper
- **Web producción**: https://kommo-chat-scrapper-kommo-scrapper.up.railway.app
- **Email**: mvelascoo@tamibot.com
- **WhatsApp**: +51 995547475

---

## Apéndice: Variables de Entorno Completas

```bash
# Kommo
KOMMO_BASE_URL=https://propertamibotcom.kommo.com
KOMMO_ACCESS_TOKEN=eyJ0eXA...  # JWT del Token API v4
KOMMO_LOGIN_EMAIL=soporte.corretaje@proper.com.pe
KOMMO_LOGIN_PASSWORD=Tami12345$

# Database
DATABASE_URL=postgresql://postgres:RSXXjDgg...@gondola.proxy.rlwy.net:52491/railway

# Optional
LOG_LEVEL=INFO
```
