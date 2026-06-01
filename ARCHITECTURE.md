# Architecture — Fairy-Fixed Discord Bot

> Last reviewed: 2026-05-10 by Hermes Agent — architecture map + dependency analysis v3.0.0
> Prior review: 2026-05-06 v2.0.0
>
> **Addendum 2026-05-16**: cambios significativos durante la sesión de mayo 2026.
> Ver detalles en `CHANGELOG.md`. Resumen:
> - El monolito `utils/discord_tools.py` (5423 → 4338 líneas) se desagregó en
>   3 módulos hermanos en `utils/tools/`: `_declarations.py`, `_helpers.py`,
>   `_constants.py`. La clase `ToolExecutor` quedó intacta. Snapshot del
>   monolito original en `deprecated/utils_old/discord_tools_monolith.py`.
> - Sistema de banco/tesorería bidireccional implementado (`cogs/treasury.py`,
>   `/banco` slash group). Tablas nuevas: `guild_treasury`, `guild_treasury_movements`.
> - 5 tools nuevas para deudas (`list_morosos`, `get_user_debt`, `get_loan_leaderboard`,
>   `get_loan_stats`, `get_loan_history`) + 4 para treasury.
> - Logger custom Y O U K A I, ruido de libs suprimido.
> - 4 bugs latentes pre-existentes corregidos (NameError en `_safe_get`,
>   `discord.__version__`, `WORKFLOWS`, automod_v2 import roto).
> - Token leak en logs corregido y 598 ocurrencias redactadas en archivos históricos.
> - Suite de tests pytest expandida de 80 → 104 (incluye 24 tests del contrato
>   de discord_tools).

## Overview

Fairy-Fixed is a 21K+ LOC Discord bot with AI agent capabilities. It features conversational AI via Google AI Studio (Gemma 4), tournament system with SVG rendering, automod with risk scoring, hybrid RAG search (vector + FTS5), social graph analysis, text adventure engine (Dream-Quest of Unknown Kadath), curse/mouthwash systems, media guard (image similarity detection), and model hot-switching. Built on discord.py with SQLite + ChromaDB.

## Stack

- **Language**: Python 3.11
- **Framework**: discord.py >= 2.4.0
- **Database**: SQLite (aiosqlite + FTS5 for BM25) + ChromaDB (for KNN embeddings) + secondary SQLite for Codex
- **LLM**: Google AI Studio — gemma-4-26b-a4b-it (google-genai SDK), plus DeepSeek v4 Pro/Flash via custom provider, OpenRouter
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2
- **TTS**: Piper (system binary) — currently disabled
- **Rendering**: cairosvg + Pillow (SVG→PNG/GIF)
- **Vision**: opencv-python-headless (video frame extraction), ONNX Runtime (media_guard image embeddings)
- **Local LLM**: MouthWash heuristic replacement engine, transformers MarianMT (curse translator OPUS-MT)
- **Logging**: loguru
- **Deploy**: systemd (plana-bot.service) / start.sh + venv

## Components

