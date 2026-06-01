# SKILL: data_mastery
> Motor de recuperación inteligente de datos. Lee TODA esta skill antes de ejecutar cualquier consulta compleja.

---

## 1. FILOSOFÍA — piensa antes de llamar

Las tools de datos son costosas. Antes de lanzar cualquier llamada, responde estas 3 preguntas:

1. **¿Qué tipo de pregunta es?** (ver §2 — tabla de decisión)
2. **¿Cuánto volumen espero?** (ver §3 — gestión de escala)
3. **¿Puedo responderlo con una sola query, o necesito encadenar?** (ver §4 — cadenas)

Nunca hagas búsquedas brutas de 168h con limit=50 y esperes que el resultado sea representativo. No lo es.

### La Regla de Oro de la Investigación (Rigor y Alma)
> [!IMPORTANT]
> **Toda investigación o análisis social debe combinar de forma obligatoria y balanceada datos cuantitativos y cualitativos:**
> * **El Rigor (Datos Cuantitativos):** Muestra números, porcentajes, tendencias y rankings para demostrar escala y patrones generales (usando `aggregate_messages`, `get_leaderboard`, etc.).
> * **El Alma (Datos Cualitativos):** Ilustra cada métrica o conclusión con evidencia empírica directa de los usuarios. Busca mensajes reales (`search_messages_semantic`) y extrae hilos cronológicos completos (`get_message_context` con 100 mensajes anteriores/posteriores) para citar las palabras textuales de las personas.
> 
> *Un análisis compuesto únicamente por números y estadísticas desnudas carece de precisión social y humana; un análisis compuesto únicamente por opiniones sin datos carece de solidez. NUNCA presentes listas de números solas sin acompañarlas de citas textuales ilustrativas.*

---

## 2. TABLA DE DECISIÓN — qué tool usar

| Tipo de pregunta | Tool principal | Tools de apoyo |
|---|---|---|
| "¿Qué dijo X sobre Y?" | `search_messages_semantic` | `get_user_timeline` |
| "¿Quién habló de Y?" | `search_messages_semantic` | `get_server_activity` |
| "¿Qué pasó antes o después de un mensaje clave?" | `get_message_context` | `search_messages_semantic` |
| "¿Cuántos mensajes por día esta semana?" | `aggregate_messages` | — |
| "¿A qué horas está activo el servidor?" | `get_peak_hours` | `aggregate_messages` |
| "Top usuarios del mes" | `aggregate_messages` (group_by=user) | `get_leaderboard` |
| "Historia completa de un usuario" | `get_user_timeline` | `get_user_card` |
| "¿Qué pasó ayer a las 10pm?" | `aggregate_messages` (rango absoluto) | `paginate_messages` |
| "Mensajes que suenan a raid" | `search_messages_semantic` | `antiraid_scan` |
| "¿Cuántos warns/bans en el último mes?" | `aggregate_messages` (type=audit) | `get_infractions_summary` |
| "Dame todos los mensajes de #canal" | `paginate_messages` | — |
| "¿Quiénes suelen hablar juntos?" | `query_pattern_analysis` (mode=cooccurrence) | `compare_user_activity` |
| "Contexto de una conversación" | `get_message_context` | `paginate_messages` |

---

## 3. GESTIÓN DE ESCALA

### Regla de oro: nunca pidas más de lo que puedes procesar

- **< 200 mensajes esperados**: una sola call con `search_messages` o `search_messages_semantic`
- **200–2000 mensajes**: usa `aggregate_messages` para obtener estadísticas directamente en SQL (no traigas los mensajes raw)
- **> 2000 mensajes o períodos > 7 días**: usa `paginate_messages` con offset, procesa en lotes de 100, y agrega los resultados tú mismo

### Ventanas de tiempo inteligentes

NO hagas esto:
```
search_messages(hours=720, limit=50)  # 30 días truncados a 50 = basura
```

SÍ haz esto para análisis de 30 días:
```
aggregate_messages(
  group_by="day",
  start_ts="2025-03-01T00:00:00",
  end_ts="2025-03-31T23:59:59"
)
```

O si necesitas mensajes reales, pagina:
```
paginate_messages(hours=720, limit=100, offset=0)   # lote 1
paginate_messages(hours=720, limit=100, offset=100) # lote 2
... hasta que count < limit
```

---

## 4. CADENAS DE CONSULTA — patrones inteligentes

### Patrón A: "Identifica y profundiza"
Ideal para: encontrar usuarios relevantes y luego investigarlos
```
1. get_server_activity(hours=168)           → identifica top usuarios
2. get_user_timeline(user_id=X, days=7)    → profundiza en el más relevante
3. get_user_card(user_id=X)                → contexto de personalidad
```

### Patrón A2: "Análisis profundo de un usuario"
Ideal para: entender a fondo cómo habla, qué temas toca, su personalidad
```
1. paginate_messages(user_id=X, hours=8760, limit=100, offset=0, order="desc")
2. paginate_messages(user_id=X, hours=8760, limit=100, offset=100, order="desc")
   ... hasta 1000 mensajes (10 lotes) o hasta que count < 100
3. Analiza: tono, temas recurrentes, horarios, relaciones, vocabulario
```
Usa esto cuando pidan "analiza a X", "cómo es X", "qué tipo de persona es X".
1000 mensajes dan suficiente contexto para un perfil completo.

