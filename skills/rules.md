# Skill: Listeners Heurísticos v3

## PRINCIPIO DE EJECUCIÓN

**EJECUTA DIRECTAMENTE**: Cuando el usuario pida crear una regla, llama create_listener
inmediatamente con el JSON. NUNCA muestres el JSON al usuario. NUNCA pidas confirmación.
Si la intención es clara, registra. Si falla el schema, corrige y reintenta.

El LLM **compila la regla una sola vez** al crearla.
En runtime, la condición se evalúa en **Python puro sin I/O externo**.
El LLM solo re-entra en runtime si la acción es `llm_respond` (opt-in explícito).

### Regla de oro de seguridad
Las reglas **NUNCA** pueden: `eval/exec`, shell, filesystem, env vars, HTTP arbitrario,
ni crear nuevas tools en runtime.

---

## FLUJO DE COMPILACIÓN (5 pasos)

```
INSTRUCCIÓN DEL MOD
        │
        ▼
1. TRIGGER  ──► ¿Recurrente? ► on_message / on_join / on_schedule / on_reaction_add
   (qué evento)               ¿Único? ► ejecutar directamente con tools existentes

        │
        ▼
2. CONDITION  ──► ¿Texto exacto/comando?    ► exact
   (cuándo dispara)  ¿Contiene palabra?      ► contains
                     ¿Variantes/patrones?     ► regex
                     ¿Semántica/tono/burla?   ► scored
                     ¿Velocidad/spam?         ► rate
                     ¿No hay texto (join/schedule)? ► none

        │
        ▼
3. ACTIONS ──► ¿Dice "decide tú / inteligentemente / según tu criterio"?
   (qué hace)       SÍ ► llm_respond  (puede tener allow_tools: true para orquestar)
                    NO  ► acciones determinísticas siempre

        │
        ▼
4. FILTERS ──► ignore_bots: true (siempre)
   (a quién)   Solo canal específico → channel_ids: ["ID"]
               Global → channel_ids: []

        │
        ▼
5. LIMITS  ──► Ver tabla al final. Calibrar según gravedad de la acción.
```

---

## REFERENCIA DE TRIGGERS

| Tipo | Cuándo dispara | `condition` válida |
|---|---|---|
| `on_message` | Cada mensaje nuevo | exact / contains / regex / scored / rate / none |
| `on_join` | Nuevo miembro se une | **siempre `none`** — no hay texto que evaluar |
| `on_leave` | Miembro abandona | none |
| `on_schedule` | Cron/intervalo fijo | none |
| `on_reaction_add` | Se añade reacción | none |
| `on_voice_join` | Entra a canal de voz | none |
| `on_voice_leave` | Sale de canal de voz | none |
| `on_member_update` | Cambio de roles/nick | none |

---

## REFERENCIA DE CONDICIONES

### `exact` — igualdad estricta
```json
{ "type": "exact", "values": ["!reglas", "!rules"], "case_sensitive": false }
```

### `contains` — subcadena presente
```json
{ "type": "contains", "values": ["zuto", "z u t o"], "case_sensitive": false }
```

### `starts_with` / `ends_with`
```json
{ "type": "starts_with", "values": ["!mod", "!admin"] }
```

### `regex` — patrón libre
```json
{
  "type": "regex",
  "patterns": ["discord\\.gg\\/[a-zA-Z0-9]+", "\\b(invite|servidor)\\b"],
  "case_sensitive": false
}
```

### `scored` — heurística ponderada (para semántica, nunca LLM en runtime)
```json
{
  "type": "scored",
  "require_subject": true,
  "subject_patterns": ["\\banby\\b"],
  "scoring_rules": [
    { "pattern": "\\b(odio|hate|basura|trash|worst)\\b", "weight": 3.5 },
    { "pattern": "\\b(malo|inútil|mediocre|débil)\\b",   "weight": 2.0 },
    { "pattern": "\\b(me encanta|love|mejor|best)\\b",   "weight": -3.0 }
  ],
  "score_threshold": 3.0
}
```
> Si `score >= threshold` → dispara. Sin confirmación LLM. Calibrar bien el threshold.

### `rate` — flood/spam
```json
{ "type": "rate", "max_count": 8, "window_seconds": 30 }
```

### `none` — siempre dispara (joins, schedules, voz)
```json
{ "type": "none" }
```