```
main.py (FairyBot) ─── Services ──┬── utils/database.py (Database, 1725+ LOC)
  │                                ├── utils/llm_client.py (LLMClient/GoogleLLM/OpenRouterLLM/CustomLLM)
  │                                ├── utils/orchestrator.py (Orchestrator — message pipeline)
  │                                ├── utils/nexus.py (FairyNexus — identity/alias tracker)
  │                                ├── utils/embed_engine.py (EmbedEngine — intent matching)
  │                                ├── utils/svg_engine.py (SVGEngine — SVG generation via LLM)
  │                                ├── utils/tts_engine.py (TTSEngine — Piper wrapper, DEAD while voice disabled)
  │                                ├── utils/discord_tools.py (ToolExecutor — 94+ _do_* methods)
  │                                ├── utils/repetition_shield.py (RepetitionShield)
  │                                ├── utils/memoria_agente.py (MemoriaAgente — agent memory)
  │                                ├── utils/destilador.py (Destilador — 3-phase personality distillation)
  │                                ├── utils/destilador_personas.py (legacy — 0 runtime refs, kept for schema)
  │                                ├── utils/graph_analyzer.py (GraphAnalyzer — social graph, 756 LOC) ★
  │                                ├── utils/curse_translator.py (CurseTranslator — OPUS-MT, 285 LOC) ★ NEW
  │                                ├── utils/curse_webhook.py (CurseWebhookManager — 128 LOC) ★ NEW
  │                                ├── utils/mouth_wash_llm.py (MouthWashLLM — heuristic dict-based engine, 264 LOC) ★ NEW
  │                                ├── utils/link_checker.py (DEAD — 0 references)
  │                                └── utils/security.py (PermLevel, require_level)
  │
  └── Cogs ──────────┬── cogs/nlp_handler.py (NLP pipeline entry) ★ CRITICAL
                       ├── cogs/nexus_observer.py (entity/alias extraction) ★ CRITICAL
                       ├── cogs/message_logger.py (message archival + embeddings) ★ CRITICAL
                       ├── cogs/automod_v2.py (risk-based automod)
                       ├── cogs/torneo.py (tournament with AI agents)
                       ├── cogs/listeners.py (trigger/keyword system)
                       ├── cogs/moderation.py (mod commands)
                       ├── cogs/admin.py (guild config)
                       ├── cogs/draw.py (SVG generation)
                       ├── cogs/destilacion.py (personality distillation + /card viewer)
                       ├── cogs/xoft.py (alt personality via LLM)
                       ├── cogs/info.py (server/user info)
                       ├── cogs/model_switcher.py (LLM provider hot-swap) ★ NEW
                       ├── cogs/dream_quest.py (Kadath text adventure, 734 LOC) ★ NEW
                       ├── cogs/media_guard/ (image similarity detection) ★ NEW
                       ├── cogs/curse.py (curse system, 346 LOC) ★ NEW
                       ├── cogs/mouthwash.py (mouth wash LLM, 187 LOC) ★ NEW
                       ├── cogs/voice.py (TTS — COMMENTED OUT in OPTIONAL_COGS)
                       └── cogs/safe_domains.py (URL safety — NOT LOADED ⚠, 1799 LOC dead code)
```

## Cog Load Status (2026-05-10)

| Cog | List | Loaded | Documented | Notes |
|-----|------|--------|------------|-------|
| cogs.nlp_handler | CRITICAL | ✓ | ✓ | |
| cogs.nexus_observer | CRITICAL | ✓ | ✓ | |
| cogs.message_logger | CRITICAL | ✓ | ✓ | |
| cogs.admin | OPTIONAL | ✓ | ✓ | |
| cogs.moderation | OPTIONAL | ✓ | ✓ | |
| cogs.automod_v2 | OPTIONAL | ✓ | ✓ | |
| cogs.info | OPTIONAL | ✓ | ✓ | |
| cogs.draw | OPTIONAL | ✓ | ✓ | |
| cogs.destilacion | OPTIONAL | ✓ | ✓ | |
| cogs.listeners | OPTIONAL | ✓ | ✓ | |
| cogs.torneo | OPTIONAL | ✓ | ✓ | |
| cogs.xoft | OPTIONAL | ✓ | ✓ | |
| cogs.model_switcher | OPTIONAL | ✓ | ✗ | NEW — not in prior ARCHITECTURE.md |
| cogs.dream_quest | OPTIONAL | ✓ | ✗ | NEW — Kadath system |
| cogs.media_guard | OPTIONAL | ✓ | ✗ | NEW — not in prior ARCHITECTURE.md |
| cogs.curse | OPTIONAL | ✓ | ✗ | NEW — not in prior ARCHITECTURE.md |
| cogs.mouthwash | OPTIONAL | ✓ | ✗ | NEW — not in prior ARCHITECTURE.md |
| cogs.voice | COMMENTED OUT | ✗ | ✓ | TTS disabled, documented but not loaded |
| cogs.safe_domains | NOT IN LISTS | ✗ | ✓ | 1799 LOC dead code, documented but never loaded |

