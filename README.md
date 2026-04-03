# Kommo Chat Scrapper

Herramienta automatizada para extraer, enriquecer y analizar conversaciones de WhatsApp desde Kommo CRM. Incluye dashboard web, deteccion de bots vs humanos, y metricas de atencion.

---

## Como funciona

El sistema combina dos fuentes de datos:

1. **Kommo API v4** - Extrae datos estructurados (leads, contactos, pipelines, tags, eventos, cambios de etapa)
2. **Selenium headless** - Navega la vista de chats y extrae el contenido real de los mensajes (la API no expone mensajes de chat)

### Flujo de ejecucion

```
1. Login automatico (usuario sin 2FA)
2. Navegar a chats del dia con filtro Unix timestamp
3. Scroll virtual para cargar todos los chats
4. Por cada chat:
   - Navegar a la URL del chat
   - Expandir mensajes colapsados ("Mas X de Y")
   - Extraer mensajes via JavaScript injection
   - Detectar: autor, bot/humano, media, timestamp
5. Enriquecer via API:
   - Leads con campos custom, tags, pipeline, responsable
   - Contactos con telefono y email
   - Eventos del dia (tags, cambios etapa, creaciones)
   - Stage changes historicos
6. Guardar en PostgreSQL (10 tablas)
7. Compilar conversaciones por cliente (JSON para LLM)
8. Calcular metricas diarias
```

### Deteccion de Bot vs Humano

El scraper identifica automaticamente quien envio cada mensaje:

| Tipo | Como detecta | Ejemplo |
|------|-------------|---------|
| **Bot** | Author contiene "SalesBot" o "Tami Bot" | `SalesBot (INICIO INVERSIONES 25.07.25)` |
| **Agente humano** | Mensaje OUT sin patron de bot | `Martin Velasco`, `Daisy` |
| **Contacto** | Mensaje IN (entrante del cliente) | `Jose Junior Quispe Figueroa` |

### Analisis de volumenes (Events API)

Para entender los volumenes reales de un dia:

| Tipo | Que es | Ejemplo Mar 31 |
|------|--------|----------------|
| **Conversaciones reales** | Leads con mensajes IN + OUT | 295 |
| **Pendientes** | Solo IN (cliente escribio, sin respuesta) | 45 |
| **Follow-up** | Solo 1-2 OUT (bot de seguimiento) | 109 |
| **Masivo** | Solo 3+ OUT (campana masiva) | 11 |
| **Selenium "opened"** | Solo chats activos abiertos | 95 |

---

## Implementacion para un nuevo cliente

### Paso 1: Clonar repositorio

```bash
git clone https://github.com/tamibot/kommo-chat-scrapper.git
cd kommo-chat-scrapper
```

### Paso 2: Instalar dependencias

```bash
pip install selenium psycopg2-binary flask gunicorn
```

**Requisitos del sistema:**
- Python 3.9+
- Google Chrome instalado (para Selenium headless)
- PostgreSQL (Railway, Supabase, local, etc.)

### Paso 3: Configurar credenciales

```bash
cp .env.example .env
```

Editar `.env` con los datos del cliente:

```env
# === KOMMO API ===
# URL de la cuenta (reemplazar subdominio)
KOMMO_BASE_URL=https://MI-SUBDOMINIO.kommo.com

# Token API v4
# Obtener: Kommo > Configuracion > Integraciones > Tu integracion > Token
KOMMO_ACCESS_TOKEN=eyJ0eXAiOiJKV1Q...

# === LOGIN PARA SCRAPING ===
# IMPORTANTE: Este usuario NO debe tener 2FA habilitado
KOMMO_LOGIN_EMAIL=scraper@empresa.com
KOMMO_LOGIN_PASSWORD=password123

# === POSTGRESQL ===
DATABASE_URL=postgresql://usuario:password@host:puerto/basededatos
```

### Paso 4: Descubrir la cuenta

```bash
python scripts/setup_account.py
```

Este script:
- Valida la conexion API
- Descubre todos los pipelines y etapas
- Mapea campos personalizados (leads + contactos)
- Lista usuarios y sus roles
- Identifica canales de chat (WhatsApp, Telegram, etc.)
- Detecta tags en uso
- Guarda todo en `config/kommo_mappings.json`

### Paso 5: Validar todo

