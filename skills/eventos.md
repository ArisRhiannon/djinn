# SKILL: eventos
> Guía completa para planificar, crear y gestionar eventos en servidores Discord.

---

## TIPOS DE EVENTOS EN DISCORD

| Tipo | Descripción | Herramienta |
|------|-------------|-------------|
| **Evento de canal de voz** | El evento ocurre en un VC del servidor | `create_event(voice_channel_id: ID)` |
| **Evento externo** | Fuera de Discord (stream, IRL, web) | `create_event(location: "URL o descripción")` |
| **Torneo / competencia** | Con bracket y registro | Combinación de múltiples herramientas |
| **Anuncio + encuesta** | Para medir interés previo | `create_poll` + `send_embed` |

---

## FLUJO COMPLETO DE UN EVENTO

### Fase 1 — Planificación (días antes)

#### 1.1 Encuesta de interés (opcional)
```
create_poll(
  question: "¿Les gustaría un torneo de [JUEGO] este fin de semana?",
  answers: "¡Sí, cuenten conmigo!, Tal vez, No puedo pero me interesa",
  channel_id: CANAL_GENERAL,
  duration_h: 48,
  multiple: false
)
```

#### 1.2 Crear el evento oficial en Discord
```
create_event(
  name: "🏆 Torneo de [JUEGO]",
  start_time: "2025-07-20T18:00:00",
  end_time:   "2025-07-20T22:00:00",
  description: "¡El evento más esperado del mes!\n\n📋 Reglas:\n• [REGLA 1]\n• [REGLA 2]\n\n🎁 Premios:\n• 1er lugar: [PREMIO]\n\n¡Únete al evento para recibir recordatorio automático!",
  voice_channel_id: "ID_CANAL_VOZ"
)
```

#### 1.3 Anuncio oficial
```
send_embed(
  channel_id: CANAL_ANUNCIOS,
  title: "📅 [NOMBRE DEL EVENTO]",
  description: "[DESCRIPCIÓN ATRACTIVA DEL EVENTO]\n\nHaz clic en el evento del servidor para activar el recordatorio. 🔔",
  color: "#A855F7",
  fields_json: [
    {"name": "📅 Fecha", "value": "[DÍA, DD de MES]", "inline": true},
    {"name": "⏰ Hora", "value": "[HORA] UTC", "inline": true},
    {"name": "📍 Dónde", "value": "<#CANAL_VOZ> / [PLATAFORMA]", "inline": true},
    {"name": "🎁 Premio", "value": "[PREMIO O N/A]", "inline": true},
    {"name": "👥 Cupos", "value": "[N] participantes máx.", "inline": true},
    {"name": "📋 Inscripción", "value": "Reacciona con ✅ para inscribirte", "inline": false}
  ],
  thumbnail_url: "[URL_IMAGEN_OPCIONAL]",
  timestamp: true
)
```

---

### Fase 2 — Preparación (día anterior)

#### 2.1 Recordatorio
```
send_embed(
  channel_id: CANAL_EVENTOS,
  title: "⏰ Recordatorio: [EVENTO] ¡Mañana!",
  description: "El evento es **mañana a las [HORA] UTC**.\n¿Estás listo/a?",
  color: "#F59E0B",
  timestamp: true
)
```

#### 2.2 Mensaje programado para el día del evento
```
schedule_message(
  channel_id: CANAL_EVENTOS,
  content: "🔴 **[EVENTO] empieza en 30 minutos.** ¡Conéctate a <#CANAL_VOZ>! @here",
  delay_minutes: [MINUTOS_HASTA_30_ANTES_DEL_EVENTO]
)
```

---

### Fase 3 — Día del evento

#### 3.1 Mensaje de inicio
```
send_embed(
  channel_id: CANAL_GENERAL,
  title: "🟢 ¡[EVENTO] ha comenzado!",
  description: "El evento está en marcha. ¡Únete ahora en <#CANAL_VOZ>!",
  color: "#57F287",
  ping_everyone: false,
  timestamp: true
)
```

#### 3.2 Ajustar el canal de voz si hay mucho ruido
```
set_slowmode(seconds: 15, channel_id: CANAL_CHAT_EVENTO)
```

---

### Fase 4 — Post-evento

#### 4.1 Anuncio de resultados
```
send_embed(
  channel_id: CANAL_ANUNCIOS,
  title: "🏆 Resultados: [NOMBRE DEL EVENTO]",
  description: "¡El evento ha concluido! Felicitaciones a todos los participantes.",
  color: "#F59E0B",
  fields_json: [
    {"name": "🥇 1er Lugar", "value": "[GANADOR]", "inline": true},
    {"name": "🥈 2do Lugar", "value": "[GANADOR]", "inline": true},
    {"name": "🥉 3er Lugar", "value": "[GANADOR]", "inline": true},
    {"name": "📊 Participantes totales", "value": "[N]", "inline": true},
    {"name": "⏱️ Duración", "value": "[X] horas", "inline": true}
  ],
  timestamp: true
)
```

#### 4.2 Asignar rol de ganador (si existe)
```
assign_role(user_id: ID_GANADOR, role_id: ROL_CAMPEON)
```

#### 4.3 Eliminar el evento de Discord
```
delete_event(event_id: ID_EVENTO)
```

---

## CALENDARIO DE EVENTOS (MENSUAL)

Para planificar un mes completo, usa esta estructura:

```
Semana 1: Evento casual (ej: noche de juegos libre)
Semana 2: Torneo/competencia
Semana 3: Evento social (karaoke, trivia, etc.)
Semana 4: Evento especial/mensual (mayor escala)
```

Crea todos los eventos de Discord de una vez al inicio del mes para que los miembros puedan marcarlos en su calendario.

---

## TIPOS DE EVENTOS POR CATEGORÍA

### Eventos de gaming
- Torneos 1v1, 2v2, Battle Royale
- Noches de juegos cooperativos
- Retos de speedrun
- Watch parties de torneos (ej: Worlds, Major)

### Eventos sociales
- Noche de trivia temática
- Karaoke (compartir pantalla + YouTube)
- Movie night (watch2gether, Netflix Party)
- AMAs (ask me anything) con miembros destacados

### Eventos de contenido
- Concurso de arte/fanart
- Concurso de escritura/ficción
- Photo contest
- Meme competition

### Eventos de comunidad
- Debate temático
- Sesión de Q&A con el staff
- Game jam
- Charity stream

---

## NOTAS IMPORTANTES

⚠️ **Zona horaria:** Discord muestra los eventos en la hora local de cada usuario. Siempre especifica UTC en los anuncios para evitar confusiones.

⚠️ **`start_time` formato:** Debe ser ISO 8601: `"2025-07-20T18:00:00"` (sin zona horaria = UTC).

⚠️ **Eventos externos vs. voz:** Si el evento es un stream externo, usa `location` con la URL. Si es dentro de Discord, usa `voice_channel_id`.

⚠️ **Cancelaciones:** Si necesitas cancelar, usa `delete_event` y notifica con `send_embed` inmediatamente.