**Summary**: 17 cogs loaded (3 CRITICAL + 14 OPTIONAL). 12 were previously documented. 5 new cogs (model_switcher, dream_quest, media_guard, curse, mouthwash) added to OPTIONAL_COGS since May 6 review. 2 cogs documented but NOT loaded (voice, safe_domains).

**dream_quest location**: `cogs.dream_quest` appears in main.py OPTIONAL_COGS (line 110). It is NOT in CRITICAL_COGS. The Kadath system correctly loads as an optional cog.

## Data Flow

### Primary Message Pipeline
```
Discord message (mention) → NLPHandlerCog.on_message
  → permission check (can_use_fairy_nl)
  → media extraction (images/video frames)
  → Orchestrator.process_message()
    → _prepare_content (strip mention, resolve user/role/channel IDs)
    → nexus_context (IDs + aliases snapshot from FairyNexus)
    → hybrid_search_messages (FTS5 + sqlite-vec KNN RAG)
    → if tools_available: generate_with_tools(tool_system_prompt + nexus)
    → else: generate_plain(system_prompt + nexus)
    → _record_turn (append to per-channel deque, trim to 200K token budget)
    → RepetitionShield.check()
    → smart_chunk → send
```

### Alternate flows:
- `cogs/xoft.py` → `self.bot.llm.generate_plain()` directly (bypasses Orchestrator/RAG/Nexus)
- `cogs/torneo.py` → `self.bot.llm.generate_plain()` directly (bypasses Orchestrator/RAG/Nexus)

### NEW: Curse System Flow
```
cogs/curse.py loaded → CurseTranslator.load_model() (OPUS-MT models)
  → CurseCog.on_message intercepts cursed user's message
    → 1. Delete original message
    → 2. CurseTranslator.translate() → random language (is/mt/xh/pap/eo)
    → 3. CurseWebhookManager.send_cursed() → impersonated webhook re-send

Commands: /curse, /uncurse, /listcursed (admin only)
DB tables: curses (guild_id, user_id, release_at, reason, created_by, display_name)
```

### NEW: MouthWash System Flow
```
cogs/mouthwash.py loaded → MouthWashLLM.initialize() (heuristic parametric dictionary engine)
  → MouthWashCog.on_message intercepts washed user's message
    → 1. Delete original message
    → 2. MouthWashLLM.rewrite() → family-friendly rewrite via local LLM
    → 3. CurseWebhookManager.send_cursed() → impersonated webhook re-send

DB tables: mouth_washes (guild_id, user_id, release_at, reason, created_by)
Shared dependency: CurseWebhookManager (used by both curse and mouthwash for webhook impersonation)
```

### NEW: Dream Quest (Kadath) Flow
```
cogs/dream_quest.py loaded → GameState + KadathView + DreamQuestCog
  /aventura command → create/load GameState from data/kadath_saves/{user_id}.json
    → load_world() from data/kadath_world.json (graph of story nodes)
    → KadathView renders buttons for available paths + inventory Select
    → _advance_to_node(): apply effects, check endings, save game, re-render view
    → _ending(): display final embed, delete save file

No LLM dependency. Pure state machine with JSON world graph.
6 canonical endings tracked (locura_arkham, despertar_terror, festin_zoog, justicia_felina, asimilacion_lunar, + node.is_ending)
SAN-driven embed color system (green→yellow→orange→red→black)
```

### NEW: Model Switcher Flow
```
cogs/model_switcher.py → /modelo command (owner-only, ID 239550977638793217)
  → _parse_provider_value() → provider, model_name, disable_thinking
  → Update bot.config in memory + persist to data/model_config.json
  → create_llm_client() + load() → hot-swap bot.llm, bot.orchestrator.llm, bot.svg_engine.llm_client
  → Fallback detection: if GoogleLLM created but provider != "google", warn about missing credentials

Supports: Google (Gemma 4 26B/31B), OpenRouter, DeepSeek v4 Pro/Flash (thinking ON/OFF)
```