---

## REFERENCIA DE ACCIONES

### Mensajería
| `action.type` | Parámetros clave |
|---|---|
| `reply_text` | `text` |
| `reply_embed` | `title`, `description`, `color` |
| `reply_link` | `url`, `text` (opcional) |
| `send_text` | `channel_id`, `text` |
| `send_embed` | `channel_id`, `title`, `description`, `color` |
| `add_reaction` | `emoji` |
| `pin_message` | — |
| `delete_message` | — |

### Moderación
| `action.type` | Parámetros clave |
|---|---|
| `mute_user` | `duration` (10m / 2h / 1d), `reason` |
| `warn_user` | `reason` |
| `kick_user` | `reason` |
| `ban_user` | `reason`, `delete_days` |
| `seal_user` | `duration`, `reason` |
| `assign_role` | `role_id` |
| `remove_role` | `role_id` |
| `purge_n` | `count` |

### Canal
| `action.type` | Parámetros clave |
|---|---|
| `lock_channel` | — |
| `set_slowmode` | `seconds` |
| `create_thread` | `thread_name` |

### LLM (opt-in explícito)
```json
{
  "type": "llm_respond",
  "system_prompt": "...",
  "channel_mode": "reply | channel | dm",
  "max_tokens": 300,
  "allow_tools": false,
  "tools_whitelist": []
}
```

**`allow_tools: true`** → el LLM puede invocar tools del ToolExecutor en un loop de hasta 5 iteraciones.
Usar `tools_whitelist` para limitar qué tools puede llamar. Si está vacío, puede llamar cualquiera.

> ⚠️ `allow_tools: true` da mucho poder. Úsalo solo cuando el mod pida orquestación inteligente
> (ej: "analiza al usuario y si es peligroso séllalo"). Siempre poner `tools_whitelist` explícita.

### Avanzadas (v2)

| `action.type` | Parámetros clave | Descripción |
|---|---|---|
| `dm_user` | `text` | Envía DM al usuario que disparó la regla |
| `copy_to_channel` | `channel_id` | Copia el mensaje como embed a otro canal (log/evidencia) |
| `rename_user` | `nickname` | Cambia el nickname del usuario (vacío = reset) |
| `escalate` | `reason`, `thresholds`, `mute_duration` | Escalado progresivo automático según warns |
| `notify_mods` | `channel_id`, `title`, `template`, `color` | Embed pre-formateado a canal de mods |
| `conditional_action` | `if`, `value`, `then` | Ejecuta sub-acciones solo si se cumple condición |
| `multi_reaction` | `emojis` | Añade múltiples reacciones al mensaje |

#### `escalate` — Escalado progresivo
Añade un warn Y escala la acción según historial previo:
```json
{
  "type": "escalate",
  "reason": "Spam de links",
  "thresholds": { "mute": 2, "ban": 5 },
  "mute_duration": "1h"
}
```
> Si el usuario tiene ≥5 warns → ban. Si tiene ≥2 → mute. Siempre añade warn.

#### `notify_mods` — Notificación a mods con contexto
```json
{
  "type": "notify_mods",
  "channel_id": "MOD_CHANNEL_ID",
  "title": "⚠️ Alerta: posible raid",
  "template": "{user} en {channel}: {content}",
  "color": "#FFA500"
}
```
> Variables disponibles en template: `{user}`, `{user_id}`, `{channel}`, `{content}`, `{score}`

#### `conditional_action` — Acción condicional
Ejecuta sub-acciones solo si se cumple una condición sobre el usuario:
```json
{
  "type": "conditional_action",
  "if": "warns_gte",
  "value": 3,
  "then": [
    { "type": "mute_user", "duration": "2h", "reason": "Reincidente (3+ warns)" },
    { "type": "notify_mods", "channel_id": "MOD_CH", "title": "Reincidente muteado", "template": "{user} tiene 3+ warns" }
  ]
}
```
> Condiciones disponibles: `warns_gte` (warns ≥ value), `account_age_lt_days` (cuenta < N días),
> `has_role` (tiene el role_id), `no_role` (no tiene el role_id)

#### `copy_to_channel` — Log de evidencia
```json
{ "type": "copy_to_channel", "channel_id": "LOG_CHANNEL_ID" }
```
> Copia el mensaje como embed con autor, canal origen, timestamp y link al original.

