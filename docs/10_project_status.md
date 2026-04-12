# 10. Estado del Proyecto y Donde Nos Quedamos

**Última actualización:** 2026-04-06

---

## Estado General: PRODUCCIÓN ✅

El sistema está operativo y scrapeando datos diariamente.

---

## Datos en la Base de Datos

| Fecha | Chats | Mensajes | Con Humano | Solo Bot | Scrapeado |
|-------|-------|----------|-----------|----------|-----------|
| 2026-03-29 | 110 | 2,251 | 51 | 56 | ✅ |
| 2026-03-30 | 331 | 12,118 | 257 | 41 | ✅ |
| 2026-03-31 | 338 | 11,383 | 232 | 42 | ✅ |
| 2026-04-01 | - | - | - | - | ❌ Pendiente |
| 2026-04-02 | 10 | 265 | 4 | 6 | ⚠️ Solo 10 chats |
| 2026-04-03 | 10 | 224 | 6 | 4 | ⚠️ Solo 10 chats |
| 2026-04-04 | 178 | 6,629 | 147 | 29 | ✅ |
| 2026-04-05 | 79 | 1,679 | 37 | 37 | ✅ |
| **Total** | **1,056** | **34,549** | | | |

### Pendientes de scraping:
- **Apr 1**: no scrapeado con la lógica corregida
- **Apr 2**: solo 10 chats (necesita full scrape)
- **Apr 3**: solo 10 chats (necesita full scrape)
- **Mar 24-28**: días con envíos masivos, no scrapeados aún

### Para completar un día:
```bash
python scripts/scrape_v3.py --from-date 2026-04-01 --to-date 2026-04-01
```

---

## Registros en tablas

| Tabla | Registros | Descripción |
|-------|-----------|-------------|
| kommo_chats | 1,056 | Resumen por chat/día |
| kommo_messages | 34,549 | Cada mensaje individual |
| kommo_leads | 939 | Leads enriquecidos con pipeline, tags |
| kommo_contacts | 927 | Contactos con teléfono, email |
| kommo_stage_changes | 1,738 | Historial de cambios de etapa |
| kommo_events | 6,817 | Eventos de la API |
| kommo_conversations_compiled | 416 | Conversaciones compiladas para LLM |
| kommo_pending_attention | 304 | Chats donde NOSOTROS debemos responder |
| kommo_lead_summary | 828 | Métricas agregadas por lead |
| kommo_no_reply_tracking | 436 | Chats sin respuesta del CLIENTE |
| kommo_daily_metrics | 7 | Métricas diarias agregadas |
| kommo_scrape_errors | 0 | Errores de scraping |
| kommo_app_settings | 9 | Configuración de la app web |

---

## Bugs Corregidos (v1.1)

| # | Bug | Estado |
|---|-----|--------|
| 1 | Bot detection en mensajes IN (cliente marcado como bot) | ✅ Corregido |
| 2 | WhatsApp Business contado como agente humano | ✅ Corregido |
| 3 | `feed-note__talk-outgoing` era footer, no dirección | ✅ Corregido |
| 4 | Timestamps Unix desfasados 5h por timezone | ✅ Corregido |
| 5 | Enrichment retry infinito en 429 | ✅ Corregido |
| 6 | Events API limit=100 (max es 250) | ✅ Corregido |
| 7 | Settings page crash (`group.keys`) | ✅ Corregido |
| 8 | Selenium background hang sin output | ✅ Corregido |
| 9 | `isOut` variable undefined en JS | ✅ Corregido |
| 10 | SUBDOMAIN hardcodeado | ✅ Corregido (lee de .env) |

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────┐
│                    FLUJO DIARIO                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. Events API ──────────────────────────> Targets   │
│     (incoming_chat_message,                         │
│      outgoing_chat_message)                         │
│     Clasifica: conversation/pending/follow_up/masivo│
│     Obtiene: talk_id, lead_id, contact_id, origin   │
│                                                     │
│  2. Selenium Headless ───────────────────> Mensajes  │
│     Navega a cada chat por URL directa              │
│     Expande "Más X de Y"                            │
│     Extrae via JS: autor, dirección, timestamp,     │
│     tipo de media, texto                            │
│     Detecta: SalesBot/TamiBot/agent/system/contact  │
│                                                     │
│  3. API Enrichment ──────────────────────> Contexto  │
│     Batch GET leads (50/req) con contacts           │
│     Stage changes por fecha                         │
│     Tags, custom fields, responsable                │
│                                                     │
│  4. PostgreSQL ──────────────────────────> Storage    │
│     13 tablas con UPSERT (no duplica)               │
│     Analytics: pending, no-reply, lead summary      │
│     Conversaciones compiladas para LLM              │
│                                                     │
│  5. Flask Dashboard ─────────────────────> Web       │
│     Gráficos Chart.js                               │
│     Filtros clickeables por status/fecha            │
│     Links directos a Kommo                          │
│     Deploy automático en Railway                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Credenciales Necesarias (Proper Tamibot)

| Variable | Valor | Estado |
|----------|-------|--------|
| KOMMO_BASE_URL | https://propertamibotcom.kommo.com | ✅ |
| KOMMO_ACCESS_TOKEN | eyJ0eXA... (1082 chars) | ✅ Vigente |
| KOMMO_LOGIN_EMAIL | soporte.corretaje@proper.com.pe | ✅ Sin 2FA |
| KOMMO_LOGIN_PASSWORD | (en .env) | ✅ |
| DATABASE_URL | Railway PostgreSQL | ✅ Conectado |

---

## Web Dashboard

- **URL**: https://kommo-chat-scrapper-kommo-scrapper.up.railway.app
- **Estado**: ✅ Operativo
- **Páginas**: Dashboard, Chats, Chat Detail, Pendientes, Sin Respuesta, Etapas, Config

---

## Próximos Pasos Sugeridos

1. **Completar scraping faltante**: Apr 1, 2 (full), 3 (full)
2. **Scraping diario automatizado**: Configurar cron job para ejecutar cada día
3. **Mejorar Top Agentes**: Cruzar con canales de WhatsApp Business para identificar asesores reales
4. **Batch insert**: Optimizar inserts a DB (actualmente uno por uno, lento para 10k+ mensajes)
5. **Análisis LLM**: Usar conversaciones compiladas para clasificar calidad de atención
6. **Alertas**: Notificar cuando hay chats pendientes de alta urgencia