### NEW: Media Guard Flow
```
cogs/media_guard/ → MediaGuardCog
  → Embedder: ONNX mobilenetv3_small → 1280-dim image embeddings
  → IndexManager: hnswlib index of banned media (data/banned_media.bin)
  → Thresholds: per-guild similarity thresholds
  → GIFProcessor: frame extraction for GIF analysis
  → On message: extract media → embed → similarity search → flag/delete if above threshold

Commands: /prohibir, /listprohibited
Currently: 30 banned entries indexed (as of May 9)
```

### Listener hot-reload:
ToolExecutor → `bot.notify_listener_change()` → `bot.get_cog('Listeners')` → ListenersCog methods (no circular import)

## External Dependencies

- Discord API (discord.py)
- Google AI Studio API (google-genai SDK)
- OpenRouter API (optional, via openai SDK)
- DeepSeek API (custom provider, /v1/chat/completions endpoint)
- sentence-transformers (local all-MiniLM-L6-v2 model)
- Piper TTS (system binary, disabled)
- cairosvg + Pillow (SVG rendering)
- ONNX Runtime (media_guard image embeddings)
- MouthWash parametric replacement dictionary engine
- HuggingFace transformers (curse translator — MarianMT/OPUS-MT models)
- hnswlib (media_guard similarity index)

## Database

### Main DB (168 MB)
| Table | Size | Purpose |
|-------|------|---------|
| message_embeddings | 93 MB | 384-float BLOB per message >= 5 chars |
| vec_messages_chunks00 | 51 MB | Stale/legacy embeddings for sqlite-vec |
| messages | 4.5 MB | Message content + metadata |
| aliases | 0.8 MB | nexus_observer identity data |
| messages_fts | 1.2 MB | FTS5 full-text search (duplicates content) |

**New tables added since May 6:**
| Table | Purpose |
|-------|---------|
| curses | Curse system — active curses (guild_id, user_id, release_at, reason, created_by, display_name) |
| mouth_washes | MouthWash system — active washes (guild_id, user_id, release_at, reason, created_by) |
| audit_log | Action logging (guild_id, action_type, actor_id, target_id, details, timestamp) |

**Known DB issues** (open):
- Embeddings stored TWICE (BLOB + vec table) = 144 MB wasted
- vec_messages has NO CASCADE DELETE → orphaned rows after prune
- Growth rate: ~19.5 MB/day, ~600 MB/month without pruning
- DB size stable since 2026-05-05 (daily pruning working)

## Dependency Graph (New Systems)

```
cogs/curse.py
  ├── utils/curse_translator.py  (CurseTranslator — OPUS-MT MarianMT models)
  └── utils/curse_webhook.py     (CurseWebhookManager — webhook create/send/cache)

cogs/mouthwash.py
  ├── utils/mouth_wash_llm.py    (MouthWashLLM — heuristic dict-based engine)
  └── utils/curse_webhook.py     (CurseWebhookManager — SHARED with curse)

cogs/model_switcher.py
  ├── utils/llm_client.py        (create_llm_client, GoogleLLM)
  └── data/model_config.json     (persistence)

cogs/dream_quest.py
  ├── data/kadath_world.json     (world graph — story nodes)
  └── data/kadath_saves/         (per-user GameState JSON files)
  Note: No LLM dependency — pure state machine.

cogs/dream_quest.py
  ├── embedder.py                (ONNX mobilenetv3_small)
  ├── index_manager.py           (hnswlib similarity index)
  ├── media_resolver.py          (URL/image extraction)
  ├── gif_processor.py           (GIF frame extraction)
  └── thresholds.py              (per-guild config)

CurseWebhookManager SHARED by:
  ├── cogs/curse.py      (cursed message impersonation)
  └── cogs/mouthwash.py  (washed message impersonation)
```

## Known Issues (open)

