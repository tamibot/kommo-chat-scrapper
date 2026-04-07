# Changelog

## [1.1.0] - 2026-04-06

### Scraper Robusto (scrape_v3.py)
- **Auto-restart del driver**: si Chrome headless se cuelga, se reinicia automaticamente y reloguea
- **Timeouts**: page_load=20s, script=15s para evitar cuelgues indefinidos
- **flush=True global**: output en tiempo real incluso en tareas background
- **Contador de restarts**: progreso muestra `restart:0` para monitorear estabilidad
- **3 retries por chat**: si falla la extraccion, reintenta hasta 3 veces

### Deteccion IN/OUT Corregida
- **Bug critico resuelto**: mensajes del cliente se confundian con mensajes de bot
- **Metodo correcto**: usa clase CSS `feed-note-incoming` del elemento `.feed-note`
- **Validado**: 0 mensajes IN marcados como bot, 0 WhatsApp Business como agent
- **Delivery status**: solo presente en mensajes OUT (Read/Delivered)
- **Bot detection**: solo aplica a mensajes OUT, patrones: SalesBot, TamiBot, generico "bot"
- **Sender types**: contact (IN), bot (OUT+bot), agent (OUT+humano), system (OUT+WhatsApp Business)

### Flujo Hibrido Events API + Selenium
- **Events API para discovery**: 15 paginas en ~20s (antes: 60s+ scroll Selenium)
- **Clasificacion automatica**: conversation/pending/follow_up/masivo
- **Origin/canal del Events API**: waba, instagram_business, tiktok_kommo, facebook
- **4x mas cobertura**: 291 targets vs 66 del Selenium "opened"
- **Timestamps Unix exactos**: coinciden 100% con Kommo UI (timezone Peru UTC-5)

### Analytics Engine (analytics.py)
- **parse_kommo_timestamp**: convierte "DD.MM.YYYY HH:MM" y "Yesterday" a datetime
- **Mensajes consecutivos**: cuenta OUT/IN al final de cada chat
- **Pending attention**: chats donde NOSOTROS debemos responder, con urgencia (high/medium/normal)
- **No-reply mejorado**: con origin, tags, responsable, ultimo mensaje del cliente
- **Lead summary**: metricas acumuladas por lead, hot lead detection por etapa de pipeline
- **Hot leads**: detecta automaticamente leads en etapas calientes (HORARIO INDICADO, VISITA MODO, etc.)

### Schema Expansion (13 tablas)
- `kommo_messages`: +origin, +parsed_at, +has_media, +media_description
- `kommo_chats`: +origin, +category, +responsible_user, +pipeline_name, +stage_name,
  +consecutive_out_end, +consecutive_in_end, +last_out/in_timestamp, +scrape_quality, +tags
- `kommo_leads`: +is_hot, +priority, +last_activity_date, +total_chats, +total_messages
- `kommo_no_reply_tracking`: +origin, +tags, +lead_name, +last_in_timestamp
- **NEW**: `kommo_pending_attention` - chats urgentes esperando nuestra respuesta
- **NEW**: `kommo_lead_summary` - metricas de lifecycle por lead con hot detection

### Dashboard Web
- **Graficos Chart.js**: Conversaciones por dia (stacked: Atendidos/Solo Bot/Sin Respuesta)
- **Donut de estado**: distribucion visual de atencion
- **Tags cloud**, Top Bots, Top Agentes rankings
- **URL dinamica**: `{{ kommo_base_url }}` en todos los templates (no hardcodeado)
- **Pendientes nuestros** (/pending): urgencia, responsable, tiempo sin responder
- **Filtros clickeables**: por status en la lista de chats
- **Date picker**: calendario + dropdown de fechas disponibles
- **Validacion de token**: boton con resultado en vivo en /settings

### Errores Corregidos
1. Bot detection en mensajes IN → ahora solo aplica a OUT
2. WhatsApp Business contado como agent → ahora es sender_type=system
3. `feed-note__talk-outgoing` era el footer de conversacion, no indicador de direccion
4. Timestamps Unix desfasados 5h → corregido con timezone-aware datetime
5. Enrichment.py retry infinito en 429 → max 3 retries
6. Events API limit=100 → aumentado a 250 (max de la API)
7. `settings.html` crash por `group.keys` colisionando con dict.keys()
8. Selenium background hang → auto-flush stdout + timeouts + auto-restart
9. `parse_chat_date_from_messages` usaba fecha del primer msg → ahora usa fecha del filtro
10. `isOut` variable undefined en JS → corregido a `dir === 'OUT'`

## [1.0.0] - 2026-04-03

### Sistema inicial completo
- Scraper v3 con Selenium headless
- Dashboard web Flask en Railway
- 10 tablas PostgreSQL
- Deteccion de Bot vs Humano
- API enrichment (leads, contacts, tags, stages)
- Setup wizard y validacion de credenciales
