# 08. Guía de Despliegue para Modelos de IA (LLM Deployment)

Este framework está optimizado para ser orquestado y desplegado de forma autónoma por Asistentes Inteligentes de Código (Claude, Cursor, Github Copilot).

Si deseas que un LLM tome el control de este proyecto y lo instale en tu máquina, copia íntegramente el "Inception Prompt" expuesto a continuación y pégalo en tu asistente.

---

> [!TIP]
> **Prompt Maestro**: *Copia este bloque de texto, pégalo en tu asistente de Inteligencia Artificial y deja que él configure todo por ti.*

```text
[SYSTEM: ACTÚA COMO LEAD ENGINEER Y PYTHON ARCHITECT]

ACCIÓN INMEDIATA:
Me acabo de descargar el repositorio 'Kommo Chat Scraper Híbrido V4'. Necesito que orquestes un despliegue impecable siguiendo estas directivas secuenciales:

1. COMPRENSIÓN DOCUMENTAL
Lee el archivo `/CLAUDE.md` y `/docs/09_onboarding_guide.md`. Entiende la arquitectura "API-First + Selenium" híbrida. La base de datos funciona con lógica UPSERT y el scraper usa un acumulador virtual DOM para extraer mensajes de chat.

2. RECOLECCIÓN DE CREDENCIALES (ANTES DE TODO)
Pregúntame por mis 5 credenciales, una por una, explicando para qué sirve cada una:
- KOMMO_BASE_URL (URL de mi cuenta Kommo, ej: https://miempresa.kommo.com)
- KOMMO_ACCESS_TOKEN (Token API v4 de Kommo)
- KOMMO_LOGIN_EMAIL (Usuario sin 2FA para el scraper)
- KOMMO_LOGIN_PASSWORD (Contraseña del usuario)
- DATABASE_URL (PostgreSQL connection string)

ADVERTENCIA CRÍTICA: La cuenta KOMMO_LOGIN_EMAIL NO PUEDE tener verificación en dos pasos (2FA). Si la tiene, Selenium se congelará.

3. CONFIGURACIÓN
A) Crear `.env` con las credenciales
B) Ejecutar `pip install -r requirements.txt`

4. DISCOVERY DE CUENTA
Ejecutar `python scripts/setup_account.py` para mapear pipelines, campos, usuarios y canales.

5. VALIDACIÓN COMPLETA
Ejecutar `python scripts/health_check.py` y verificar que los 26 checks pasen.

6. DEPLOY WEB (ANTES DE SCRAPEAR)
Guíame para desplegar el dashboard web en Railway ANTES de empezar a scrapear datos.

7. TEST INICIAL
Ejecutar `python scripts/scrape_v3.py --max-chats 5` y verificar en la web que los datos se ven bien.

8. SCRAPE COMPLETO
Solo después de verificar que todo funciona, ejecutar `python scripts/scrape_v3.py --date yesterday`

9. VERIFICACIÓN FINAL
Ejecutar `python scripts/health_check.py` nuevamente para confirmar que todo está operativo.

Confírmame que entendiste y empieza pidiendo las credenciales.
```

---

## Agentes Disponibles (.claude/agents/)

Si usas Claude Code, el proyecto incluye agentes especializados:

| Agente | Cuándo usarlo |
|--------|--------------|
| `new-client-setup` | Onboarding de un nuevo cliente desde cero |
| `daily-scrape` | Scrape diario con pre/post validación |
| `scraper-validator` | Verificar calidad de datos después de un scrape |

### Cómo invocar un agente en Claude Code:
Los agentes se activan automáticamente cuando describes la tarea. Por ejemplo:
- "Setup a new Kommo client" → activa `new-client-setup`
- "Run the daily scrape with validation" → activa `daily-scrape`
- "Validate the last scrape results" → activa `scraper-validator`
