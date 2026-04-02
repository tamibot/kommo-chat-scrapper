# Kommo Chat Scrapper

> Herramienta automatizada para extraer, enriquecer y analizar conversaciones de chat desde Kommo CRM. Diseñada para ejecutarse con **Claude Code** como asistente de configuración.

---

## Que hace este proyecto?

Este scraper extrae **todas las conversaciones de WhatsApp** desde Kommo CRM de forma automatizada:

1. **Scraping** - Selenium headless navega la vista de chats y extrae cada mensaje
2. **Enrichment** - La API de Kommo agrega datos del lead, contacto, pipeline, tags
3. **Analytics** - Detecta bots vs humanos, tiempo de atención, chats sin respuesta
4. **Storage** - PostgreSQL con 10 tablas optimizadas
5. **LLM Ready** - Conversaciones compiladas en texto plano por cliente

---

## Arquitectura

```mermaid
graph TB
    subgraph "1. Scraping (Selenium)"
        A[Login Kommo] --> B[Cargar lista de chats]
        B --> C[Scroll virtual para todos los chats]
        C --> D[Navegar a cada chat]
        D --> E[Expandir 'Más X de Y']
        E --> F[Extraer mensajes via JS]
    end

    subgraph "2. API Enrichment"
        G[Batch fetch leads] --> H[Batch fetch contacts]
        H --> I[Fetch tags y custom fields]
        I --> J[Fetch stage changes events]
        J --> K[Fetch all events del dia]
    end

    subgraph "3. Processing"
        L[Detectar Bot vs Humano]
        M[Calcular interacciones]
        N[Detectar chats sin respuesta]
        O[Compilar conversacion por cliente]
    end

    subgraph "4. Storage (PostgreSQL)"
        P[(kommo_contacts)]
        Q[(kommo_leads)]
        R[(kommo_chats)]
        S[(kommo_messages)]
        T[(kommo_events)]
        U[(kommo_stage_changes)]
        V[(kommo_conversations_compiled)]
        W[(kommo_daily_metrics)]
    end

    F --> L
    L --> M --> N --> O
    K --> T
    J --> U
    O --> V
    G --> Q
    H --> P
    F --> S
    N --> R
    R --> W
```

## Flujo de datos por mensaje

```mermaid
flowchart LR
    A[Mensaje en Kommo] --> B{Es saliente?}
    B -->|Si| C{Author contiene 'SalesBot'?}
    C -->|Si| D[sender_type: bot]
    C -->|No| E[sender_type: agent]
    B -->|No| F[sender_type: contact]

    D --> G{Tiene media?}
    E --> G
    F --> G
    G -->|Imagen| H[type: image]
    G -->|Video| I[type: video]
    G -->|Archivo| J[type: file]
    G -->|Audio| K[type: audio]
    G -->|Texto| L[type: text]
```

---

## Requisitos previos

| Herramienta | Version | Para que |
|-------------|---------|----------|
| Python | 3.9+ | Runtime principal |
| Google Chrome | 120+ | Selenium headless |
| PostgreSQL | 13+ | Base de datos (puede ser Railway, Supabase, local) |
| pip | 21+ | Gestor de paquetes |

## Instalacion rapida

```bash
# 1. Clonar
git clone <repo-url>
cd kommo_chat_scrapper

# 2. Instalar dependencias Python
pip install selenium psycopg2-binary

# 3. Configurar credenciales
cp .env.example .env
# Editar .env con tus datos (ver seccion Credenciales)

# 4. Validar que todo funciona
python scripts/validate_setup.py

# 5. Ejecutar (test con 5 chats)
python scripts/scrape_v3.py --max-chats 5

# 6. Scrape completo de ayer
python scripts/scrape_v3.py --date yesterday
```

---

## Credenciales necesarias

Edita el archivo `.env` con estos valores:

### Kommo CRM

| Variable | Descripcion | Donde obtenerla |
|----------|-------------|-----------------|
| `KOMMO_BASE_URL` | URL de tu cuenta Kommo | `https://TU-SUBDOMINIO.kommo.com` |
| `KOMMO_ACCESS_TOKEN` | Token API v4 | Kommo > Configuracion > Integraciones > Tu integracion > Token |
| `KOMMO_LOGIN_EMAIL` | Email de usuario **sin 2FA** | Un usuario con acceso a chats, sin verificacion de 2 pasos |
| `KOMMO_LOGIN_PASSWORD` | Password del usuario | |

### PostgreSQL

| Variable | Descripcion |
|----------|-------------|
| `DATABASE_URL` | Connection string completo: `postgresql://user:pass@host:port/dbname` |

### Como crear un usuario sin 2FA en Kommo

1. Ir a Configuracion > Usuarios
2. Crear nuevo usuario con rol que tenga acceso a Chats
3. Asegurarse de que NO tenga habilitada la autenticacion de 2 factores
4. Este usuario sera usado exclusivamente por el scraper

---

## Comandos disponibles