### 🔴 Critical
- **`.env` contiene credenciales vivas** — Token de Discord, API key de Google, y sufijo de OpenRouter expuestos en texto plano. Si el repositorio se vuelve público o se filtra, compromiso total del bot y de la cuenta de Google AI Studio. **Rotar inmediatamente.**
- **`/poll`, `/xoft`, `/aventura` sin autenticación** — Cualquier usuario puede crear mensajes persistentes, enviar por webhook con nombre/avatar personalizados, y generar archivos de guardado. No tienen `@require_level` ni verificación de permisos. (info.py:179, xoft.py:127, dream_quest.py:665)
- **~~Hardcoded API key en `utils/api_server.py:221`~~** — _Resuelto 2026-05-15 (Wave 1, SEC-03)._ El fallback ahora es `secrets.token_urlsafe(32)` generado aleatoriamente al arranque si `FAIRY_API_KEY` no está en el entorno. La key generada se loggea (prefijo) para que el admin la copie a `.env` si quiere persistencia.
- **cogs/safe_domains.py — 1799 LOC dead code**: Not in CRITICAL_COGS or OPTIONAL_COGS. Never loaded.
- **KadathView `on_timeout` AttributeError** (May 7-9): `'KadathView' object has no attribute 'message'`. The View is constructed before being attached to a message via `send()`, so `self.message` is None when timeout fires. Multiple occurrences per session flood logs with tracebacks.
- **KadathView `_ending` TypeError** (May 7): `followup.send(embed=embed, view=None)` — passing `view=None` to `send()` causes `TypeError: expected view parameter to be of type View or LayoutView, not NoneType`. The `_ending` method at line 653 should omit the `view` kwarg entirely when view is None.

### 🟠 High
- **Orchestrator.client AttributeError** (May 8): `cogs/info.py:166` references `self.bot.orchestrator.client.ready` but Orchestrator has no `client` attribute. This breaks the `/botinfo` command. Fix: reference `self.bot.llm` instead.
- **LLM direct access bypassing Orchestrator**: cogs/xoft.py:85 and cogs/torneo.py:881 call `self.bot.llm.generate_plain()` directly, skipping RAG context, Nexus identity augmentation, and repetition shield.
- **CurseTranslator: stale import error in logs** (May 8): Log shows `ModuleNotFoundError: No module named 'ctranslate2'` at `_load_ct2_model:99`. This function no longer exists in current code (replaced by OPUS-MT MarianMT). Indicates a deployment mismatch — old bytecode or incomplete rollout.

### 🟡 Medium
- **Silent exception swallowing**: automod_v2.py:307,513,531; voice.py:264; destilacion.py:274,321 — `except Exception: pass`/`continue` hides failures silently.
- **DB bloat**: 168 MB, embeddings duplicated. No CASCADE DELETE on vec_messages.
- **DB write_lock limitation**: database.py `asyncio.Lock` only serializes coroutine submission, not aiosqlite worker execution (see PLAN_DB_LOCK_FIX.md).
- **Dead utilities**: destilador_personas.py (701 LOC, 0 refs), link_checker.py, tts_engine.py (while voice disabled). Kept for schema compatibility but have no runtime use.
- **Curse/webhook rate limiting risk**: Both curse and mouthwash delete-and-resend via webhook on every message. A cursed user spamming could trigger Discord rate limits rapidly (message delete + webhook send per message).
- **Curse/webhook rate limiting risk**:

### 🟢 Low
- **LLM bypass**: xoft/torneo skip Orchestrator (intentional for now — they need their own prompt chains)
- **voice.py**: Commented out in OPTIONAL_COGS, TTS disabled (intentional)
- **.env**: Plain-text secrets on disk (intended — gitignored). Missing GITHUB_TOKEN env var (discord_tools.py handles gracefully).
- **database.py:358**: f-string SQL in migration (safe — values from hardcoded list)
- **Botinfo 404 Unknown interaction** (May 9): Interaction expired before response could be sent. Low priority — Discord interaction timeout issue.
- **Typing indicator rate limiting** (May 9): `429 Too Many Requests` on `POST /channels/{id}/typing`. Caused by rapid successive mentions in the same channel. Discord-imposed limit.

