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
Lee el archivo `/docs/00_master_index.md`. Entiende la arquitectura "API-First" vs "Selenium Edge". Toma consciencia de que la base de datos funciona con lógica UPSERT para evitar duplicados y el uso de un Virtual DOM de bypass para la extracción de mensajería analítica.

2. MATRIZ DE REQUISITOS (SETUP INTELIGENTE)
Lee cuidadosamente `/docs/01_requirements_setup.md` y prepara los comandos de entorno (Instalación de requisitos pip y brew). 
IMPORTANTE: El código no tiene variables quemadas (es 100% agnóstico). Pregúntame, sin asumir nada, por mis 5 credenciales exactas para tu `.env`: 
- KOMMO_BASE_URL (URL base de mi empresa).
- KOMMO_ACCESS_TOKEN.
- KOMMO_LOGIN_EMAIL.
- KOMMO_LOGIN_PASSWORD.
- DATABASE_URL (URI de acceso a mi PostgreSQL).

Advierte en tu respuesta que mi cuenta KOMMO_LOGIN_EMAIL NO PUEDE tener activa la verificación en dos pasos (2FA), de lo contrario Selenium fallará.

3. ORQUESTACIÓN DE ARRANQUE
Una vez me ayudes a fijar los secretos en un `.env` válido y tengas listo Python:
A) Invoca primeramente el script `python3 scripts/extract_mappings.py` para mapear dinámicamente las etapas e IDs de mi cuenta.
B) Dispara la extracción principal ejecutando `python3 scripts/scrape_v3.py --date yesterday`.

Confírmame que entendiste y pregúntame por las credenciales.
```
