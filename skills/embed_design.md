# SKILL: embed_design
> Guía maestra para diseñar embeds Discord de alta calidad y impacto visual.

---

## ANATOMÍA DE UN EMBED DISCORD

```
╔══════════════════════════════════════╗
║ [AUTHOR ICON] Author Name            ║  ← author
║ ┌──────────────────────────────────┐ ║
║ │ TÍTULO DEL EMBED                 │ ║  ← title (max 256 chars)
║ │ ────────────────────────────── │ ║
║ │ Descripción principal.           │ ║  ← description (max 4096)
║ │ Soporta **markdown** de Discord. │ ║
║ ├──────────────────────────────────┤ ║
║ │ Campo 1 (inline) │ Campo 2       │ ║  ← fields (max 25)
║ │ valor            │ valor         │ ║
║ ├──────────────────────────────────┤ ║
║ │ Campo largo (no inline)          │ ║
║ │ valor completo aquí              │ ║
║ └────────────────────── [THUMBNAIL]┘ ║  ← thumbnail (esquina derecha)
║ [IMAGE DE ANCHO COMPLETO]            ║  ← image
║ [FOOTER ICON] Footer text · 14:30   ║  ← footer + timestamp
╚══════════════════════════════════════╝
```

---

## PALETA DE COLORES POR TIPO

Usa estos colores hex según el **propósito del embed**:

```
🟢 ÉXITO / BIENVENIDA:    #57F287   (verde Discord)
🔴 ERROR / BAN / ALERTA:  #ED4245   (rojo Discord)
🟡 ADVERTENCIA / WARN:    #FEE75C   (amarillo Discord)
🔵 INFO / ANUNCIO:        #5865F2   (blanco azulado)
🟣 ESPECIAL / EVENTO:     #A855F7   (violeta Fairy)
🩷 CELEBRACIÓN / LOGRO:   #EC4899   (rosa)
⚪ NEUTRAL / LOG:         #2B2D31   (gris Discord)
🧊 MOD LOG:               #4F545C   (gris azulado)
🌅 DAILY / RECORDATORIO:  #F59E0B   (ámbar)
```

---

## PLANTILLAS LISTAS PARA USAR

### Embed de bienvenida
```json
{
  "channel_id": "CANAL_BIENVENIDA",
  "title": "✨ ¡Bienvenido/a a [NOMBRE_SERVIDOR]!",
  "description": "Hola **[USUARIO]**, nos alegra tenerte aquí.\n\n📌 Lee <#CANAL_REGLAS> antes de participar.\n🎭 Escoge tus roles en <#CANAL_ROLES>.\n💬 Preséntate en <#CANAL_PRESENTACIONES>.\n\n¡Esperamos que disfrutes tu estancia! 🌟",
  "color": "#57F287",
  "thumbnail_user_id": "ID_USUARIO",
  "footer_text": "Miembro #N del servidor",
  "timestamp": true
}
```

### Embed de sanción (warn/mute)
```json
{
  "channel_id": "CANAL_LOGS",
  "title": "⚠️ Advertencia Registrada",
  "description": "Se ha registrado una advertencia en el sistema de moderación.",
  "color": "#FEE75C",
  "fields_json": [
    {"name": "👤 Usuario", "value": "[NOMBRE] (`[ID]`)", "inline": true},
    {"name": "🛡️ Moderador", "value": "[MOD]", "inline": true},
    {"name": "📊 Total warns", "value": "[N]/3", "inline": true},
    {"name": "📝 Razón", "value": "[RAZÓN]", "inline": false}
  ],
  "timestamp": true,
  "footer_text": "Sistema de moderación automático"
}
```

### Embed de ban
```json
{
  "channel_id": "CANAL_LOGS",
  "title": "🔨 Usuario Baneado",
  "description": "Un miembro ha sido expulsado permanentemente del servidor.",
  "color": "#ED4245",
  "fields_json": [
    {"name": "👤 Usuario", "value": "[NOMBRE] (`[ID]`)", "inline": true},
    {"name": "🛡️ Moderador", "value": "[MOD]", "inline": true},
    {"name": "📝 Razón", "value": "[RAZÓN]", "inline": false},
    {"name": "🗑️ Mensajes eliminados", "value": "[N] días", "inline": true}
  ],
  "timestamp": true
}
```

### Embed de anuncio importante
```json
{
  "channel_id": "CANAL_ANUNCIOS",
  "title": "📢 [TÍTULO DEL ANUNCIO]",
  "description": "[CUERPO DEL ANUNCIO CON TODOS LOS DETALLES]\n\nPuedes usar **negrita**, *cursiva*, `código`, y > citas en la descripción.",
  "color": "#5865F2",
  "fields_json": [
    {"name": "📅 Fecha", "value": "[FECHA]", "inline": true},
    {"name": "⏰ Hora", "value": "[HORA] UTC", "inline": true}
  ],
  "footer_text": "Equipo de moderación",
  "timestamp": true,
  "ping_everyone": false
}
```

