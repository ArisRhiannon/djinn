# Changelog

Todos los cambios notables del proyecto. El formato sigue [Keep a Changelog](https://keepachangelog.com/),
y la versión sigue [SemVer](https://semver.org/) cuando aplica.

---

## [unreleased] — Sesión 2026-05-15 → 2026-05-16

### 🚨 Security

- **Token leak en logs (CRÍTICO)** — Loguru estaba con `diagnose=True`/`backtrace=True`
  por default, lo que hacía que cada traceback imprimiera los **valores** de las
  variables locales. La línea `bot.run(config.discord_token, …)` exponía el token
  en cada error. **598 ocurrencias del token redactadas** en 11 archivos de log
  históricos (`fairy_2026-05-05.log` → `fairy_2026-05-15.log`). Fix permanente
  en `main.py`: `diagnose=False, backtrace=False` en ambas sinks. (Commit `30bbbef`)
- **SEC-01: `execute_code` removido** del catálogo de tools. Permitía RCE vía
  prompt injection. Sandbox basado en filtros de string es trivialmente
  bypaseable (`__class__.__mro__`, etc.). (Wave 1)
- **SEC-02: SSRF guards** en `_do_web_fetch`, `_do_fetch_url_preview`, `_do_weather`
  vía `utils.security.is_url_safe()`. (Wave 2)
- **SEC-03: API key fallback** `"fairy-local-dev"` reemplazado por
  `secrets.token_urlsafe(32)` con warning en logs si `FAIRY_API_KEY` no está en
  `.env`. (Wave 1)
- **SEC-04: Permission gate** por tool en `utils/security.py:TOOL_REQUIRED_PERMS`.
  Mod tools (`ban_user`, `kick_user`, etc.) requieren los permisos Discord
  correspondientes. (Wave 2)

### 🐛 Fixed (críticos)

- **Bug "continue" — loop infinito de `send_message` en pipeline público (P0)**
  — Reportado en producción por Aris (2026-05-16 04:20). Claude Sonnet 4.6 vía
  proxy llamó `send_message` **6 veces seguidas** a un simple "hola" de Law,
  alucinando que el usuario decía "continue" repetidamente entre cada llamada.

  **Causa raíz**: el loop agentic en las 3 implementaciones de
  `generate_with_tools` (GoogleLLM/OpenRouterLLM/CustomLLM) no tenía noción de
  "tool terminal". Confiaba en que el modelo decidiera no llamar más tools, pero
  Claude tiene un sesgo documentado a preferir tools sobre texto plano. Sin un
  user turn nuevo, el modelo alucinaba un "continue" implícito y volvía a llamar
  `send_message`. El loop solo terminaba al alcanzar `max_rounds`.

  **Fix de 3 capas**:
  1. **Constante `TERMINAL_TOOLS`** en `utils/llm_client.py` con
     `{send_message, send_embed, send_dm}`.
  2. **Guard en las 3 implementaciones del loop**: variable
     `terminal_already_called` que se setea tras la primera tool terminal. Si
     en un round posterior el modelo intenta otra tool terminal, el loop aborta
     con `return ""` (output ya entregado en la primera).
  3. **System prompts reforzados** (genérico, qwen y public) con regla explícita:
     *"send_message es para OTROS canales; para responder al canal actual, emite
     texto plano. Nunca llames dos tools terminales en el mismo turn."*

  **Test de regresión**: `tests/test_terminal_tools_guard.py` con 4 tests que
  reproducen el bug con mocks y verifican que el guard dispara correctamente
  (incluyendo el caso normal de get_data → send_embed → texto comentario, que
  NO debe disparar el guard).

  **Permitido**: tras una tool terminal, el modelo puede emitir UN round más
  con texto plano (comentario sobre lo enviado, ej. *"El embed ya está en el
  canal — banco sano"*). Solo se bloquea el caso de dos tools terminales
  consecutivas. (Sesión 2026-05-16 ~04:40)

### ✨ Added

- **Sistema de banco/tesorería (Y O U K A I · B A N K)** (`cogs/treasury.py`)
  con bootstrap de **6,000 cr** por servidor. Bidireccional: préstamos salen
  del pool, cuotas vuelven con interés. Defaults representan pérdida real.
  Comandos: `/banco saldo`, `/banco entregar @user monto razón`, `/banco depositar`,
  `/banco historial`. Tools para el LLM: `get_treasury_balance`, `get_treasury_history`,
  `treasury_grant_credits`, `treasury_deposit` (las dos últimas requieren
  `manage_guild`). Tablas nuevas: `guild_treasury`, `guild_treasury_movements`.
  (Commit `528dd3c`)
- **5 tools granulares de deudas**: `list_morosos`, `get_user_debt`,
  `get_loan_leaderboard`, `get_loan_stats`, `get_loan_history`. Reemplazan en
  parte la `get_loan_info` genérica. Skill `skills/deudas.md` enriquecido con
  patrones de uso y ejemplo canónico de tabla con `send_embed`. (Commit `cd15e1a`)
- **Logs Y O U K A I**: terminal rediseñada con prefijo `Y O U K A I · módulo`,
  paleta comfy no-saturada (sage/amber/coral/grey), iconos por nivel
  (`▸ INFO`, `⚠ WARNING`, `✗ ERROR`, `⛔ CRITICAL`, `· DEBUG`), supresión
  de ruido de libs (`Batches: 100%|...`, HF Hub progress, transformers verbose).
  Embeddings agregados: 1 línea cada 6 flushes, heartbeat con stats cada 66.
  (Commit `53175c0`)
- **Suite de tests pytest (80 → 104 tests)**: `test_security`, `test_safe_domains`,
  `test_circuit_breaker`, `test_metrics`, `test_db_maintenance`, `test_http_session`,
  y `test_discord_tools_contract` (24 tests blindando el contrato del refactor).
  (Commits `3b66f8c`, `f03642c`, `e0fdebc`, `2526204`)
- **CI** en GitHub Actions (`.github/workflows/ci.yml`) corre tests en cada push.
- **`db_maintenance` cog**: backup periódico + VACUUM. (Wave 3)
- **Métricas thread-safe** standalone (`utils/metrics.py`). (Wave 5)
- **Circuit breaker** standalone (`utils/circuit_breaker.py`). (Wave 1)
- **HTTP session helper** (`utils/http_session.py`) para futura migración. (Wave 7)
- **`pyproject.toml`** con config de pytest + ruff + mypy gradual. (Wave 6)

### 🔧 Changed

- **Refactor del monolito `utils/discord_tools.py`** (de 5423 → 4338 líneas, ~20% reducción).
  Extraído en 4 fases con cero riesgo, snapshot diff byte-idéntico verificado en cada paso:
  - **Fase 1** (`f03642c`): 137 declarations + helpers `_str/_int/_bool/_decl` →
    `utils/tools/_declarations.py` (1074 líneas)
  - **Fase 2** (`e0fdebc`): 5 helpers privados (`_parse_hex_color`, `_member_avatar_url`,
    `_safe_perm_name`, `_parse_duration`, `_safe_int`) → `utils/tools/_helpers.py` (59 líneas)
  - **Fase 3** (`2526204`): 6 constantes (`SKILLS_DIR`, `_PERM_CONCURRENCY`, `_DEFAULT_TOOL_TIMEOUT`,
    `_TOOL_TIMEOUTS`, `_DB_REQUIRED_TOOLS`, `_MOD_TOOLS`) + `_fix_json` →
    `utils/tools/_constants.py` (67 líneas)
  - **Fase 4** (`829e85b`): consolidación de imports + docstring del módulo
- **Wave 6**: `safe_domains.py` (165 KB de literales Python) → `data/safe_domains.json` +
  loader cacheable en `utils/safe_domains.py`. El cog viejo ahora es un shim.
- **Wave 8**: scaffolding inicial en `utils/tools/__init__.py` (split modular futuro).
- **Wave 9**: nuevo endpoint `/api/v1/metrics_x` + handler.
- **Wave 10**: tooling (pyproject + CI).

### 🐛 Fixed

- **Bug regresión introducido por Wave 6**: `cogs/automod_v2.py:20` importaba
  `from .safe_domains import _SAFE_DOMAINS` (cog ya movido a `deprecated/`).
  Migrado a `utils.safe_domains` preservando comportamiento exacto. (Commit `30bbbef`)
- **Bug A (preexistente)**: `utils/discord_tools.py` `_do_list_listeners` usaba
  función local `_safe_get` antes de definirla → NameError si `trigger_type != ""`.
  Fix: definición movida arriba del primer uso. (Commit `30bbbef`)
- **Bug B (preexistente)**: `utils/api_server.py:408` usaba `discord.__version__`
  sin `import discord` → NameError en `/api/v1/status`. Fix: import añadido. (Commit `30bbbef`)
- **Bug C (preexistente, P1)**: `utils/discord_tools.py` `_do_run_workflow` usaba
  `WORKFLOWS` sin `self.` (3 lugares) → el tool **nunca había funcionado**, fallaba
  silente porque el dispatcher tragaba la excepción. (Commit `30bbbef`)
- **Bug del refactor fase 2**: `_parse_duration()` se movió a `_helpers.py` pero
  `_DURATION_RE`, `_DURATION_SECONDS`, `_MAX_TIMEOUT_SECONDS` quedaron huérfanas
  en `discord_tools.py` → `NameError` en runtime. Pillado por nuevos tests
  runtime. Las 3 constantes se movieron junto con la función. (Commit `8e628cf`)
- **Routing**: la categoría `_TOOL_CATEGORIES["channels"]` listaba `delete_channel`
  pero está en `FORBIDDEN` (no existe). Limpiado. (Commit `6040843`)

### 🗑️ Deprecated / Movido

- `cogs/voice.py` → `deprecated/cogs_old/voice.py` (TTS por VC, disabled hace tiempo, 0 imports activos)
- `data/kadath_world_v2.json` → `deprecated/data_backups/` (124 KB sin referencias en código)
- `scripts/kadath_act3_*.py` y `kadath_act4_*.py` (6 archivos) → `deprecated/scripts_oneoff/`
  (generadores one-shot, 0 imports activos)
- `cogs/safe_domains.py` → `deprecated/cogs_old/safe_domains.py.legacy` (Wave 6)

### 📚 Documentation

- `README.md` (nuevo): overview del proyecto, stack, estructura, sistemas principales,
  cómo correr tests, API interna, env vars.
- `CHANGELOG.md` (este archivo, nuevo).
- `deprecated/README.md` (nuevo): explica qué hay en cada subcarpeta y por qué se deprecó.
- `skills/banco.md` (nuevo): protocolo del sistema de banco con ejemplo canónico.
- `skills/deudas.md` (actualizado): tools nuevas + ejemplo de tabla.

---

## Versiones previas

Antes de la sesión 2026-05-15 / 2026-05-16, el repo no tenía git inicializado ni
changelog. La línea base es el commit `78f734f chore: snapshot inicial post-Wave 1-10
review` que captura el estado pre-fixes de seguridad. Para historial anterior,
ver el `INFORME_TECNICO.md` y los reviews del agente Hermes.