### Patrón B: "Semántico + confirmación"
Ideal para: buscar un concepto y verificar con datos duros
```
1. search_messages_semantic(query="pelea entre usuarios", hours=48)
   → encuentra mensajes relevantes semánticamente
2. aggregate_messages(user_id=X, group_by="hour", hours=48)
   → confirma si hubo spike de actividad en esa ventana
```

### Patrón C: "Agregado + muestra"
Ideal para: reportes donde necesitas stats + ejemplos concretos
```
1. aggregate_messages(group_by="user", hours=168)
   → obtén el ranking con conteos reales
2. search_messages(user_id=top_user, hours=168, limit=10)
   → obtén muestra de mensajes para contextualizar
```

### Patrón D: "Timeline de incidente"
Ideal para: reconstruir qué pasó exactamente
```
1. aggregate_messages(group_by="hour", start_ts=..., end_ts=...)
   → identifica la hora de mayor actividad
2. paginate_messages(channel_id=X, start_ts=hora_pico, limit=50)
   → lee los mensajes en orden cronológico
3. get_user_timeline(user_id=sospechoso, days=1)
   → cruza con historial del usuario
```

### Patrón E: "Búsqueda + Extracción de Contexto" (RECOMENDADO para investigación)
Ideal para: cuando se busca un tema o usuario y se quiere ver la conversación real circundante.
```
1. search_messages_semantic(query="tensión o pelea", hours=72)
   → encuentra mensajes relevantes del incidente.
2. get_message_context(message_id="ID_ENCONTRADO", before_limit=100, after_limit=100)
   → extrae el contexto exacto (100 anteriores, 100 posteriores y el central) para leer la discusión real.
```

---

## 5. BÚSQUEDA SEMÁNTICA — cómo usarla bien

`search_messages_semantic` usa búsqueda híbrida (FTS5 + embeddings + RRF). Es más inteligente que `search_messages` pero más lenta. Úsala cuando:

- La pregunta es conceptual ("mensajes agresivos", "usuarios que piden ayuda")
- No conoces las palabras exactas que usó el usuario
- Quieres ranking por relevancia real, no por fecha

**Parámetros clave:**
- `query`: escribe en lenguaje natural, como harías en Google. No uses operadores booleanos.
  **IMPORTANTE:** NUNCA pongas el nombre del usuario en la query. Usa `user_id` para filtrar por usuario.
  ❌ `query="Pepito opiniones sobre juegos"` → busca la palabra "Pepito" en mensajes de todos
  ✅ `query="opiniones sobre juegos", user_id="123456"` → busca semánticamente en mensajes de Pepito
- `semantic_weight` (0.0–1.0): 0.0 = solo FTS5/BM25, 1.0 = solo semántico, 0.5 = híbrido (recomendado)
- `hours`: ventana de tiempo. Para semántica, 72-168h es el sweet spot. Más de 7 días puede traer ruido.
- `min_score`: filtra resultados de baja relevancia. Empieza con 0.3, sube si hay mucho ruido.

**Ejemplo correcto:**
```
search_messages_semantic(
  query="usuarios discutiendo o insultándose",
  hours=48,
  limit=20,
  semantic_weight=0.6,
  min_score=0.35
)
```

---

## 5b. EXTRACCIÓN DE CONTEXTO — `get_message_context` (CRÍTICO)

La herramienta `get_message_context` es tu arma principal para la investigación cualitativa profunda. Cuando ejecutas búsquedas (ya sea `search_messages` o `search_messages_semantic`), obtienes fragmentos aislados que carecen del flujo real de la conversación.

### Recomendación Obligatoria de Investigación:
> [!IMPORTANT]
> **RECOMIENDA E INVOCA ESTA HERRAMIENTA SIEMPRE QUE:**
> 1. Realices una búsqueda de mensajes y encuentres uno o varios resultados relevantes.
> 2. Quieras entender qué causó una discusión o qué pasó inmediatamente después.
> 3. El usuario te pida investigar un incidente o conversación del pasado.
> 
> **Cómo recomendarla en el chat:** Siempre que muestres resultados de búsquedas al usuario, añade una nota recomendando el uso de esta herramienta para expandir el contexto: *"Para ver la conversación completa que rodea a este mensaje, puedo usar la herramienta de contexto `get_message_context` con el ID `XXX` y recuperar 100/150 mensajes anteriores y posteriores."*

### Parámetros Clave:
- `message_id`: El ID del mensaje que sirve como punto de referencia.
- `before_limit`: Cantidad de mensajes anteriores en el mismo canal (default: 150. **Recomendado: 100**).
- `after_limit`: Cantidad de mensajes posteriores en el mismo canal (default: 150. **Recomendado: 100**).

