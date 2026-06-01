# Skill: Deudas (Y O U K A I · S E R V I C E S)

## Sistema de Préstamos

Youkai ofrece préstamos agiotistas a usuarios sin créditos. El interés escala según su score crediticio (0–1000).

### Tiers
| Monto | Cuotas | Score mínimo |
|-------|--------|-------------|
| 600   | 4 días | 0           |
| 1000  | 5 días | 300+        |
| 1500  | 6 días | 500+        |

### Interés
Fórmula: `tasa = 2.0 - (score / 1000) * 1.8`
- Score 1000 → 20%
- Score 500 → 110%
- Score 0 → 200%

### Score Crediticio
- Default para nuevos: 500
- Pago exitoso: +15
- Pago fallido: -40
- Préstamo pagado sin fallos: +30 bonus
- Default (3 fallos seguidos): -100
- Blacklist: score 0 + 2 defaults

### Tier labels
- 800-1000: **S**
- 600-799: **A**
- 400-599: **B**
- 200-399: **C**
- 0-199: **D**

### Cobro
Automático cada 24h. Si no puede pagar, se marca como moroso y se expone en el canal.

---

## Tools dedicadas (úsalas en este orden de preferencia)

### `list_morosos` — La tool principal para LISTADOS
Devuelve datos completos para construir tablas. Úsala SIEMPRE que pidan "morosos", "deudores", "lista de quien debe", "quién no ha pagado".

**Args:**
- `sort`: `"debt_desc"` (default), `"debt_asc"`, `"misses_desc"`, `"days_desc"`, `"score_asc"`
- `min_debt`: filtra por deuda restante mínima (default 0)
- `only_late`: `"yes"` (solo con cuotas falladas) o `"no"` (incluir al día)
- `limit`: hasta 50 (default 25)

**Devuelve por moroso:** `name`, `debt`, `principal`, `installment`, `paid/of`, `progress_pct`, `misses`, `consec_miss`, `interest_rate_pct`, `score`, `tier`, `total_loans`, `defaults`, `days_since_loan`, `hours_to_next_collection`, `blacklisted`.

### `get_user_debt` — Estado completo de UN usuario
Para "¿cuánto debe X?", "¿cómo va X?". Combina score + tier + préstamo activo en una sola llamada.

### `get_loan_leaderboard` — Rankings
**Modes:**
- `biggest_debtors` — top deudas activas
- `best_payers` — mejores scores (con préstamos)
- `worst_defaulters` — más defaults
- `top_borrowers` — más préstamos totales
- `longest_active` — deudas más antiguas

### `get_loan_stats` — Stats globales del servidor
Total activos, deuda circulante, morosos, completados, defaulteados, score promedio, blacklisted, success rate.

### `get_loan_history` — Pagos de un usuario
Últimos N cobros con éxito/fallo y balances.

### `get_loan_info` — Tool legacy (modes status/morosos/historial)
Sigue funcionando pero las nuevas tools son más ricas.

---

## Cómo formatear una TABLA de morosos (canon)

Cuando devuelvas una tabla de deudores usa **`send_embed`** con campos en formato monoespaciado dentro de un bloque de código. Esto fuerza la alineación.

### Ejemplo (5 morosos)

```
embed:
  title: "🩸 Wall of Shame · Morosos del Servidor"
  color: 0xE63946
  description: |
    ```
    Usuario              Deuda    Cuota   Pagado    Score  Días
    ──────────────────  ──────   ─────   ──────   ─────  ────
    Karu (Tupu)          1,234    309    1/4 ❌     420(B)   3
    Xokram                 850    213    2/5 ❌     580(B)   5
    Aris                   600    150    0/4 ❌❌    180(D)   2
    Daraziel               420    105    3/4 ✓      720(A)   4
    Papu                   180     45    3/5 ❌     290(C)   6
    ```
  fields:
    - name: "📊 Total"
      value: "5 morosos · 3,284 créditos"
      inline: true
    - name: "💀 Score promedio"
      value: "438 (tier B-)"
      inline: true
    - name: "⏰ Próximos cobros"
      value: "todos en menos de 24h"
      inline: true
  footer: "Datos en tiempo real · /deuda para ver tu estado"
```

**Reglas para la tabla:**
- Usa monoespacio (\`\`\`...\`\`\`) para alinear columnas — Discord respeta el código
- Truncar nombres a 18 caracteres
- Símbolos: ✓ pagó al día, ❌ falla actual, ❌❌ doble fallo (cerca de default), 🚫 blacklisted
- Orden por defecto: deuda descendente
- Si hay 0 morosos: embed verde con mensaje positivo "Servidor al día — nadie debe."

---

## Patrones de uso típicos

### "Lístame a los deudores"
```
list_morosos(sort="debt_desc", only_late="yes", limit=25)
→ send_embed con tabla
```

### "¿Cuánto debe Karu?"
```
get_user_by_name("Karu") → user_id
get_user_debt(user_id) → embed con score + active_loan + tier
```

### "Mi deuda" / "¿cuánto debo?"
Ya tienes el `user_id` del que pregunta en el contexto.
```
get_user_debt(user_id=<quien pregunta>) → embed
```
También recomendá `/deuda` para detalle completo.

### "Top 10 deudores"
```
get_loan_leaderboard(mode="biggest_debtors", limit=10)
```

### "Wall of shame" / "peores defaulters"
```
get_loan_leaderboard(mode="worst_defaulters", limit=10)
```

### "Buenos pagadores" / "quiénes pagan bien"
```
get_loan_leaderboard(mode="best_payers", limit=10)
```

### "¿Cómo va el banco?"
```
get_loan_stats() → embed con totales
```

### "Historial de pagos de X"
```
get_user_by_name("X") → uid
get_loan_history(uid, limit=15)
```

---

## Notas

- El préstamo se ofrece automáticamente con botón cuando un usuario no tiene créditos (no necesitas ofrecerlo tú)
- `/deuda` es el slash command para que el usuario vea su propio estado crediticio
- **No puedes perdonar deudas ni modificar scores** — eso es automático del sistema
- Si preguntan cómo subir su score: "paga a tiempo"
- Si nadie debe: respondé positivo, no inventes deudores
- Resolver nombres con `get_user_by_name` ANTES de llamar a las tools que requieren `user_id`