## Resolved Issues

### 2026-05-10 (this review)
- **Security sweep completed**: 4🔴 críticos encontrados — credenciales vivas en `.env`, 3 comandos sin auth (`/poll`, `/xoft`, `/aventura`), API key hardcodeada en `api_server.py:221`. 1🟠 SQL injection potencial (currently safe via whitelist).
- **Architecture mapped**: 5 new cogs (curse, mouthwash, model_switcher, dream_quest, media_guard), 4 new utils (curse_translator, curse_webhook, mouth_wash_llm) fully documented with data flows, dependencies, and DB tables.
- **Runtime errors documented**: KadathView on_timeout AttributeError, KadathView _ending TypeError (both still open 🔴). CurseTranslator ctranslate2 import (stale code — resolved in current code, OPUS-MT replacement live). MouthWash model discrepancies (Qwen3-0.6B in code, Qwen2-5/SmolLM2 in logs — model file needs verification). Botinfo 404, typing 429 (Discord-imposed limits, 🟢 low).
- **Orchestrator.client bug verified RESOLVED**: Log from May 8 showed `AttributeError: 'Orchestrator' has no attribute 'client'` at `cogs/info.py:166`. Current code correctly uses `self.bot.orchestrator.llm.ready` — this was a stale bytecode/deployment mismatch, not a current code bug.
- **Sutileza manual sweep**: `asyncio.create_task` references all properly stored (48 calls, 8 in project code, all with `add_done_callback`). Zero bare `except:` or `except Exception: pass` in project code. No AnnAssign tuple bugs, no missing returns, no forward references found.
- **Cross-reference complete**: 17 cogs loaded vs 12 previously documented. 5 undocumented cogs now added to component diagram. 2 cogs documented but not loaded (voice, safe_domains).
- **dream_quest verified**: Present in OPTIONAL_COGS (line 110), loads successfully, Kadath system functional despite view timeout bug.

### 2026-05-06 (this review)
- **Verified all prior fixes intact**: SQL injection whitelist, circular dependency bridge, asyncio task leaks, silent exceptions, simulacion/cards deletion, str.format brace escaping, LLM thinking_level, Discord intents.
- **Compile sweep**: All 41 .py files pass AST syntax check with zero errors.
- **No new sutilezas found**: AnnAssign tuple, missing returns, task leaks, stale references, forward references, method name mismatches — all checked and clean.

### 2026-05-05 (session 2)
- **Destilador KeyError FIXED** — `utils/destilador.py` prompts used `{` and `}` for JSON examples, which Python's `str.format()` interpreted as placeholder syntax. E.g. `{ "nombre": "..." }` triggered `KeyError('\n "nombre"')`. Fix: escaped all literal braces to `{{` / `}}` in prompt templates, except `{mensajes}` which is the actual placeholder.

### 2026-05-05
- **Cards system REPLACED by Destilación** — `cogs/cards.py` + `utils/card_generator.py` deleted. New system:
  - `cogs/destilacion.py`: `/destilación` (owner ID 239550977638793217 + admins only) + `/card` (public viewer)
  - `utils/destilador.py`: 3-phase LLM analysis (Superficie → Estructura → Esencia) with 9 req/min rate limiter
  - `utils/database.py`: added `get_user_all_messages()` and `get_guild_member_ids()` for destillation queries
  - `user_cards` table reused — JSON schema changed from `{profile, stats, personality, social}` to `{superficie, estructura, esencia}`
  - `main.py`: CardGenerator, hourly_card_update, _init_card_generator removed. Cog list updated to `cogs.destilacion`