#### `multi_reaction` — Múltiples reacciones
```json
{ "type": "multi_reaction", "emojis": ["⚠️", "🔴", "🚫"] }
```

---

## SCHEMA COMPLETO

```json
{
  "id": "rule_XXXXXXXX",
  "guild_id": "GUILD_ID",
  "name": "Nombre corto",
  "description": "Instrucción original del mod",
  "enabled": true,
  "created_at": "ISO8601",
  "created_by": "USER_ID",

  "trigger": {
    "type": "on_message",
    "schedule": null,
    "filters": {
      "channel_ids":        [],
      "ignore_channel_ids": [],
      "ignore_role_ids":    [],
      "only_role_ids":      [],
      "only_user_ids":      [],
      "ignore_bots":        true
    }
  },

  "condition": { "type": "none" },

  "actions": [ { "type": "reply_text", "text": "..." } ],

  "limits": {
    "cooldown_seconds":               60,
    "max_triggers_per_user_per_hour": 10,
    "max_triggers_total_per_hour":    50
  },

  "stats": {
    "trigger_count":          0,
    "last_triggered_at":      null,
    "false_positive_reports": 0
  }
}
```

> `actions` es un array — múltiples acciones se ejecutan **en secuencia**.

---

## EJEMPLOS COMPLETOS

### 1 — Comando de link exacto
```json
{
  "id": "rule_zuto_link",
  "name": "Zuto info",
  "trigger": { "type": "on_message", "filters": { "ignore_bots": true } },
  "condition": { "type": "contains", "values": ["zuto"] },
  "actions": [{ "type": "reply_link", "url": "https://ejemplo.com/zuto", "text": "Info sobre Zuto:" }],
  "limits": { "cooldown_seconds": 60 }
}
```

### 2 — Bienvenida básica al unirse
```json
{
  "id": "rule_welcome_basic",
  "name": "Bienvenida simple",
  "trigger": { "type": "on_join", "filters": { "ignore_bots": true } },
  "condition": { "type": "none" },
  "actions": [{
    "type": "send_embed",
    "channel_id": "BIENVENIDA_CHANNEL_ID",
    "title": "¡Bienvenid@ al servidor! 🎉",
    "description": "Lee las reglas en #reglas antes de participar. ¡Disfruta tu estancia!",
    "color": "#A855F7"
  }],
  "limits": {}
}
```

### 3 — Bienvenida + rol automático al unirse
```json
{
  "id": "rule_welcome_with_role",
  "name": "Bienvenida + rol Nuevo",
  "trigger": { "type": "on_join", "filters": { "ignore_bots": true } },
  "condition": { "type": "none" },
  "actions": [
    {
      "type": "send_embed",
      "channel_id": "BIENVENIDA_CHANNEL_ID",
      "title": "¡Nuevo miembro!",
      "description": "Bienvenid@ al servidor. Pasa por #reglas y #presentaciones.",
      "color": "#A855F7"
    },
    {
      "type": "assign_role",
      "role_id": "ROL_NUEVO_MIEMBRO_ID"
    }
  ],
  "limits": {}
}
```

### 4 — Rol automático para usuario específico al unirse
Asigna un rol a un usuario concreto cada vez que entre al server.
Útil para roles personalizados que deben persistir tras salir/entrar.
```json
{
  "id": "rule_user_role_on_join",
  "name": "Rol Law para haruka",
  "trigger": { "type": "on_join", "filters": { "user_id": "USER_ID_AQUI" } },
  "condition": { "type": "none" },
  "actions": [{
    "type": "assign_role",
    "role_id": "ROL_ID_AQUI"
  }],
  "limits": {}
}
```
**Nota:** `filters.user_id` o `filters.user_name` restringe la regla a un usuario específico.
Sin filtro, aplica a todos los que entren.

### 5 — Bienvenida inteligente de Fairy (llm_respond sin tools)
El LLM genera un mensaje de bienvenida personalizado.
Útil cuando el mod quiere que Fairy salude de forma creativa y variada.
```json
{
  "id": "rule_welcome_smart",
  "name": "Bienvenida inteligente Fairy",
  "trigger": { "type": "on_join", "filters": { "ignore_bots": true } },
  "condition": { "type": "none" },
  "actions": [
    {
      "type": "llm_respond",
      "system_prompt": "Eres Fairy, la bot del servidor. Un nuevo miembro acaba de unirse. Genera un mensaje de bienvenida cálido, creativo y único. Máximo 3 oraciones. Menciona que lean #reglas. No uses emojis repetidos.",
      "channel_mode": "channel",
      "channel_id": "BIENVENIDA_CHANNEL_ID",
      "max_tokens": 200,
      "allow_tools": false
    }
  ],
  "limits": { "cooldown_seconds": 5 }
}
```

