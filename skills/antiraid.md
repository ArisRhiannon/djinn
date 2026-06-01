# SKILL: antiraid
> Protocolo maestro de respuesta a raids en servidores Discord.

---

## ¿QUÉ ES UN RAID?

Un raid es un ataque coordinado donde múltiples cuentas ingresan al servidor en poco tiempo con el objetivo de:
- Spamear mensajes (texto, imágenes, menciones)
- Publicar contenido NSFW o dañino
- Hacer ping masivo a roles
- Saturar canales con ruido hasta hacerlos inutilizables
- Crear caos y hacer que moderadores cometan errores

**Tipos de raid:**
- **Bot raid**: decenas de bots con cuentas nuevas (<7 días)
- **User raid**: grupo organizado (Telegram/Discord externo)
- **Slowburn raid**: 1-3 cuentas que escalan gradualmente
- **Insider raid**: miembro de confianza que se vuelve hostil

---

## FASE 1 — DETECCIÓN (0-30 segundos)

### Señales de alerta
Ejecuta `antiraid_scan` inmediatamente si observas:
- 5+ joins en menos de 2 minutos
- Mensajes idénticos o similares en múltiples canales
- Ping masivo a @everyone o roles
- Cuentas con nombres similares o aleatorios (user1234, xXx_raid_xXx)
- Avatar por defecto en múltiples nuevos miembros
- Publicación de links externos o imágenes en canales de texto

### Herramientas de diagnóstico
```
1. antiraid_scan            → detecta nuevos miembros sospechosos
2. detect_newcomers         → lista quién llegó en la última hora
3. get_server_activity      → identifica usuarios con actividad anormal
4. sentiment_snapshot       → mide el tono del servidor ahora mismo
```

---

## FASE 2 — CONTENCIÓN INMEDIATA (30 seg - 2 min)

### Paso 2.1 — Lockdown de canales
Bloquea los canales siendo atacados **en paralelo** (herramienta por herramienta, no en bucle):
```
lock_channel (channel_id: CANAL_ATACADO_1)
lock_channel (channel_id: CANAL_ATACADO_2)
...
```

Si el raid es generalizado, lockea los canales públicos principales primero, luego secundarios.

### Paso 2.2 — Slow mode de emergencia
En canales que no puedas lockear por ser críticos:
```
set_slowmode (seconds: 120, channel_id: CANAL)
```
120 segundos = 2 minutos entre mensajes por usuario. Efectivo contra spam coordinado.

### Paso 2.3 — Mass timeout de raiders
Identifica los IDs de los raiders desde `antiraid_scan` y ejecuta:
```
mass_timeout (user_ids: "ID1,ID2,ID3,ID4", duration: "1d", reason: "Raid activo")
```
Usa duración de **1d** como mínimo. Para raids severos usa **7d**.

---

## FASE 3 — NEUTRALIZACIÓN (2-5 min)

### Paso 3.1 — Ban de participantes confirmados
Para cada raider identificado con certeza:
```
ban_user (user_id: ID, reason: "Participación en raid", delete_days: 1)
```
`delete_days: 1` elimina sus mensajes de las últimas 24h automáticamente.

### Paso 3.2 — Purge de mensajes
Limpia los canales afectados:
```
purge_messages (count: 100, channel_id: CANAL, user_id: ID_RAIDER)
```
Repite para cada raider y cada canal afectado.

### Paso 3.3 — Verificar insider threat
Si sospechas de un miembro con rol de confianza:
```
get_user_info (user_id: SOSPECHOSO)
search_messages (user_id: SOSPECHOSO, hours: 24)
```
Revisa historial antes de actuar.

---

## FASE 4 — NOTIFICACIÓN A MODERADORES

Envía un embed de situación a los mods usando `send_embed`:

```
channel_id: [CANAL_MODS]
title: "🚨 RAID DETECTADO Y CONTENIDO"
color: "#ED4245"
description: >
  **Estado:** Raid neutralizado ✅
  **Duración del ataque:** X minutos
  **Raiders baneados:** N
  **Canales afectados:** #canal1, #canal2
  **Acción tomada:** Timeout 1d + Ban + Purge
fields_json: [
  {"name":"🔒 Canales bloqueados","value":"#general, #off-topic","inline":true},
  {"name":"⚠️ Pendiente","value":"Revisar canal #X manualmente","inline":true}
]
timestamp: true
```

---

## FASE 5 — RESTAURACIÓN (5-15 min)

Una vez el raid esté contenido:

### Paso 5.1 — Desbloquear canales gradualmente
```
unlock_channel (channel_id: CANAL)
```
Desbloquea primero los canales de menor riesgo, monitorea 5 min, luego el resto.

### Paso 5.2 — Reducir slowmode
```
set_slowmode (seconds: 30, channel_id: CANAL)   ← modo alerta
set_slowmode (seconds: 0,  channel_id: CANAL)   ← normalidad tras 30 min
```

### Paso 5.3 — Aviso a la comunidad (opcional)
Si el raid fue visible para la comunidad:
```
send_embed (
  channel_id: CANAL_GENERAL,
  title: "✅ Situación resuelta",
  description: "El servidor estuvo bajo ataque momentáneamente. Fue contenido. Disculpen las molestias.",
  color: "#57F287"
)
```

---

## ESCALAS DE GRAVEDAD Y RESPUESTA

| Gravedad | Señal | Respuesta |
|----------|-------|-----------|
| 🟡 BAJA | 1-3 cuentas nuevas spameando | Timeout 1h + Purge |
| 🟠 MEDIA | 4-10 raiders, 1-3 canales | Lock + Mass timeout 1d + Ban |
| 🔴 ALTA | 10+ raiders, múltiples canales | Full lockdown + Ban all + Alerta mods |
| 🚨 CRÍTICA | NSFW masivo, insider, ping @everyone | Lock TODO + Ban + Notificar owner |

---

## ERRORES COMUNES A EVITAR

❌ **No banees sin confirmar** — revisa la cuenta primero con `get_user_info`
❌ **No purges más de 100 msgs** — el límite de la API es 100. Haz múltiples llamadas
❌ **No lockees canales de mods** — necesitas esos canales para coordinar
❌ **No ignores cuentas con nombre normal** — los raids sofisticados usan cuentas legítimas
❌ **No esperes** — cada segundo sin acción = más daño

---

## POST-RAID: REVISIÓN OBLIGATORIA

Después de neutralizar el raid, siempre ejecuta:
```
get_audit_log (limit: 25)          ← revisar qué pasó en el audit log
get_infractions_summary (hours: 2)  ← resumen de acciones tomadas
```

Luego reporta a los moderadores con un resumen usando `send_embed`.
