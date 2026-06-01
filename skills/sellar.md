# SKILL: sellar
> Protocolo maestro para sellar (aislar) usuarios en el servidor Discord.

---

## ¿QUÉ ES EL SELLO?

El sello es una medida de moderación temporal que:
1. **Aísla** al usuario en un canal privado visible solo para él y los moderadores
2. **Quita todos sus roles** (guardados en DB para restaurar después)
3. **Bloquea el acceso** a todos los demás canales del servidor
4. **Programa la liberación automática** al vencer el tiempo
5. **Notifica a los mods** con un embed interactivo con opciones de liberar/mantener

No es un ban. Es un timeout avanzado con canal de comunicación privado.

---

## CUÁNDO USAR EL SELLO

✅ **Apropiado para:**
- Usuario que necesita una conversación privada urgente con moderación
- Comportamiento disruptivo que requiere aislamiento temporal sin ban
- Conflicto grave entre usuarios (aislar a una parte)
- Investigación activa donde el usuario no debe comunicarse con otros
- Alternativa gradual antes del ban definitivo

❌ **No usar para:**
- Spam simple → usa `mute_user` (timeout)
- Violación leve → usa `warn_user`
- Infracción grave y confirmada → usa `ban_user`
- Usuarios con rol de administrador (fallará por jerarquía de roles)

---

## FLUJO COMPLETO DEL SELLO

### Paso 1 — Verificación previa (OBLIGATORIO)
Antes de sellar, ejecuta:
```
get_user_info(user_id: ID)
```
Confirma:
- El usuario existe en el servidor
- No tiene rol de admin/owner (no se puede sellar)
- Revisa su historial de advertencias
- Evalúa si el sello es la medida correcta

### Paso 2 — Ejecutar el sello
```
seal_user(
  user_id:       "ID_DEL_USUARIO",
  duration:      "2h",            ← ver tabla de duraciones abajo
  reason:        "Razón clara y específica del sello",
  mod_channel_id: "ID_CANAL_MODS" ← donde se enviará el embed de notificación
)
```

### Paso 3 — Lo que hace el sistema automáticamente
1. Guarda todos los roles actuales del usuario en la base de datos
2. Quita **todos** los roles del usuario
3. Crea un rol especial `🔒 Sellado` con `view_channel=False` base
4. Aplica ese rol a todos los canales del servidor (deniega acceso)
5. Crea un canal `🔒-sellado-[username]` visible solo para el usuario y mods
6. Envía un mensaje al usuario en su canal explicando la situación
7. Envía un embed de notificación al canal de mods con reacciones ✅ y 🔒
8. Programa la liberación automática al vencer `duration`

---

## TABLA DE DURACIONES

| Duración | Cuándo usarla |
|----------|---------------|
| `30m`    | Situación de calor, el usuario solo necesita enfriarse |
| `1h`     | Default. Infracción menor-media, primera vez |
| `2h`     | Reincidente o comportamiento más serio |
| `6h`     | Situación grave, necesita tiempo para reflexionar |
| `12h`    | Muy grave, justo antes de considerar ban temporal |
| `1d`     | Extremo. Casi-ban. Reservado para casos muy serios |
| `7d`     | Prácticamente un ban temporal. Usar con criterio |

---

## MENSAJES EN EL CANAL SELLADO

El sistema crea el canal y el usuario verá el mensaje automático. Sin embargo, **si los mods quieren comunicarse con el usuario**, pueden enviar mensajes adicionales al canal sellado:

```
send_message(
  channel_id: "[ID_CANAL_SELLADO]",
  content: "Hola [usuario], has sido aislado temporalmente porque [razón]. 
            Durante este tiempo puedes hablar aquí con los moderadores. 
            Tu sello se levanta automáticamente en [tiempo]."
)
```

---

## EMBED DE NOTIFICACIÓN A MODS

El sistema envía automáticamente un embed al canal de mods. Si necesitas enviarlo manualmente (si no se proporcionó `mod_channel_id`):

```
send_embed(
  channel_id:  "[CANAL_MODS]",
  title:       "🔒 Usuario Sellado",
  color:       "#F59E0B",
  description: "**[NOMBRE_USUARIO]** ha sido sellado.",
  fields_json: [
    {"name":"👤 Usuario","value":"[NOMBRE] (`[ID]`)","inline":true},
    {"name":"⏱️ Duración","value":"[DURACIÓN]","inline":true},
    {"name":"📝 Razón","value":"[RAZÓN]","inline":false},
    {"name":"🔓 Para liberar","value":"Reacciona ✅ al mensaje de sello o usa `/unseal`","inline":false}
  ],
  timestamp:   true
)
```

---

## LIBERACIÓN ANTICIPADA

Si los mods deciden liberar al usuario antes del tiempo programado:

```
unseal_user(user_id: "ID_DEL_USUARIO")
```

Esto:
1. Quita el rol `🔒 Sellado`
2. Restaura todos los roles originales (desde DB)
3. Elimina el canal temporal
4. Cancela la tarea de auto-liberación
5. Notifica al usuario en el canal (antes de eliminarlo)

---

## REACCIONES EN EL EMBED DE MODS

El embed enviado al canal de mods tiene dos reacciones:

| Reacción | Acción |
|----------|--------|
| ✅ | Libera al usuario inmediatamente (como `unseal_user`) |
| 🔒 | Confirma mantener el sello (no hace nada, solo feedback) |

Solo moderadores con permiso `MANAGE_ROLES` pueden activar las reacciones.

---

## ERRORES COMUNES Y SOLUCIONES

### ❌ "Missing Discord permissions"
El bot necesita que su rol esté **por encima** del rol más alto del usuario objetivo. Verifica la jerarquía de roles en el servidor.

### ❌ "Member not found"
El usuario ya no está en el servidor (se fue durante el proceso). Verifica con `get_user_info`.

### ❌ El canal sellado no se elimina tras el tiempo
El bot se reinició durante el sello. Usa `unseal_user` manualmente para limpiar el estado.

### ❌ No se restauraron los roles
Ocurrió un error al guardar en DB. Revisa `get_audit_log` y restaura roles manualmente con `assign_role`.

---

## ADVERTENCIAS IMPORTANTES

⚠️ **Jerarquía de roles:** El bot debe tener el rol más alto posible. Si el usuario tiene un rol igual o superior al bot, el sello fallará.

⚠️ **Sin roles de admin:** No se puede sellar a alguien con permisos de `Administrator` — Discord no permite quitarles acceso por overwrite.

⚠️ **Un sello a la vez:** No selles al mismo usuario dos veces sin liberar primero. Causará conflicto en DB y creará un rol sellado duplicado.

⚠️ **Canales por categoría:** Los canales dentro de categorías con permisos sincronizados pueden ignorar los overwrites del rol sellado. Si el sello no parece funcionar en algunos canales, revisa la sincronización de la categoría.