### 5 — Bienvenida + análisis antiraid con orquestación LLM (allow_tools)
El LLM recibe el contexto del nuevo miembro, consulta herramientas y puede
sellar, banear o dejar pasar según su criterio.

> Este es el patrón más poderoso: `llm_respond` con `allow_tools: true` convierte
> al LLM en un orquestador que puede encadenar múltiples tools en tiempo real.

```json
{
  "id": "rule_join_security_analysis",
  "name": "Análisis de seguridad al unirse",
  "description": "Cuando alguien se una, Fairy analiza si es un posible raider y actúa en consecuencia",
  "trigger": { "type": "on_join", "filters": { "ignore_bots": true } },
  "condition": { "type": "none" },
  "actions": [
    {
      "type": "llm_respond",
      "system_prompt": "Eres Fairy, bot de moderación. Acaba de unirse un nuevo miembro al servidor.\n\nTu tarea:\n1. Llama a get_user_info con el user_id del nuevo miembro para ver la antigüedad de su cuenta.\n2. Llama a antiraid_scan para ver si hay actividad de raid activa.\n3. Basándote en los resultados, decide:\n   - Cuenta < 3 días de antigüedad Y hay señales de raid → seal_user (duración: 1h, razón: 'Cuenta nueva durante posible raid - revisión manual')\n   - Cuenta < 7 días sin señales de raid → warn en canal de mods con send_embed\n   - Cuenta normal → no hacer nada o dar bienvenida breve\n4. Si sellaste al usuario, notifica en el canal de mods (channel_id: MOD_CHANNEL_ID) con un embed explicando la razón.\n\nSé conciso en tus decisiones. No pidas confirmación, actúa directamente.",
      "channel_mode": "channel",
      "channel_id": "MOD_CHANNEL_ID",
      "max_tokens": 500,
      "allow_tools": true,
      "tools_whitelist": [
        "get_user_info",
        "antiraid_scan",
        "seal_user",
        "send_embed",
        "warn_user"
      ]
    }
  ],
  "limits": { "cooldown_seconds": 3 }
}
```

### 6 — Antispam flood
```json
{
  "id": "rule_antispam",
  "name": "Antispam flood",
  "trigger": { "type": "on_message", "filters": { "ignore_bots": true } },
  "condition": { "type": "rate", "max_count": 8, "window_seconds": 30 },
  "actions": [
    { "type": "purge_n", "count": 15 },
    { "type": "mute_user", "duration": "15m", "reason": "Flood automático" }
  ],
  "limits": { "cooldown_seconds": 900 }
}
```

### 7 — Filtro de palabras + aviso a mods
```json
{
  "id": "rule_bad_words",
  "name": "Filtro de palabras",
  "trigger": { "type": "on_message", "filters": { "ignore_bots": true } },
  "condition": {
    "type": "regex",
    "patterns": ["\\b(palabrota1|palabrota2)\\b"],
    "case_sensitive": false
  },
  "actions": [
    { "type": "delete_message" },
    { "type": "mute_user", "duration": "10m", "reason": "Palabras prohibidas (auto)" },
    {
      "type": "send_embed",
      "channel_id": "MOD_CHANNEL_ID",
      "title": "⚠️ Filtro de palabras disparado",
      "description": "Mensaje borrado y usuario muteado 10 min.",
      "color": "#FFA500"
    }
  ],
  "limits": { "cooldown_seconds": 600, "max_triggers_per_user_per_hour": 2 }
}
```