```bash
python scripts/validate_setup.py
```

Verifica:
- `.env` con todas las variables
- Python dependencies instaladas
- Chrome headless funcional
- Kommo API conecta y responde
- Login Selenium sin 2FA funciona
- PostgreSQL conecta y tiene tablas

### Paso 6: Test inicial

```bash
# Scrapear 5 chats de ayer para validar
python scripts/scrape_v3.py --max-chats 5
```

### Paso 7: Scrape completo

```bash
# Ayer completo
python scripts/scrape_v3.py --date yesterday

# Rango de fechas
python scripts/scrape_v3.py --from-date 2026-03-24 --to-date 2026-03-31
```

---

## Informacion que se necesita del cliente

| Dato | Donde obtenerlo | Obligatorio |
|------|-----------------|-------------|
| **Subdominio Kommo** | La URL de su cuenta (ejemplo: `miempresa.kommo.com`) | Si |
| **Token API v4** | Kommo > Configuracion > Integraciones > Crear integracion privada > Generar token | Si |
| **Usuario sin 2FA** | Crear un usuario dedicado para el scraper SIN autenticacion de 2 factores | Si |
| **PostgreSQL URL** | Crear una base de datos (Railway, Supabase, local) | Si |
| **Scopes del token** | Minimo: `crm`, `files`, `notifications` | Si |

### Como crear el token API

1. Ir a `https://SUBDOMINIO.kommo.com/settings/widgets/`
2. Click en "Crear integracion" > "Integracion privada"
3. Nombre: "Chat Scrapper"
4. Permisos: marcar todo
5. Click en "Instalar"
6. Copiar el token de acceso

### Como crear usuario sin 2FA

1. Ir a `https://SUBDOMINIO.kommo.com/settings/users/`
2. Crear nuevo usuario: `scraper@empresa.com`
3. Rol: con acceso a Chats, Leads, Contactos
4. **Importante**: NO habilitar autenticacion de 2 factores
5. Este usuario sera usado exclusivamente por el scraper automatizado

---

## Comandos disponibles

```bash
# === SETUP ===
python scripts/setup_account.py         # Descubrir cuenta (pipelines, campos, usuarios)
python scripts/validate_setup.py        # Validar credenciales y conexiones
python scripts/extract_mappings.py      # Re-generar mapeos de la cuenta

# === SCRAPING DIARIO ===
python scripts/scrape_v3.py                         # Ayer (default)
python scripts/scrape_v3.py --date yesterday        # Ayer explicito
python scripts/scrape_v3.py --date current_day      # Hoy
python scripts/scrape_v3.py --max-chats 15          # Test con 15 chats

# === SCRAPING SEMANAL ===
python scripts/scrape_v3.py --date previous_week    # Semana pasada (7 scrapes individuales)
python scripts/scrape_v3.py --date current_week     # Semana actual

# === SCRAPING HISTORICO ===
python scripts/scrape_v3.py --from-date 2026-03-01 --to-date 2026-03-31

# === OPCIONES AVANZADAS ===
python scripts/scrape_v3.py --skip-enrich           # Sin enrichment API
python scripts/scrape_v3.py --skip-compile           # Sin compilar conversaciones
python scripts/scrape_v3.py --skip-stages            # Sin cambios de etapa
```

---

## Dashboard Web

La aplicacion web se deploya en Railway (o cualquier hosting que soporte Python/Flask).

### Deploy en Railway desde GitHub

1. Crear proyecto en Railway
2. Conectar repositorio GitHub
3. Agregar variable de entorno: `DATABASE_URL`
4. Railway detecta el `Procfile` y deploya automaticamente

### Paginas disponibles

| Pagina | URL | Descripcion |
|--------|-----|-------------|
| **Dashboard** | `/` | Stats generales, graficos por dia, tags, bots, agentes |
| **Chats** | `/chats` | Lista de chats con filtros por fecha y estado |
| **Chat Detail** | `/chat/{id}` | Conversacion completa con burbujas, lead info, links a Kommo |
| **Pendientes** | `/pending` | Chats donde el cliente escribio y NO hemos respondido |
| **Sin Respuesta** | `/no-reply` | Chats donde nosotros escribimos y el cliente NO respondio |
| **Etapas** | `/stages` | Historial de cambios de pipeline/stage |
| **Config** | `/settings` | Credenciales, validacion de token, configuracion |

