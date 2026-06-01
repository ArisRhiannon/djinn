# Skill: Banco / Tesorería (Y O U K A I · B A N K)

## El sistema económico

Cada servidor tiene una **tesorería** (banco/pool) que arranca con **6,000 créditos** (bootstrap inicial al primer acceso).

### Flujo del dinero

```
                 ┌──────────────────┐
                 │  POOL del BANCO  │
                 │  Y O U K A I     │
                 └────────┬─────────┘
                          │
       Préstamo otorgado  │  Cuota cobrada
       /banco entregar    │  Default (pérdida)
       /créditos dar      │
                          ▼
                 ┌──────────────────┐
                 │     USUARIO       │
                 │   user_credits    │
                 └──────────────────┘
```

- **Préstamos otorgados** salen del pool (`balance -= principal`).
- **Cuotas pagadas** vuelven al pool (`balance += amount`, incluye intereses).
- **Defaults**: el remanente se pierde (registrado en `total_lost_defaults`).
- **Staff** puede entregar (`/banco entregar`) o depositar (`/banco depositar`).
- **Atajo `/créditos dar`**: solo Aris/Cisart, max 1,200 cr, también debita del pool.

### Estados del banco

| Balance | Etiqueta | Comportamiento |
|---------|----------|----------------|
| < 600 | 🔴 critical | No se prestan ni los más chicos |
| 600-1499 | 🟠 low | Solo préstamos chicos (tier 1) |
| 1500-2999 | 🟡 stable | Chicos y medianos disponibles |
| ≥ 3000 | 🟢 healthy | Todos los tiers disponibles |

Si un usuario pide préstamo y no hay fondos, **se rechaza** y no se crea deuda.

---

## Tools dedicadas

### `get_treasury_balance` — Estado actual del banco

Devuelve:
- `summary`: frase humana que ya integra balance + estado + nota operativa (úsala como base para responder)
- `balance`: cuánto hay en caja AHORA
- `outstanding_debt`: préstamos activos (capital pendiente)
- `bootstrap_amount`: capital inicial (informativo)
- `total_collected`: cuotas cobradas + depósitos staff (acumulado)
- `total_disbursed`: préstamos otorgados + grants staff (acumulado)
- `total_lost_defaults`: pérdidas por defaults (acumulado)
- `operating_result` = `total_collected - total_disbursed` (resultado de operaciones; positivo = banco gana en intereses)
- `net_profit`: alias retrocompat de `operating_result`
- `health`: "critical" | "low" | "stable" | "healthy"
- `breakdown`: top movimientos por volumen (suma agrupada por razón)

Úsala cuando pregunten: "cómo va el banco", "saldo del pool", "cuánto tiene Youkai", "cuánto ha ganado el banco".

### `get_treasury_history` — Movimientos recientes

Devuelve los últimos N movimientos con `amount`, `balance_after`, `reason`, `metadata`, `user_name`, `by_staff_name`, `created_at`.

Razones posibles: `bootstrap`, `loan_disbursed`, `loan_repayment`, `loan_default`, `staff_grant`, `staff_deposit`, `event_reward`.

Filtros: `reason_filter` para mostrar solo un tipo.

### `treasury_grant_credits` — STAFF ONLY
Entrega créditos del pool a un usuario. **Requiere `manage_guild`**. Si no hay fondos, falla. Genera movimiento `staff_grant`.

### `treasury_deposit` — STAFF ONLY
Ingresa créditos al pool. **Requiere `manage_guild`**.

---

## Slash commands

### `/banco`

| Comando | Permiso | Qué hace |
|---------|---------|----------|
| `/banco saldo` | público | Embed con estado completo del banco |
| `/banco entregar @user monto razón` | manage_guild | Entrega del pool a un usuario |
| `/banco depositar monto razón` | manage_guild | Ingresa al pool |
| `/banco historial [limit]` | público | Movimientos recientes |

### `/créditos dar`

| Comando | Permiso | Qué hace |
|---------|---------|----------|
| `/créditos @user monto [razón]` | Aris/Cisart hardcoded | Atajo: entrega del pool, max 1,200 cr |

> **Nota**: ya **NO existe `/créditos quitar`**. Para sustraer créditos a un usuario sin moverlos al banco, no hay slash directo (era una funcionalidad rara que se quitó porque no salía/entraba a ningún lado coherente).

---

## Cómo formatear un embed del banco

Si Youkai necesita responder con un embed manual (alternativa al `/banco saldo` directo), seguir este formato:

```
embed:
  title: "🏦 Y O U K A I · B A N K"
  color: 0x2A9D8F  # turquesa cuando saludable. 0xE63946 si crítico, 0xF77F00 si bajo
  description: |
    ```
    💰 En caja AHORA       4,250 cr
    🏃 Prestado afuera     1,840 cr
    🏗️ Capital inicial     6,000 cr
    ```
  fields:
    - name: "Estado · 🟢 Saludable"
      value: "Todos los tiers de préstamo disponibles"
      inline: false
    - name: "Histórico de operaciones"
      value: |
        ```
        📥 Cuotas cobradas       +2,140
        📤 Préstamos otorgados   -3,900
        💀 Pérdidas (defaults)        0
        ───────────────────────────────
        📊 Resultado operativo   -1,760
        ```
      inline: false
    - name: "Lectura"
      value: "⏳ El banco está en negativo de operación — hay préstamos vivos cuyas cuotas todavía no terminaron de volver."
      inline: false
  footer: "Pool del servidor"
```

Reglas de claridad:
- **"En caja"** = balance disponible. Lo que el banco puede prestar AHORA.
- **"Prestado afuera"** = capital pendiente de cobro (préstamos activos).
- **"Capital inicial"** = el bootstrap, valor histórico, no se restablece.
- **"Resultado operativo"** = cuotas - préstamos otorgados. Positivo = banco gana intereses. Negativo = más prestado de lo cobrado (todavía).
- NO mezclar bootstrap con operaciones — son cosas distintas (capital vs P&L).

---

## Patrones de uso

### "¿Cómo va el banco?" / "Cuánto tiene Youkai"
```
get_treasury_balance() → usar `summary` + `breakdown` para el comentario
```

### "Movimientos del banco"
```
get_treasury_history(limit=15) → lista cronológica
```

### "Solo los préstamos otorgados últimos"
```
get_treasury_history(limit=10, reason_filter="loan_disbursed")
```

### Staff: "Dale 500 a Karu por ganar el evento"
```
[verifica permission_check primero]
get_user_by_name("Karu") → uid
treasury_grant_credits(uid, 500, "Premio Halloween 2025") → confirmación
```

### Staff: "Pon 3000 al banco como recompensa por X"
```
treasury_deposit(3000, "Bonus mensual del staff")
```

---

## Notas / reglas

- **Nunca** ofrezcas perdonar deudas modificando scores — eso es automático.
- **Nunca** llames `treasury_grant_credits` o `treasury_deposit` sin permission check (el dispatcher rechaza si el usuario no tiene `manage_guild`).
- Si el banco está en `health: critical`, mencionalo — alguien tiene que pagar para reabrir el flujo.
- Para `staff_grant`, **siempre** pedí una `reason` clara — queda en el historial permanente.
- Si `outstanding_debt > balance` el banco está en "deuda neta" — el servidor le debe a la economía.
- Bootstrap inicial: 6,000 cr. Está en `Database.DEFAULT_TREASURY_BOOTSTRAP`.
- `/créditos dar` es un atajo de Aris/Cisart para entregas chicas — sale del mismo pool.