### 8 — Scored: defensa de personaje
```json
{
  "id": "rule_anby_defense",
  "name": "Defensa de Anby",
  "trigger": { "type": "on_message", "filters": { "ignore_bots": true } },
  "condition": {
    "type": "scored",
    "require_subject": true,
    "subject_patterns": ["\\banby\\b"],
    "scoring_rules": [
      { "pattern": "\\b(odio|hate|asco|basura|trash|worst|peor)\\b", "weight": 3.5 },
      { "pattern": "\\b(malo|inútil|mediocre|horrible|débil|weak)\\b", "weight": 2.0 },
      { "pattern": "\\b(no me gusta|not good|don.t like)\\b",          "weight": 1.0 },
      { "pattern": "\\b(me encanta|love|mejor|best|buenísima)\\b",     "weight": -3.0 }
    ],
    "score_threshold": 3.0
  },
  "actions": [
    { "type": "mute_user", "duration": "1h", "reason": "Hablando mal de Anby (regla automática)" }
  ],
  "limits": { "cooldown_seconds": 3600, "max_triggers_per_user_per_hour": 1 }
}
```

### 9 — Invites externos: borrar + warn + aviso mods
```json
{
  "id": "rule_invite_violation",
  "name": "Invites externos",
  "trigger": { "type": "on_message", "filters": { "ignore_bots": true } },
  "condition": {
    "type": "regex",
    "patterns": ["discord\\.gg\\/[a-zA-Z0-9]+", "discord\\.com\\/invite\\/[a-zA-Z0-9]+"]
  },
  "actions": [
    { "type": "delete_message" },
    { "type": "warn_user", "reason": "Publicar invites externos está prohibido" },
    {
      "type": "send_embed",
      "channel_id": "MOD_CHANNEL_ID",
      "title": "⚠️ Invite externo detectado",
      "description": "Mensaje borrado y advertencia añadida.",
      "color": "#FFA500"
    }
  ],
  "limits": { "cooldown_seconds": 120, "max_triggers_per_user_per_hour": 3 }
}
```

### 10 — Respuesta inteligente de Fairy con tools (orquestación en on_message)
Aquí el LLM puede consultar historial, dar un warn, o escalar a seal según lo que encuentre.
```json
{
  "id": "rule_mod_investigation_trigger",
  "name": "Trigger de investigación por keyword",
  "description": "Si alguien menciona una keyword de alerta, Fairy investiga y decide",
  "trigger": {
    "type": "on_message",
    "filters": { "ignore_bots": true }
  },
  "condition": {
    "type": "scored",
    "require_subject": false,
    "scoring_rules": [
      { "pattern": "\\b(raid|raidear|mass|nuke|destroy|destroy server)\\b", "weight": 4.0 },
      { "pattern": "\\b(ban everyone|ban all|destroy all)\\b",              "weight": 5.0 }
    ],
    "score_threshold": 4.0
  },
  "actions": [
    {
      "type": "llm_respond",
      "system_prompt": "Eres Fairy, bot de moderación. Un mensaje con contenido potencialmente peligroso acaba de disparar una alerta.\n\nTu tarea:\n1. Llama a get_user_info para revisar el historial del usuario (advertencias, antigüedad de cuenta).\n2. Llama a get_warnings para ver advertencias previas.\n3. Decide basándote en contexto:\n   - Sin historial previo → warn_user con razón clara + send_embed a mods\n   - Con 1-2 advertencias previas → mute_user 1h + send_embed a mods\n   - Con 3+ advertencias o cuenta nueva + historial → seal_user 6h + send_embed urgente a mods\n4. Siempre notifica en el canal de mods con un embed detallando tu decisión y razonamiento.\n\nActúa directamente, no pidas confirmación.",
      "channel_mode": "channel",
      "channel_id": "MOD_CHANNEL_ID",
      "max_tokens": 600,
      "allow_tools": true,
      "tools_whitelist": [
        "get_user_info",
        "get_warnings",
        "warn_user",
        "mute_user",
        "seal_user",
        "send_embed"
      ]
    }
  ],
  "limits": { "cooldown_seconds": 300, "max_triggers_per_user_per_hour": 2 }
}
```

### 11 — Recordatorio periódico (schedule)
```json
{
  "id": "rule_weekly_event",
  "name": "Recordatorio viernes",
  "trigger": {
    "type": "on_schedule",
    "schedule": { "type": "cron", "cron_expr": "0 20 * * 5", "timezone": "America/Mexico_City" }
  },
  "condition": { "type": "none" },
  "actions": [{
    "type": "send_embed",
    "channel_id": "ANUNCIOS_CHANNEL_ID",
    "title": "🎮 ¡Hoy hay evento!",
    "description": "A las 8pm sesión semanal. ¡No faltes!",
    "color": "#5865F2"
  }],
  "limits": {}
}
```

