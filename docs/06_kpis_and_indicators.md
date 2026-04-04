# 06. Formulación de KPIs (Reglas Lógicas Comerciales)

Un gran Data Center es ciego si no hay inteligencia procesándola. Nuestra sección base de Negocios evalúa cada interacción procesada a través del `extract_chat_robust` aplicando sentencias Condicionales Python strictas para clasificar el Lead.

---

## 1. El Detector Central de Atención (`attention_status`)
Un Lead puede hablar desde 3 horas a 4 días con distintas personas en el mismo Chat de Kommo. Nos importa **cómo quedó el final de la plática**.

El Scraper extrae todo el arreglo y lee el **último mensaje emitido**:

```mermaid
%%{init: {'theme': 'dark'}}%%
flowchart TD
    Inicio[Lectura del Último Array de Chat] --> Dir{¿Último Mensaje Dirección?}
    Dir -- IN --> Pend[💥 PENDING_RESPONSE (Cliente esperando)]
    
    Dir -- OUT --> SubQ{¿Quien lo Envío?}
    SubQ -- Robot Engine / Regex Bot --> BOnly[🤖 BOT_ONLY (Humano ausente en todo el Array)]
    SubQ -- Agente Humano --> Check{¿Hubo mensajes IN previos del cliente?}
    Check -- SÍ --> Atend[✅ ATTENDED (Hubo respuesta mutua)]
    Check -- NO --> OB[📢 OUTBOUND_ONLY (Propaganda Directa Ignorada)]
```

> **Explicación del `bot_only` vs `attended`:** El sistema sabe inferir que, si entró un mensaje de cliente y salió un de agente, el estatus base será satisfactorio (Attended). Si el cliente habló e inició el chat pero nadie le contestó excepto el Bot (Tami/Funy)... se quedará calificado como un Lead "Bot_Only".

---

## 2. El Radar Antimonio / No-Reply Tracker (Métrica 5/0)
La tabla `kommo_no_reply_tracking` busca específicamente leads abandonados en ráfagas.

**Reglas de Condición Interna del Python Tracker:**
1. Traza los últimos 5 mensajes temporales.
2. Si los 5 mensajes provienen del Equipo de Ventas (`OUT`) *Y NINGUNO* posee etiqueta `IN`.
3. El Backend inyecta al lead forzosamente a esta tabla.
4. **Utilidad Vital:** Estos tableros permiten a Marketing frenar envíos estériles y proteger el rating / salud del canal de WhatsApp. El Asesor sabe que insistir es motivo de denuncia a Meta.

---

## 3. Contadores Dinámicos Transversales
En la compilación el motor hace una revisión acumulada:
- Registramos **`first_bot_time`** vs **`first_human_time`**. Restando la llegada original a la tabla de Postgres, descubririamos que tras enviar el SMS inicial (`IN`), el `human_time` varió en 1 hora 12 minutos... revelando lentitud extrema por los operadores.
- Trazabilidad y Cruces Tags vía **UTMs**: Acoplado a `kommo_leads` y `custom_fields`. Evaluará el ROAS real (Cuánto conversan vs De Dónde Vinieron).