---

## Base de datos (10 tablas)

| Tabla | Descripcion | Registros tipicos/dia |
|-------|-------------|----------------------|
| `kommo_contacts` | Nombre, telefono, email | ~100 |
| `kommo_leads` | Pipeline, stage, tags, responsable, custom fields (JSONB) | ~100 |
| `kommo_chats` | Analytics: bot/human, attention_status, interactions | ~100 |
| `kommo_messages` | Cada mensaje: author, is_bot, type, text, timestamp | ~1,000 |
| `kommo_stage_changes` | Cambios de etapa (pipeline movement) | ~200 |
| `kommo_events` | Todos los eventos (tags, links, creaciones) | ~1,000 |
| `kommo_conversations_compiled` | Conversacion JSON + texto plano por cliente (para LLM) | ~100 |
| `kommo_daily_metrics` | Metricas agregadas por dia | 1 |
| `kommo_scrape_errors` | Errores de scraping (no bloquea el proceso) | 0-5 |
| `kommo_no_reply_tracking` | Chats sin respuesta del cliente | ~50 |

### Campos clave de `kommo_chats`

| Campo | Valores posibles | Descripcion |
|-------|-----------------|-------------|
| `attention_status` | `attended`, `pending_response`, `bot_only`, `outbound_only` | Estado de atencion |
| `total_bot` | 0-N | Mensajes enviados por SalesBots |
| `total_human` | 0-N | Mensajes enviados por agentes humanos |
| `has_human_response` | true/false | Si un humano respondio |
| `human_takeover_at_msg` | 0-N | En que mensaje intervino el humano |
| `bot_names` | TEXT[] | Bots que participaron |
| `human_agents` | TEXT[] | Agentes humanos que participaron |
| `last_message_direction` | `IN`/`OUT` | Quien hablo ultimo |

---

## Estructura del proyecto

```
kommo-chat-scrapper/
├── scripts/
│   ├── setup_account.py        # Descubrir cuenta (PRIMER PASO)
│   ├── validate_setup.py       # Validar credenciales
│   ├── scrape_v3.py            # Scraper principal (produccion)
│   └── extract_mappings.py     # Re-generar mapeos
├── src/kommo/
│   ├── api_client.py           # Cliente REST API v4
│   ├── enrichment.py           # Enrichment con rate limiting (6 req/s)
│   ├── chat_scraper.py         # Modulo Selenium (clase reutilizable)
│   └── database.py             # PostgreSQL operations (10 tablas)
├── web/
│   ├── app.py                  # Flask web app
│   └── templates/              # HTML templates (Bootstrap 5 + Chart.js)
├── config/
│   └── kommo_mappings.json     # Mapeos de pipelines, campos, usuarios
├── output/                     # JSON output por ejecucion
├── .env.example                # Template de credenciales
├── Procfile                    # Para Railway deployment
├── CLAUDE.md                   # Contexto para Claude Code
├── CHANGELOG.md                # Historial de cambios
└── README.md                   # Este archivo
```

---

## Limitaciones conocidas

| Limitacion | Causa | Workaround |
|-----------|-------|------------|
| API no da mensajes de chat | Requiere scope "chats" + amojo HMAC | Selenium extrae mensajes del DOM |
| Selenium es lento (~15 chats/min) | Delays anti-ban + page load | Reducir delay a 1.5s, paralelizar en futuro |
| Virtual scroll no carga todo | Kommo recicla DOM elements | Acumulador global en JS + paciencia |
| Timestamps relativos | "Yesterday 14:11" vs "DD.MM.YYYY HH:MM" | Parser que detecta ambos formatos |
| Envios masivos inflan conteos | Bots envian miles de follow-ups | Filtrar por conversaciones con IN+OUT |

---

## Seguridad y anti-ban

- Delays aleatorios 1.5-2.5 segundos entre chats
- Rate limiting API: maximo 6 requests/segundo
- Retries automaticos con backoff exponencial
- Session de Chrome persistida en `/tmp/kommo_scraper_session`
- Errores se loguean sin detener el proceso
- UPSERT en todas las tablas (re-ejecutar no duplica)

---

## Licencia

Proyecto privado - Antigravity / Tamibot
