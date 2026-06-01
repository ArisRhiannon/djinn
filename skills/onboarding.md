# SKILL: onboarding
> Protocolo completo para dar la bienvenida a nuevos miembros y configurar el servidor para recepción óptima.

---

## FILOSOFÍA DEL ONBOARDING

Los primeros **5 minutos** de un nuevo miembro determinan si se queda o se va. Un onboarding excelente:
- Hace sentir bienvenido al recién llegado de manera genuina
- Le da información suficiente sin abrumarlo
- Lo conecta visualmente con la identidad del servidor
- Lo guía hacia los canales correctos de inmediato

---

## FLUJO ESTÁNDAR DE BIENVENIDA

### Paso 1 — Verificar que el usuario sea legítimo
```
get_user_info(user_id: NUEVO_ID)
```
Revisa:
- ¿La cuenta tiene más de 7 días de antigüedad? (cuentas nuevas = mayor riesgo)
- ¿Tiene avatar? (bots/raiders frecuentemente no tienen)
- ¿Se unió junto con otros usuarios al mismo tiempo? (posible raid)

Si algo es sospechoso, aplica `watch_user` antes de darle bienvenida completa.

### Paso 2 — Embed de bienvenida personalizado
```
send_embed(
  channel_id: "CANAL_BIENVENIDA",
  title: "✨ ¡Bienvenido/a, [NOMBRE]!",
  description: "Nos alegra tenerte en **[SERVIDOR]**.\n\n[MENSAJE PERSONALIZADO SEGÚN EL TIPO DE SERVIDOR]\n\n📌 Empieza por aquí:\n→ <#CANAL_REGLAS> · Lee las normas\n→ <#CANAL_ROLES> · Personaliza tu perfil\n→ <#CANAL_PRESENTACIONES> · Saluda a la comunidad",
  color: "#57F287",
  thumbnail_user_id: "NUEVO_ID",
  footer_text: "Miembro #[N] · [NOMBRE_SERVIDOR]",
  timestamp: true
)
```

### Paso 3 — Asignar rol de novato (si existe)
```
assign_role(user_id: NUEVO_ID, role_id: ROL_NOVATO_ID)
```

### Paso 4 — Notificación opcional a mods (para servidores pequeños)
```
send_embed(
  channel_id: "CANAL_STAFF",
  title: "📥 Nuevo miembro",
  description: "**[NOMBRE]** se unió al servidor.",
  color: "#3B82F6",
  fields_json: [
    {"name": "Cuenta creada", "value": "[FECHA]", "inline": true},
    {"name": "ID", "value": "`[ID]`", "inline": true}
  ],
  timestamp: true
)
```

---

## MENSAJES DE BIENVENIDA POR TIPO DE SERVIDOR

### Servidor de gaming
```
¡Has llegado al cuartel general de los mejores jugadores! 🎮

Aquí encontrarás equipo con quién jugar, torneos, noticias y mucho más.
No olvides pasar por <#roles> para activar los juegos que juegas
y unirte a la acción en <#matchmaking>.

¡GG y bienvenido!
```

### Servidor de anime/fandom
```
¡Otro nakama se une a la aventura! ⭐

Somos una comunidad apasionada por [FANDOM]. Aquí puedes debatir,
compartir fanart, hacer amigos y mucho más.
Pasa por <#roles-de-fandom> para elegir tus series favoritas
y desbloquear canales dedicados.

¡Bienvenido a la familia!
```

### Servidor comunitario general
```
¡Bienvenido/a a tu nuevo hogar en Discord! 🏠

Este es un espacio para conocer gente, charlar y pasarla bien.
No hay más reglas que el respeto mutuo — lee <#reglas> para
el detalle y luego ve a presentarte en <#presentaciones>.

¡Esperamos conocerte mejor!
```

---

## SISTEMA DE BIENVENIDA AVANZADO (MÚLTIPLES PASOS)

Para servidores que quieren más profundidad:

### 1. DM de bienvenida
```
send_dm(
  user_id: NUEVO_ID,
  content: "¡Hola [NOMBRE]! 👋 Gracias por unirte a **[SERVIDOR]**.\nAquí tienes todo lo que necesitas para empezar:\n\n📜 **Reglas:** [LINK]\n🎭 **Roles:** <#CANAL_ROLES>\n💬 **Presentaciones:** <#CANAL_PRES>\n\nSi tienes dudas, escríbeme aquí o menciona a @Moderador en el servidor.",
  embed_title: "Bienvenido a [SERVIDOR]",
  embed_color: "#A855F7"
)
```

### 2. Evento de bienvenida en canal principal
```
send_embed(canal_general, ...)  ← embed público
```

### 3. Hilo privado opcional (servidores premium)
```
create_thread(
  message_id: ID_DEL_MENSAJE_DE_BIENVENIDA,
  thread_name: "👋 Bienvenida de [NOMBRE]",
  auto_archive: 1440
)
```
Luego enviar un mensaje al hilo invitando al nuevo miembro a presentarse.

---

## SETUP DE CANALES DE ONBOARDING

Si el servidor necesita configurar el sistema de bienvenida desde cero:

### Canales mínimos recomendados
```
📋 #reglas              → lock_channel para que nadie escriba, solo leer
👋 #bienvenidas         → solo el bot puede escribir
🎭 #roles               → reaction roles o selección de roles
💬 #presentaciones      → primer canal donde los nuevos pueden escribir
📢 #anuncios            → lock_channel, solo admins escriben
```

### Configuración de canales
```
lock_channel(canal_reglas)     ← nadie escribe, solo leen
lock_channel(canal_anuncios)   ← solo staff puede escribir
set_channel_topic(
  channel_id: CANAL_BIENVENIDAS,
  topic: "Bienvenidas automáticas de nuevos miembros · Solo el bot puede escribir aquí"
)
```

---

## MÉTRICAS DE ONBOARDING SALUDABLE

Usa estas herramientas para evaluar la retención:
```
detect_newcomers(hours: 168)          ← nuevos de la última semana
find_inactive_members(days: 7)        ← quién llegó y nunca participó
get_server_activity(hours: 168)       ← actividad general de la semana
```

**Señal de alerta:** Si más del 50% de los nuevos de la semana están en `find_inactive_members(days: 7)`, el onboarding necesita mejoras.

**Señal positiva:** Los nuevos aparecen en `get_server_activity` dentro de las primeras 24h.

---

## MENSAJES PERSONALIZADOS POR NÚMERO DE MIEMBRO

Añade momentos especiales para hitos:
```python
if miembro_numero == 100:
    titulo = "🎊 ¡El miembro #100 está aquí!"
    color  = "#EC4899"
elif miembro_numero == 500:
    titulo = "🏆 ¡Miembro #500! ¡Gran hito!"
    color  = "#F59E0B"
elif miembro_numero % 100 == 0:
    titulo = f"✨ ¡Miembro #{miembro_numero}! ¡Gracias por estar aquí!"
    color  = "#A855F7"
else:
    titulo = f"👋 ¡Bienvenido/a, {nombre}!"
    color  = "#57F287"
```

Adapta el embed según el hito para celebrar el crecimiento de la comunidad.