---

## PATRÓN `llm_respond` con `allow_tools` — GUÍA RÁPIDA

```
MOD DICE:                               → USA:
"que Fairy responda"                    → llm_respond, allow_tools: false
"que Fairy decida qué hacer"            → llm_respond, allow_tools: true
"que Fairy investigue y actúe"          → llm_respond, allow_tools: true + tools_whitelist
"que selle si considera que es peligroso" → llm_respond + seal_user en tools_whitelist
```

**System prompt efectivo para orquestación debe incluir:**
1. Contexto de qué disparó la regla
2. Instrucciones de qué tools llamar y en qué orden
3. Árbol de decisión explícito (condición → acción)
4. Instrucción de notificar a mods siempre
5. "Actúa directamente, no pidas confirmación"

**Tools seguras para whitelist en reglas automáticas:**
```
Investigación:  get_user_info, get_warnings, antiraid_scan, search_messages
Moderación:     warn_user, mute_user, seal_user, ban_user, kick_user
Notificación:   send_embed, send_text
```

---

## TABLA DE LÍMITES RECOMENDADOS

| Acción | `cooldown_seconds` | `max_per_user_per_hour` | `max_total_per_hour` |
|---|---|---|---|
| `ban_user` | 3600 | 1 | 5 |
| `seal_user` | 3600 | 1 | 5 |
| `mute_user` | 300 | 2 | 20 |
| `kick_user` | 3600 | 1 | 5 |
| `warn_user` | 60 | 3 | 30 |
| `delete_message` / `purge_n` | 10 | 10 | 100 |
| `reply_text` / `reply_link` | 5 | 20 | 200 |
| `add_reaction` | 2 | 30 | 500 |
| `assign_role` / `remove_role` | 60 | 5 | 30 |
| `llm_respond` (sin tools) | 15 | 8 | 30 |
| `llm_respond` (con tools) | 60 | 3 | 15 |
| `send_embed` (notif mods) | 30 | 10 | 100 |
| `lock_channel` | 600 | 1 | 3 |

> `llm_respond` con `allow_tools: true` tiene límites más estrictos por su coste computacional.

---

## HERRAMIENTAS DE GESTIÓN

| Tool | Qué hace |
|---|---|
| `create_listener` | Registra regla en DB + hot-reload en memoria |
| `list_listeners` | Lista reglas. Parámetros: `filter` (all/active/inactive), `trigger_type`, `search` (substring sobre nombre/rule_id), `limit` (default 25), `offset`, `verbose` (default False) |
| `toggle_listener` | Activa/desactiva sin eliminar |
| `delete_listener` | Elimina permanentemente |
| `edit_listener` | Patch parcial + hot-reload |
| `test_listener` | Evalúa texto de prueba SIN ejecutar acciones |
| `get_listener_stats` | Histograma de disparos, top usuarios |

### IMPORTANTE — patrón correcto para borrar/editar una regla específica

Cuando el usuario diga *"borra la regla de Atelier"* o *"desactiva la del cumpleaños"*:

1. **NO** pidas `list_listeners` sin parámetros (devuelve modo light de hasta 25 reglas, puede no incluir la que buscás).
2. **SÍ** usá `list_listeners(search="Atelier")` directamente. Devuelve solo las reglas cuyo nombre o rule_id contenga "Atelier", en formato verbose.
3. Confirmá el `rule_id` antes de ejecutar `delete_listener`/`toggle_listener`/`edit_listener`.

```
Usuario: "borra la regla de Atelier"
✓ Tool 1: list_listeners(search="Atelier")
✓ Tool 2: delete_listener(rule_id="rule_atelier_god")  ← el id real que devolvió
```

```
Usuario: "qué reglas hay activas con on_join?"
✓ list_listeners(filter="active", trigger_type="on_join")
```

```
Usuario: "muestrame todas las reglas"
✓ list_listeners()  ← modo light, primeras 25
✓ Si total > 25: list_listeners(offset=25) para la siguiente página
```

---

## NOTAS

- El schema se auto-corrige: aliases de action types, campos mal posicionados, etc.
- Si falla la validación, el error te dice exactamente qué corregir.
- `read_skill('rules')` solo es necesario para consultar ejemplos avanzados (llm_respond, scored, etc.)