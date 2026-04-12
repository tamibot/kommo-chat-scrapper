# 09. Guía de Onboarding - Paso a Paso

Esta guía te lleva de **cero a producción** con el Kommo Chat Scrapper. Sigue cada paso en orden. No avances al siguiente hasta completar el actual.

---

## Fase 1: Preparar las credenciales (antes de todo)

Necesitas reunir **4 credenciales** antes de tocar código. Aquí te explicamos cada una.

### 1.1 Token API de Kommo

**¿Para qué sirve?** El token permite leer datos de tu CRM: leads, contactos, pipelines, etapas, tags, eventos. Sin este token no podemos saber quién conversó ni enriquecer los datos.

**Cómo obtenerlo:**
1. Entra a tu cuenta Kommo: `https://TU-SUBDOMINIO.kommo.com/settings/widgets/`
2. Click en **"+ Crear integración"** → **"Integración privada"**
3. Nombre: `Chat Scrapper` (o como prefieras)
4. En permisos, marca **todo**: CRM, Files, Notifications
5. Click **"Instalar"**
6. Copia el **Token de acceso** (es un texto largo que empieza con `eyJ0eXA...`)
7. Guárdalo en un lugar seguro

**Dato importante:** El token tiene fecha de expiración. Si caduca, deberás generar uno nuevo desde la misma integración.

### 1.2 Usuario sin 2FA para el Scraper

**¿Para qué sirve?** El scraper usa Selenium (un navegador automático) para entrar a la vista de chats de Kommo y leer los mensajes. Necesita un usuario que pueda hacer login sin que le pida un código por SMS o email.

**¿Por qué no puede tener 2FA?** Porque el navegador automático no puede leer un SMS ni abrir un email para copiar el código. Si tiene 2FA activado, el login se congela.

**Cómo crearlo:**
1. Ve a `https://TU-SUBDOMINIO.kommo.com/settings/users/`
2. Click en **"+ Agregar usuario"**
3. Datos sugeridos:
   - Nombre: `Scraper Bot` (o algo descriptivo)
   - Email: `scraper@tu-empresa.com`
   - Rol: **Administrador** (necesita acceso a Chats, Leads, Contactos)
4. **IMPORTANTE**: NO actives la verificación de 2 factores
5. Establece una contraseña segura
6. Guarda el email y contraseña

**Si te aparece reCAPTCHA al hacer login:** Esto pasa cuando hay muchos intentos de login automático seguidos. Solución:
1. Borra la sesión: `rm -rf /tmp/kommo_scraper_session`
2. Cambia la contraseña del usuario en Kommo
3. Espera 5 minutos e intenta de nuevo

### 1.3 Base de datos PostgreSQL (Railway)

**¿Para qué sirve?** Aquí se guardan todos los datos: mensajes, leads, contactos, métricas, conversaciones compiladas. Es la "memoria" del sistema.