### Ejemplo de uso recomendado:
```
get_message_context(
  message_id="1234567890",
  before_limit=100,
  after_limit=100
)
```
Esto recupera exactamente 100 mensajes anteriores, 100 posteriores y el mensaje objetivo (201 mensajes en total en orden cronológico), lo cual es ideal para una visualización sumamente nítida sin saturar el contexto del modelo.

---

## 6. AGGREGACIONES — sintaxis de `aggregate_messages`

Esta tool ejecuta GROUP BY directamente en SQL. Es la forma más eficiente de obtener estadísticas.

### Modos disponibles:

**Por día (trend de actividad)**
```json
{
  "group_by": "day",
  "hours": 168
}
```

**Por usuario (leaderboard preciso)**
```json
{
  "group_by": "user",
  "hours": 720,
  "limit": 20
}
```

**Por canal (qué canales están activos)**
```json
{
  "group_by": "channel",
  "hours": 24
}
```

**Por hora del día (patrón circadiano)**
```json
{
  "group_by": "hour_of_day",
  "hours": 720
}
```

**Rango absoluto (análisis de período específico)**
```json
{
  "group_by": "day",
  "start_ts": "2025-04-01T00:00:00",
  "end_ts": "2025-04-15T23:59:59"
}
```

**Audit log (infracciones)**
```json
{
  "agg_type": "audit",
  "group_by": "action",
  "hours": 720
}
```

---

## 7. PAGINACIÓN — cuándo y cómo

Usa `paginate_messages` cuando necesitas los mensajes raw (no solo estadísticas) de un volumen grande.

```
# Protocolo de paginación completa:
offset = 0
todos_los_mensajes = []

loop:
  lote = paginate_messages(
    channel_id=X,     # o user_id=X, o solo guild_id
    hours=720,
    limit=100,
    offset=offset,
    order="asc"       # "asc" para cronológico, "desc" para más recientes
  )
  
  todos_los_mensajes += lote.messages
  
  if lote.count < 100:
    break  # último lote
  
  offset += 100

# IMPORTANTE: No pagines más de 5 lotes (500 mensajes) sin agregar/resumir.
# Si el dataset es más grande, usa aggregate_messages en su lugar.
```

---

## 8. ANÁLISIS DE PATRONES — `query_pattern_analysis`

Tool especializada para detectar patrones no obvios.

### Modos:

**Co-ocurrencia** (¿quiénes hablan en los mismos canales/momentos?)
```json
{
  "mode": "cooccurrence",
  "hours": 168,
  "min_overlap": 3
}
```
→ Devuelve pares de usuarios con alta co-ocurrencia. Útil para detectar grupos, relaciones o coordinación.

**Anomalías temporales** (¿hubo spikes de actividad inusuales?)
```json
{
  "mode": "anomaly",
  "hours": 168,
  "sensitivity": 2.0
}
```
→ Usa z-score por hora. `sensitivity` = número de desviaciones estándar para considerar anomalía.

**Usuarios silenciados repentinamente** (¿alguien dejó de hablar de golpe?)
```json
{
  "mode": "sudden_silence",
  "days": 7,
  "min_previous_messages": 10
}
```

---

## 9. LÍMITES Y GUARDARRAÍLES

- **Nunca uses `search_messages` con `limit=50` y `hours > 72`** como única fuente de verdad para análisis cuantitativos. Siempre complementa con `aggregate_messages`.
- **Embeddings tienen latencia**: `search_messages_semantic` tarda ~2-5x más que `search_messages`. Úsala solo cuando la relevancia semántica importa.
- **El modelo de embeddings del bot** es el mismo `EmbedEngine` ya configurado. Si `embedder.available == False`, `search_messages_semantic` fallback automáticamente a FTS5 puro.
- **Máximo de paginación recomendado**: 10 lotes (1000 mensajes). Si necesitas más, reporta un resumen estadístico en lugar de leer todos los mensajes.

---

## 10. EJEMPLO COMPLETO — "¿Qué pasó en el servidor esta semana?"

```
PASO 1: Vista panorámica
→ aggregate_messages(group_by="day", hours=168)
  Lee: ¿qué días tuvieron más actividad?

PASO 2: Protagonistas
→ aggregate_messages(group_by="user", hours=168, limit=10)
  Lee: top 10 usuarios de la semana

PASO 3: Canales calientes
→ aggregate_messages(group_by="channel", hours=168)
  Lee: ¿dónde se concentró la actividad?

PASO 4: Incidencias (si las hubo)
→ aggregate_messages(agg_type="audit", group_by="action", hours=168)
  Lee: bans, kicks, warns de la semana

PASO 5: Contexto cualitativo (solo si hay algo notable en pasos anteriores)
→ search_messages_semantic(query="conflictos, tensión o problemas", hours=168, limit=15)
  Lee: muestra de mensajes relevantes para entender el tono

PASO 6: Síntesis
→ Presenta: resumen ejecutivo con datos del paso 1-4 + ejemplos del paso 5
```

---

*Esta skill es parte del sistema Fairy Agent. Versión: 1.0*
