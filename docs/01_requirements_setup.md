# 01. Montaje, Requisitos y Configuración (Setup)

Este documento instruye sobre las reglas vitales que deben asentarse a nivel de Servidor y Ecosistema Kommo antes de gatillar la primera petición API.

---

## 🛠 Entorno de Máquina y Dependencias (Locales/Cloud)
El Framework en sí mismo empuja operaciones robustas I/O, por lo que requiere una lista mínima pero inquebrantable de paquetes Base, dictaminados del archivo maestro `requirements.txt`:

1. **Core de Python**: Requiere *Python 3.9+* o superior (para compatibilidad estricta con utilidades asíncronas de fechas y `zoneinfo`).
2. **Motores Nativos Base Terrestres**:
   - Dependiendo de tu Servidor (Ubuntu/Mac), sugerimos instalar gestores base: `brew install postgresql` e integrar colas como Redis.
   - En entornos Containerizados (Docker / Pterodactyl), usa imágenes nativas `postgres:15-alpine` y monta volúmenes persistentes.
3. **El Navío Virtual (Chrome & Selenium)**:
   - Fundamental: Poseer una distribución de **Google Chrome** nativa en el OS y su binario hermano simbiótico **ChromeDriver** montado en el PATH global para evitar fallos de instanciación WebDriver.

```mermaid
%%{init: {'theme': 'dark'}}%%
graph TD
    subgraph OS[Operating System]
        Py[Python 3.9+]
        DB[(PostgreSQL 15)]
        CH[Google Chrome + WebDriver]
    end
    
    subgraph Repo[Cloned Repo]
        Req[requirements.txt]
        Env[.env Archivo de Variables]
    end
    
    Req -.->|pip install| Py
    Env -.->|Authentication| OS
```

---

## ⚠️ Perfil de Usuario de Acceso (La Regla del No-2FA)
Kommo proscribe el Scraping sin piedad. El usuario provisto será tu intermediario.

> [!CAUTION]
> **REGLA ABSOLUTA DEL 2FA:** La cuenta elegida y cargada en la variable `KOMMO_LOGIN_EMAIL` JAMÁS DEBE tener activa la verificación en dos pasos (SMS/Google Authenticator). Si Chrome trata de ingresar mediante tu Script en un Servidor CentOS a media noche y aparece un candado "Envía el código SMS", el Scrapper morirá silenciosamente bajo Timeout y crasheará.

**Procedimiento de Sanidad:** Crea en Kommo un Rol "Administrador Bot". Úsalo solo para este scraper. Asignale una clave alfanumérica gigante. Si ves una caída local con código de falla Cache/ReCAPTCHA constante, simplemente entra manual a ese correo desde tu PC, cámbiale el Password en tu Perfil de Kommo y actualiza tu `.env`. El bloqueo de Google se esfumará al instante.

---

## 🔐 Configuración Dinámica Multi-Sitio (`.env`)
El Sistema V4 es Universal. Si no indicas variables aquí, tu entorno fallará. Transforma o copia el `example` y asegúrate de cargar todo dinámico:

```bash
# ==========================================
# RUTAS HACIA LA MATRIZ DEL CRM
# ==========================================
# Evita siempre un slash final en el dominio
KOMMO_BASE_URL=https://nombredetuempresa.kommo.com
KOMMO_ACCESS_TOKEN=tu_bearer_api_jwt_aqui

# ==========================================
# CREDENCIALES DEL OPERADOR VIRTUAL (CHROME)
# ==========================================
# Vital: Usuario sin doble autenticacion!
KOMMO_LOGIN_EMAIL=botmaster@startup.com
KOMMO_LOGIN_PASSWORD=ClaveMegaUltraSecreta!

# ==========================================
# COLUMNAS VERTEBRALES DE ALMACENAMIENTO
# ==========================================
DATABASE_URL=postgresql://usuario:password@localhost:5432/kommo_analytica
PORT=5000            # El WebServer de tu Dashboard Flask levantara aqui.
REDIS_URL=redis://   # Para integraciones futuras con Colas N8N!
```