**Cómo crearla en Railway (recomendado):**
1. Ve a [railway.com](https://railway.com) y crea una cuenta (puedes usar GitHub)
2. En el dashboard, click **"New Project"** → **"Provision PostgreSQL"**
3. Una vez creada, click en el servicio de PostgreSQL
4. Ve a la pestaña **"Variables"**
5. Copia el valor de `DATABASE_URL` (formato: `postgresql://postgres:XXX@host:port/railway`)
6. Guárdalo

**Alternativas:** También puedes usar Supabase, Render, o una DB local.

### 1.4 Token de Railway (opcional, para deploy automático)

**¿Para qué sirve?** Permite que el dashboard web se despliegue automáticamente desde GitHub cada vez que hagas un push.

**Cómo obtenerlo:**
1. En Railway, ve a **Account Settings** → **Tokens**
2. Click **"Create Token"**
3. Nombre: `kommo-scrapper`
4. Copia el token

---

## Fase 2: Clonar e instalar

Una vez que tengas las 4 credenciales, procede:

```bash
# Clonar el repositorio
git clone https://github.com/tamibot/kommo-chat-scrapper.git
cd kommo-chat-scrapper

# Instalar dependencias
pip install -r requirements.txt
```

**Dependencias que se instalan:**
- `selenium` - Navegador automático para extraer mensajes de chat
- `psycopg2-binary` - Conexión a PostgreSQL
- `flask` - Dashboard web
- `gunicorn` - Servidor web para producción
- `python-dotenv` - Lee variables de entorno desde .env

---

## Fase 3: Configurar credenciales

```bash
cp .env.example .env
```

Abre `.env` con tu editor y llena cada campo:

```env
# La URL de tu cuenta (reemplaza TU-SUBDOMINIO)
KOMMO_BASE_URL=https://TU-SUBDOMINIO.kommo.com

# El token que copiaste en el paso 1.1
KOMMO_ACCESS_TOKEN=eyJ0eXAiOiJKV1Q...

# El usuario sin 2FA del paso 1.2
KOMMO_LOGIN_EMAIL=scraper@tu-empresa.com
KOMMO_LOGIN_PASSWORD=tu-password-seguro

# La URL de PostgreSQL del paso 1.3
DATABASE_URL=postgresql://postgres:XXX@host:port/railway
```

---

## Fase 4: Descubrir la cuenta

Este paso mapea automáticamente toda la estructura de tu CRM:

```bash
python scripts/setup_account.py
```

**¿Qué hace?** Conecta a la API de Kommo y descubre:
- Todos los pipelines y sus etapas
- Campos personalizados de leads y contactos
- Usuarios y sus roles
- Canales de chat (WhatsApp, Instagram, TikTok, Facebook)
- Tags en uso

Todo se guarda en `config/kommo_mappings.json`.

---

## Fase 5: Validar que todo funcione

```bash
python scripts/validate_setup.py
```

Esto ejecuta 6 verificaciones:
1. `.env` tiene todas las variables
2. Dependencias Python instaladas
3. Chrome headless funcional
4. API de Kommo conecta y responde
5. Login Selenium sin 2FA funciona
6. PostgreSQL conecta y tiene tablas

**Si algún check falla**, revisa el mensaje de error y corrige antes de continuar.

---

## Fase 6: Desplegar el dashboard web (ANTES de scrapear)

Es importante tener la web funcionando PRIMERO para poder visualizar los datos conforme se van scrapeando.

### Opción A: Deploy desde Railway (recomendado)

1. En Railway, click **"New Project"** → **"Deploy from GitHub Repo"**
2. Selecciona el repositorio `kommo-chat-scrapper`
3. Railway detectará el `Procfile` automáticamente
4. Ve a **Variables** del nuevo servicio y agrega:
   ```
   DATABASE_URL = (la misma URL de tu PostgreSQL)
   ```
5. Espera ~2 minutos a que termine el deploy
6. Railway te dará una URL pública (ej: `tu-app.up.railway.app`)
7. Abre la URL y verifica que ves el dashboard

### Verificar que funciona:
- Ve a `tu-app.up.railway.app/api/health` → debe mostrar JSON con `"status": "connected"`
- Ve a `tu-app.up.railway.app/settings` → llena el token API y valida

---

## Fase 7: Test inicial del scraper

Ahora sí, prueba el scraper con pocos chats:

```bash
# Test con 5 chats de ayer
python scripts/scrape_v3.py --max-chats 5
```

**¿Qué hace?**
1. Busca eventos de chat del día anterior via API
2. Clasifica los leads: conversación real, pendiente, follow-up, masivo
3. Abre Selenium y navega a cada chat
4. Extrae mensajes: quién escribió, cuándo, qué dijo, si fue bot o humano
5. Enriquece con datos del lead: pipeline, etapa, tags, responsable
6. Guarda todo en PostgreSQL
7. Compila conversaciones para análisis con IA

**Verificar en la web:** Después del test, ve a tu dashboard web y revisa:
- `/chats` → deben aparecer 5 chats
- Click en uno → debe mostrar la conversación completa
- `/` (dashboard) → deben aparecer las métricas

---

## Fase 8: Scrape completo del día anterior

Si el test fue exitoso:

```bash
python scripts/scrape_v3.py --date yesterday
```

Esto scrapeará TODOS los chats con actividad de ayer (normalmente 50-300 dependiendo del volumen).

---

## Fase 9: Verificación final

Checklist antes de considerar el sistema "en producción":

- [ ] Dashboard web accesible y mostrando datos
- [ ] Chats se ven con mensajes IN (cliente) y OUT (bot/agente)
- [ ] Bot detection funciona (TamiBot, SalesBot marcados correctamente)
- [ ] Lead info muestra pipeline, etapa, tags, responsable
- [ ] Links "Ver en Kommo" funcionan
- [ ] Página "Pendientes" muestra chats que necesitan respuesta
- [ ] Página "Sin Respuesta" muestra leads sin reply del cliente
- [ ] `/api/health` muestra todas las tablas con datos

---

## Comandos útiles después del setup

```bash
# Scrape de ayer (ejecutar diariamente)
python scripts/scrape_v3.py --date yesterday

# Scrape de hoy
python scripts/scrape_v3.py --date current_day

# Scrape de toda la semana pasada (7 días individuales)
python scripts/scrape_v3.py --date previous_week

# Scrape de un rango de fechas
python scripts/scrape_v3.py --from-date 2026-03-24 --to-date 2026-03-31

# Re-descubrir la cuenta (si cambian pipelines/campos)
python scripts/setup_account.py

# Validar que todo sigue funcionando
python scripts/validate_setup.py
```

---

## Troubleshooting

### reCAPTCHA al hacer login
```bash
rm -rf /tmp/kommo_scraper_session
# Cambia la contraseña del usuario en Kommo
# Espera 5 minutos
python scripts/scrape_v3.py --max-chats 1  # test
```

### Chrome headless se cuelga
El scraper tiene auto-restart. Si persiste:
```bash
pkill -f chromedriver
pkill -f "kommo_scraper"
# Espera 10 segundos y reintenta
```

### Token API expirado
1. Ve a Kommo > Configuración > Integraciones
2. Abre tu integración privada
3. Genera un nuevo token
4. Actualiza `.env` con el nuevo token
5. Si tienes Railway, actualiza también en `/settings` de la web

### Base de datos llena / lenta
Los inserts son individuales (no batch). Para grandes volúmenes:
- Scrape día por día, no semanas completas
- Los días con envíos masivos (4000+ leads) toman más tiempo
