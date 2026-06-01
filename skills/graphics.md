# SKILL: graphics

> Generación de gráficos SVG con estética Youkai (cyberpunk minimalista).

## REGLAS BÁSICAS

1. **Usa siempre `render_template`**. Es ~50ms vs 20-45s del LLM puro.
2. **Para avatares**: llama `batch_user_lookup(names="X,Y", context="basic")` PRIMERO. Usa la `avatar_url` que devuelve, nunca inventes URLs.
3. **Datos primero, decoración mínima**. La paleta y la voz visual ya están en los templates — solo inyectas datos limpios.
4. **No satures**. Si tienes 50 items, muestra los 10-15 más relevantes. El usuario no necesita verlo todo.

---

## TEMPLATES

### `tierlist` — Rankings S/A/B/C/D/F
Colores automáticos por tier: S=rojo, A=amarillo, B=verde, C=cyan, D=gris, F=oscuro.
```json
{
  "title": "Mejores agentes",
  "subtitle": "ZZZ Tier List",
  "tiers": [
    {"label": "S", "entries": [{"name": "Miyabi", "avatar_url": "..."}, {"name": "Yanagi"}]},
    {"label": "A", "entries": [{"name": "Zhu Yuan"}]},
    {"label": "B", "entries": [{"name": "Anton"}]}
  ]
}
```

### `leaderboard` — Ranking numérico con barras
Top 3 destacados (rojo/amarillo/cyan), resto en gris.
```json
{
  "title": "Top mensajes",
  "period": "Histórico",
  "rows": [
    {"rank": 1, "name": "Aris", "value": 12450, "avatar_url": "...", "detail": "muy activo"},
    {"rank": 2, "name": "Cisart", "value": 8230, "avatar_url": "..."},
    {"rank": 3, "name": "Xoft", "value": 5120}
  ]
}
```

### `bar_chart` — Barras verticales
```json
{"title": "Actividad por canal", "bars": [{"label": "general", "value": 892}, {"label": "off-topic", "value": 654}]}
```

### `stat_grid` — Grid de stats con tendencias
Trends "+X" verde, "-X" rojo, neutros amarillo.
```json
{
  "title": "Server stats",
  "stats": [
    {"icon": "👥", "label": "Miembros", "value": "1247", "trend": "+12"},
    {"icon": "💬", "label": "Mensajes", "value": "45.2k", "trend": "+2.1k"}
  ]
}
```

### `donut_chart` — Distribución porcentual
Colores automáticos si no especificas.
```json
{
  "title": "Distribución",
  "segments": [
    {"label": "DPS", "value": 42},
    {"label": "Support", "value": 28},
    {"label": "Tank", "value": 30}
  ],
  "center_text": "100",
  "center_label": "TOTAL"
}
```

### `radar_chart` — 6 ejes hexagonales
```json
{
  "title": "Skills",
  "axes": [
    {"label": "Ataque", "value": 85, "max": 100},
    {"label": "Defensa", "value": 60, "max": 100},
    {"label": "Velocidad", "value": 90, "max": 100},
    {"label": "Inteligencia", "value": 70, "max": 100},
    {"label": "Carisma", "value": 45, "max": 100},
    {"label": "Suerte", "value": 30, "max": 100}
  ]
}
```

### `comparison` — Lado a lado (rojo vs cyan)
```json
{
  "title": "Aris vs Cisart",
  "left": {"name": "Aris", "stats": [{"label": "ATK", "value": 85}, {"label": "DEF", "value": 70}]},
  "right": {"name": "Cisart", "stats": [{"label": "ATK", "value": 78}, {"label": "DEF", "value": 90}]}
}
```

### `profile_card` — Tarjeta de usuario
```json
{
  "name": "Youkai",
  "avatar_url": "...",
  "badge": "MOD",
  "tag_role": "Hollow Ops",
  "level": 42,
  "xp_current": 8750,
  "xp_total": 10000,
  "stats": [{"label": "Mensajes", "value": "12.4k"}, {"label": "Reacciones", "value": "3.2k"}]
}
```

### `banner` — Anuncio destacado
```json
{
  "badge": "EVENTO",
  "icon": "🏆",
  "title": "TORNEO SEMANAL",
  "subtitle": "Inscripciones hasta el viernes",
  "details": "Premio: Rol exclusivo + 50k coins"
}
```

### `timeline` — Línea horizontal con eventos alternados
```json
{
  "title": "Línea de tiempo",
  "events": [
    {"date": "ene 15", "title": "Inicio", "description": "Empezó todo", "icon": "🌟"},
    {"date": "feb 3", "title": "Cambio", "description": "Algo pasó"},
    {"date": "mar 10", "title": "Fin", "description": "Y terminó"}
  ]
}
```

### `investigation_timeline` — Vertical, estilo case file
Para reportes de investigación, warns acumulados, etc.
```json
{
  "title": "Caso: Aris",
  "subtitle": "Análisis de comportamiento",
  "events": [
    {"date": "2026-03-15", "title": "Primer warn", "description": "Spam en general", "icon": "⚠️"},
    {"date": "2026-04-01", "title": "Mute 1h", "description": "Reincidencia", "icon": "🔒", "color": "#FFD60A"}
  ]
}
```

### `heatmap` — Días × horas
```json
{
  "title": "Actividad semanal",
  "day_labels": ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"],
  "hour_labels": ["0h","4h","8h","12h","16h","20h"],
  "data": [[5,2,8,15,30,45], [3,1,5,12,25,50], ...]
}
```

### `achievement_card` — Logro
```json
{"icon": "🔪", "title": "Primera Sangre", "description": "Baneaste a tu primer usuario", "date": "2026-04-27", "progress": {"current": 1, "total": 1}}
```

### `graph_network` — Red social (auto layout circular)
```json
{
  "title": "Red social",
  "nodes": [
    {"name": "Aris", "msg_count": 500, "avatar_url": "..."},
    {"name": "Cisart", "msg_count": 300}
  ],
  "edges": [{"source": 0, "target": 1, "weight": 85}]
}
```

### `correlation_matrix` — N×N (positivos rojos/amarillos, negativos cyan)
```json
{
  "title": "Correlaciones",
  "users": [{"name": "Aris"}, {"name": "Cisart"}, {"name": "Xoft"}],
  "matrix": [[1.0, 0.45, -0.12], [0.45, 1.0, 0.67], [-0.12, 0.67, 1.0]]
}
```

### `love_graph` — Conexiones románticas (2-4 personas)
```json
{
  "title": "💕 Connection",
  "ships": [
    {"name": "Aris", "avatar_url": "..."},
    {"name": "Cisart", "avatar_url": "..."}
  ]
}
```

---

## FLUJO ESTÁNDAR

```
[Usuario pide gráfico]
   ↓
1. Si involucra usuarios → batch_user_lookup(names="A,B,C", context="basic")
   ↓ avatar_url, display_name
2. Construir el JSON minimalista (solo lo esencial)
   ↓
3. render_template(template="X", data="<json>", channel_id="...")
```

NO inventes datos. NO satures con 50 items. NO uses gradientes/colores fuera de la paleta — los templates ya tienen la estética correcta.