- **cogs/simulacion.py DELETED** — removed simulation cog per user request
- **SQL injection FIXED** — `set_guild_config()` now validates kwargs keys against `_GUILD_CONFIG_COLUMNS` whitelist (database.py:310,396-400)
- **Circular dependency FIXED** — `discord_tools.py` no longer imports `cogs.listeners.ListenersCog`. Uses `bot.notify_listener_change()` bridge method instead (main.py:451, discord_tools.py:2388,2421,2431,2447)
- **Asyncio task leaks FIXED** — voice.py: VoiceCog now stores task references in `self._bg_tasks: set[asyncio.Task]` with `add_done_callback(discard)` pattern (lines 49,152-153,251-252,272-273)
- **Silent exceptions FIXED** — all `except Exception: pass` replaced with proper logging
- **Dead code DELETED** — main.py.bak removed, docs/detector-genero-pronombres.md removed
- **Data schema preserved** — utils/memoria_agente.py and utils/destilador_personas.py keep `system_prompt_simulacion` fields (DB schema, not code references)

### 2026-05-04
- Bare `except:` clauses fixed in destilador_personas.py, torneo.py
- Config model name fixed: gemma-4-31b-it → gemma-4-26b-a4b-it
- DB abstraction: raw `_db.execute()` eliminated from cogs (4 new public methods added to Database)
- tqdm/sentence-transformers noise suppressed (TQDM_DISABLE before imports)
- Boot panel TUI added to main.py
- Section 8 bugs fixed: username preservation (8e), forward reference (8h), cache drift (8i), method name mismatch (8j), stale variable names (8k), dead _llm attr (8g)

## Conventions

- **Language**: Spanish comments, Spanish user-facing strings, English code identifiers
- **DB access**: All cogs go through `self.bot.db` (Database class). No direct `_db` access from cogs.
- **Auth**: `@require_level(PermLevel.MOD)` or `@require_level(PermLevel.ADMIN)` decorators on mod/admin commands
- **LLM**: Two system prompts — conversational (with ---ANSWER---) and agentic (with tool routing)
- **Config**: FairyConfig dataclass, loaded from .env via python-dotenv
- **Logging**: loguru with compact format + daily rotating file logs/
- **Listener hot-reload**: Use `bot.notify_listener_change()` — never import ListenersCog from utils/
- **Task safety**: Store all `asyncio.create_task()` references in a `set[asyncio.Task]` with `add_done_callback(discard)`
- **LLM access**: Cogs needing custom prompts should use `self.bot.llm.generate_plain()` (documented pattern). RAG/Nexus/Shield bypass is intentional for xoft and torneo — these cogs use their own persona-based prompt chains. Other cogs should route through Orchestrator.
- **Webhook impersonation**: Both curse and mouthwash share `CurseWebhookManager` for webhook-based user impersonation. Webhooks are created per-channel and cached.
- **Model switching**: Hot-swap via `/modelo` persists to `data/model_config.json` and updates `bot.llm`, `bot.orchestrator.llm`, and `bot.svg_engine.llm_client` atomically.

## File Inventory (NEW since May 6)

| File | LOC | Status | Description |
|------|-----|--------|-------------|
| cogs/curse.py | 346 | LOADED ✓ | Curse system — translate and impersonate cursed users |
| cogs/mouthwash.py | 187 | LOADED ✓ | MouthWash system — parametric message sanitization |
| cogs/model_switcher.py | 190 | LOADED ✓ | Hot-swap LLM provider/model from Discord |
| cogs/dream_quest.py | 734 | LOADED ✓ | Dream-Quest of Unknown Kadath text adventure |
| cogs/media_guard/ | ~500 | LOADED ✓ | Image similarity detection (ONNX + hnswlib) |
| utils/curse_translator.py | 285 | ACTIVE | OPUS-MT MarianMT translation (5 languages) |
| utils/curse_webhook.py | 128 | ACTIVE | Webhook manager for user impersonation |
| utils/mouth_wash_llm.py | 264 | ACTIVE | Heuristic dict-based replacement engine |
| data/kadath_world.json | ? | ACTIVE | Kadath world graph (story nodes) |
| data/banned_media.bin | ? | ACTIVE | MediaGuard hnswlib index (30 entries) |
| models/mouthwash/ | ? | INACTIVE | GGUF model files (unused) |