### Embed de evento
```json
{
  "channel_id": "CANAL_EVENTOS",
  "title": "🎉 [NOMBRE DEL EVENTO]",
  "description": "[DESCRIPCIÓN DEL EVENTO]\n\n¡Todos son bienvenidos a participar!",
  "color": "#A855F7",
  "fields_json": [
    {"name": "📅 Fecha", "value": "[FECHA]", "inline": true},
    {"name": "⏰ Hora", "value": "[HORA] UTC", "inline": true},
    {"name": "📍 Dónde", "value": "<#CANAL_EVENTO>", "inline": true},
    {"name": "🎁 Premio", "value": "[PREMIO O N/A]", "inline": false},
    {"name": "📋 Cómo participar", "value": "1. [PASO]\n2. [PASO]\n3. [PASO]", "inline": false}
  ],
  "thumbnail_url": "[URL_IMAGEN_OPCIONAL]",
  "timestamp": true
}
```

### Embed de reglas del servidor
```json
{
  "channel_id": "CANAL_REGLAS",
  "title": "📜 Reglas del Servidor",
  "description": "Para mantener una comunidad sana y agradable, todos los miembros deben seguir estas normas:",
  "color": "#A855F7",
  "fields_json": [
    {"name": "1️⃣ Respeto mutuo", "value": "Trata a todos con respeto. No se toleran insultos, discriminación ni acoso de ningún tipo.", "inline": false},
    {"name": "2️⃣ Sin spam", "value": "Evita mensajes repetitivos, floods de emojis o menciones innecesarias.", "inline": false},
    {"name": "3️⃣ Sin NSFW", "value": "Contenido explícito, violento o perturbador no está permitido fuera de canales designados.", "inline": false},
    {"name": "4️⃣ Sin autopromoción", "value": "No compartas links a tus redes, servidores o contenido sin permiso previo.", "inline": false},
    {"name": "5️⃣ Sigue las normas de Discord", "value": "Respeta los [Términos de Servicio](https://discord.com/terms) y las [Directrices](https://discord.com/guidelines) de Discord.", "inline": false},
    {"name": "⚠️ Consecuencias", "value": "Warn → Mute → Kick → Ban, según la gravedad de la infracción.", "inline": false}
  ],
  "footer_text": "El incumplimiento de estas normas puede resultar en sanción",
  "timestamp": true
}
```

---

## TÉCNICAS AVANZADAS DE MARKDOWN EN EMBEDS

```markdown
**negrita**           → texto en negrita
*cursiva*             → texto en cursiva
__subrayado__         → subrayado
~~tachado~~           → texto tachado
`código inline`       → fuente monoespaciada
> cita               → bloque de cita (barra lateral izquierda)
>>> bloque largo     → cita multilínea
[texto](url)         → hipervínculo
<@USER_ID>           → mención de usuario
<#CHANNEL_ID>        → mención de canal
<@&ROLE_ID>          → mención de rol
\n                   → salto de línea
\n\n                 → párrafo vacío (separador visual)
```

---

## REGLAS DE ORO PARA EMBEDS

1. **Un color, un propósito** — el color debe comunicar instantáneamente el tipo de mensaje.
2. **Máximo 6 campos** — más de 6 se vuelve abrumador visualmente.
3. **Campos inline de 3 en 3** — los campos inline se agrupan en filas de hasta 3. Usa múltiplos de 3.
4. **Título ≤ 60 chars** — si es más largo no se verá completo en móvil.
5. **Timestamp siempre en logs** — cualquier embed de moderación debe tener `"timestamp": true`.
6. **Footer para contexto secundario** — crédito, fuente, instrucciones breves.
7. **Thumbnail para humanizar** — el avatar del usuario afectado humaniza mensajes de moderación.
8. **Descripción antes que campos** — usa descripción para el contexto principal, campos para datos estructurados.

---

## ERRORES FRECUENTES

❌ `fields_json` con `"inline": true` en solo 1 campo — usa 2 o 3 juntos para que se vea bien
❌ Descripción demasiado larga — Discord la cortará después de 4096 caracteres
❌ Más de 25 campos — límite duro de la API de Discord
❌ Color sin `#` — siempre incluye el `#` en el hex: `"#A855F7"` no `"A855F7"`
❌ No añadir timestamp en embeds de moderación — imposible auditar después sin fecha/hora
