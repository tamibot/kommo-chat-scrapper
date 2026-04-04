<div align="center">
  <img src="https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge" alt="Status"/>
  <img src="https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/PostgreSQL-15-blue?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Kommo-CRM-green?style=for-the-badge" alt="Kommo CRM"/>
</div>

# Kommo Chat Scrapper V4 (Arquitectura Híbrida) 🤖📈

Bienvenido al *Framework Open Source* definitivo para análisis conversacional sobre Kommo CRM.

## 🎯 El Problema y Nuestro Objetivo Central
**El problema:** Kommo CRM es un software increíble para ventas, pero posee un enorme punto ciego analítico; **su API nativa es incapaz de exportar el contenido histórico de todos los chats**. Te permite hacer reportes básicos sobre "ventas cerradas" o montos monetarios, pero te ciega ante la verdad: *¿Tardó mucho el asesor comercial en contestar? ¿Los Bots comerciales están siendo ignorados? ¿Qué escribieron los clientes exactamente antes de abandonar?*

**Aquí entra nuestra herramienta:** El objetivo de este ecosistema es clonar automáticamente las líneas de tiempo conversacionales completas diariamente, someterlas a reglas de inteligencia de negocios, deducir indicadores cruzados, y trasladarlas a una base PostgreSQL de 10 relaciones limpia y utilizable, donde podrás descubrir exactamente la salud de tus canales de captación.

---

## 🏗️ ¿Qué vamos a conseguir? (Los Indicadores)
Al orquestar este Scraper, no consigues una aburrida sábana de mensajes inconexos. Consigues métricas vitales computadas sobre la marcha:
* **Estado de Atención:** ¿Este cliente fue respondido por un humano o quedó estancado tras las respuestas del Chatbot?
* **Radares Multi-Día:** Un sistema de alerta ("No-Reply") que identifica cuando le enviamos más de 5 SMS en ráfaga a un cliente comercial sin que nos conteste, pausando campañas erróneas.
* **Vectorización Masiva para IAs:** La tabla compila y acopla chats enteros y metadatos limpios, transformándolos a formato Texto Inteligible para orquestar RAG en modelos Grandes de Lenguaje (ChatGPT, Claude).

---

## 🛠️ Requisitos Críticos
Antes de operar, tu máquina precisará PostgreSQL, Google Chrome, Python 3.9+ configurados.

> [!CAUTION]  
> **REGLA ABSOLUTA DEL 2FA:** La cuenta de login asignada a Chrome en este proyecto (El `.env` con credenciales de email base) **JAMÁS DEBE TENER** activa la verificación de Dos-Pasos de autenticador SMS o celular. Chrome Headless entrará ciego; si requiere doble autenticador, simplemente chocará contra un muro congelando el proceso. 

Lee más instalando nuestro primer paso maestro: **[01_requirements_setup.md](docs/01_requirements_setup.md)**

---

## ⚙️ ¿Cómo funciona exactamente? (API + Selenium)

Nuestra arquitectura utiliza un flujo de pinza asimétrico para no consumir gigabytes de computación pesada:

1. **La Red Local (Webhooks y API):** Un bucle consulta de inmediato la API REST para atrapar el calor transaccional local ¿Quién conversó hoy? Obteniendo los Leads y el Huso Horario de las cuentas.
2. **La Evasión de la Memoria (Selenium Engine):** Hacemos una cacería exacta para leer la red de UI Kommo Web. Empleando inyecciones avanzadas de Javascript `window.__chatAccumulator` nuestro *WebDriver* guarda en RAM profunda y evita que interacciones visuales gigantes colapsen en las interfaces, categorizando desde audios detectados hasta textos extensos de Bot.
3. **Persistencia Multi-Reglas:** La base relacional de datos guarda tus registros usando la sentencia estricta de base `UPSERT`. Cero colmisiones, si reinicias Kommo Scrapper... las identidades sólo actualizarán datos volátiles asegurando control impecable.
4. **Visión Gráfica:** Módulos de Backend inyectan a Chart.Js la tabulación para tus gerentes.

```mermaid
%%{init: {'theme': 'dark'}}%%
flowchart LR
    A[Eventos API V4 (Horario Flexible)] -->|Deduce Quién habló| B(API Enriquecedora: GET ID y Etapas CRM)
    B -->|Lista Urls Confirmadas| C[Robótica Selenium JS Acumuladora]
    C -->|Parseo Molecular y Regex| D[(Base SQL Integrada y Contadores)]
    D -->|Export Pre-calculado| E{Web Tablero Gráfico Integrado}
```

---

## 📖 Directorio de Documentación (`/docs`)

Para gobernar a profundidad este *Workspace*, fraccionamos sus manuales en 8 directivas completísimas. Te sugerimos revisar primeramente el **[00_master_index.md](./docs/00_master_index.md)**. Allí entenderás integralmente que la infraestructura está segmentada lógicamente:
- Cómo funciona el Selenium y cómo evade la memoria HTML Kommo Web *(Doc: 04)*.
- Lógicas Relacionales de Data, Keys Primarias y Reportes *(Doc: 05, 06)*.

Si manejas agentes virtuales en tu ordenador que te ayudan a codear... el Documento **08** guarda un Master Prompt mágico de inicialización. 

---

## 🤝 Colaboradores (Comunidad y Pull Requests)
Esta arquitectura escala gracias al *Crowdsouncing*. Si encuentras métodos para simplificar las bases de inyecciones Regex, acoplar tableros más imponentes en Base Web o enlazar *WebHooks N8N* para tus pipelines, envía un Pull Request rotundo.

📩 Contacta a la Cúpula: **mvelascoo@tamibot.com**  
💬 Consultas Extensivas WhatsApp: **+51 995547475**