```bash
# Scrape de ayer (el mas comun)
python scripts/scrape_v3.py --date yesterday

# Scrape de hoy
python scripts/scrape_v3.py --date current_day

# Test rapido (15 chats)
python scripts/scrape_v3.py --max-chats 15

# Sin enrichment de API (solo scraping)
python scripts/scrape_v3.py --skip-enrich

# Historico: rango de fechas
python scripts/scrape_v3.py --from-date 2026-03-25 --to-date 2026-03-31

# Regenerar mapeos de cuenta
python scripts/extract_mappings.py

# Validar setup
python scripts/validate_setup.py
```

---

## Base de datos (10 tablas)

```mermaid
erDiagram
    kommo_contacts {
        bigint contact_id PK
        text name
        text phone
        text email
    }
    kommo_leads {
        bigint lead_id PK
        bigint contact_id FK
        text pipeline_name
        text stage_name
        text responsible_user_name
        text[] tags
        jsonb custom_fields
    }
    kommo_chats {
        serial id PK
        bigint talk_id
        bigint lead_id FK
        date chat_date
        int total_messages
        int total_bot
        int total_human
        text attention_status
        text[] bot_names
        text[] human_agents
    }
    kommo_messages {
        serial id PK
        bigint talk_id
        bigint lead_id FK
        text direction
        text sender_type
        text author
        boolean is_bot
        text bot_name
        text msg_type
        text msg_text
        text msg_timestamp
    }
    kommo_stage_changes {
        serial id PK
        bigint lead_id FK
        text old_stage_name
        text new_stage_name
        timestamp changed_at
    }
    kommo_events {
        serial id PK
        text event_type
        bigint entity_id
        jsonb value_after
        timestamp created_at
    }
    kommo_conversations_compiled {
        serial id PK
        bigint lead_id FK
        jsonb conversation_json
        text conversation_text
        text attention_status
    }
    kommo_daily_metrics {
        serial id PK
        date metric_date UK
        int total_chats
        int total_bot
        int total_human
        int chats_with_human
    }
    kommo_scrape_errors {
        serial id PK
        bigint talk_id
        text error_type
        text error_message
    }
    kommo_no_reply_tracking {
        serial id PK
        bigint lead_id UK
        text contact_name
        text contact_phone
        int consecutive_out
        text status
    }

    kommo_contacts ||--o{ kommo_leads : "tiene"
    kommo_leads ||--o{ kommo_chats : "tiene"
    kommo_leads ||--o{ kommo_messages : "tiene"
    kommo_leads ||--o{ kommo_stage_changes : "tiene"
    kommo_leads ||--o{ kommo_conversations_compiled : "tiene"
```

### Campos clave de `kommo_chats`

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `attention_status` | text | `attended`, `pending_response`, `bot_only`, `outbound_only` |
| `total_bot` | int | Mensajes enviados por SalesBots |
| `total_human` | int | Mensajes enviados por agentes humanos |
| `has_human_response` | bool | Si un humano respondio en este chat |
| `human_takeover_at_msg` | int | En que mensaje # intervino el humano |
| `bot_names` | text[] | Lista de bots que participaron |
| `human_agents` | text[] | Lista de agentes humanos que participaron |

---

## Estructura del proyecto

```
kommo_chat_scrapper/
├── scripts/
│   ├── scrape_v3.py            # Scraper principal (produccion)
│   ├── extract_mappings.py     # Extrae pipelines, campos, usuarios
│   └── validate_setup.py       # Valida credenciales y conexiones
├── src/
│   └── kommo/
│       ├── api_client.py       # Cliente REST API v4
│       ├── enrichment.py       # Enrichment con rate limiting
│       └── database.py         # PostgreSQL operations
├── config/
│   └── kommo_mappings.json     # Mapeos de pipelines, stages, users
├── output/                     # JSON output por ejecucion
├── .env.example                # Template de credenciales
├── CLAUDE.md                   # Contexto para Claude Code
├── CHANGELOG.md                # Historial de cambios
└── README.md                   # Este archivo
```

---

## Metricas que extrae

| Metrica | Fuente | Descripcion |
|---------|--------|-------------|
| Bot vs Humano | Scraping | Detecta SalesBot por nombre del author |
| Interacciones | Scraping | Cambios de direccion IN/OUT en la conversacion |
| Tiempo primer contacto | Scraping | Timestamp del primer mensaje entrante |
| Tiempo respuesta humana | Scraping | Timestamp del primer mensaje de agente |
| Chats sin respuesta | Analytics | Leads con multiples OUT sin IN de vuelta |
| Cambios de etapa | API Events | Movimiento de leads entre stages del pipeline |
| Tags aplicados | API Events | Tags como "RENTAS", "stop_ai" |
| Tipo de media | Scraping | image, video, file, audio, pdf, sticker |

---

## Anti-ban y robustez

- Delays aleatorios 2-4 segundos entre cada chat
- Rate limiting de API: maximo 6 requests/segundo
- Retries automaticos en caso de error (2 intentos)
- Errores se loguean en `kommo_scrape_errors` sin detener el proceso
- UPSERT en todas las tablas (re-ejecutar no duplica datos)
- Session de Chrome persistida en `/tmp/kommo_scraper_session`

---

## Licencia

Proyecto privado - Antigravity
