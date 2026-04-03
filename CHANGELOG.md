# Changelog

## [1.0.0] - 2026-04-03

### Sistema completo
- Scraper v3 production-grade con Selenium headless
- Dashboard web Flask desplegado en Railway
- 10 tablas PostgreSQL con analytics completos
- Deteccion automatica de Bot vs Humano vs Contacto

### Scraping
- Login automatico sin 2FA via Selenium
- Filtros Unix timestamp por dia (preciso)
- Virtual scroll con acumulador global para cargar todos los chats
- Expansion de mensajes colapsados ("Mas X de Y", hasta 5 rondas)
- Anti-ban: delays aleatorios 1.5-2.5s entre chats
- Retries automaticos con error recovery (non-blocking)
- Soporte: yesterday, current_day, previous_week, current_week, date ranges

### API Enrichment
- Batch fetch leads (50 por request) con tags, custom fields, pipeline
- Batch fetch contacts (50 por request) con telefono y email
- Stage changes por fecha via events API (lead_status_changed)
- All events: tags, links, creaciones, talk_created
- Rate limiting: max 6 req/s (safe under 7/s limit)

### Analytics
- Deteccion de 10+ SalesBots por nombre del author
- Conteo de interacciones (cambios de direccion IN/OUT)
- Punto de takeover humano (en que mensaje interviene el agente)
- Estado de atencion: attended, pending_response, bot_only, outbound_only
- Deteccion de chats sin respuesta del cliente
- Deteccion de pendientes nuestros (cliente escribio, no respondimos)
- Tipo de media: image, video, file, audio, pdf, sticker, location
- Tags del lead (RENTAS, stop_ai, etc.)

### Dashboard Web
- Graficos Chart.js: mensajes por dia (stacked), donut de status
- Tags cloud con conteos
- Top Bots y Top Agentes rankings
- Distribucion de pipelines
- Chats con filtros clickeables por status (Atendido/Pendiente/Bot Only)
- Date picker + dropdown de fechas
- Chat detail con burbujas estilo WhatsApp
- Links directos a Kommo (lead + chat)
- Pagina de Pendientes Nuestros
- Pagina de Sin Respuesta del Cliente
- Historial de cambios de etapa
- Settings con validacion de token API
- Health check endpoint

### Setup y Documentacion
- Script de discovery de cuenta (pipelines, campos, usuarios, canales, tags)
- Script de validacion de setup (6 checks)
- README completo con guia de implementacion para nuevos clientes
- CLAUDE.md con contexto tecnico completo
- .env.example con todas las variables documentadas

### Descubrimientos
- API v4 NO expone contenido de mensajes (requiere amojo API con HMAC-SHA1)
- El endpoint /talks/{id}/messages requiere scope "chats" adicional
- Selenium "opened" muestra ~95 chats/dia vs 300+ conversaciones reales
- Events API revela envios masivos (4,000+ leads en dias de campana)
- El subdomain debe ser SUBDOMINIO.kommo.com (no api-c.kommo.com)
- Timestamps en UI: "Yesterday HH:MM" para ayer, "DD.MM.YYYY HH:MM" para mas antiguos
