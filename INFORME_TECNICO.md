# Youkai Bot — Informe Técnico Completo

**Generado**: 2026-05-12
**Proyecto**: `/home/ubuntu/Desktop/los nitos hermanos/fairy-fixed`
**Stack**: Python 3.11 · discord.py 2.4 · SQLite (aiosqlite + FTS5 + sqlite-vec) · Google AI (Gemma 4) · NVIDIA NIM · ONNX Runtime

---

## Arquitectura General

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py (YoukaiBot)                      │
├─────────────────────────────────────────────────────────────────┤
│  Services: DB · Nexus · EmbedEngine · LLM · Orchestrator · TTS  │
│            SVGEngine · APIServer                                 │
├─────────────────────────────────────────────────────────────────┤
│  Cogs (20): nlp_handler · listeners · moderation · automod_v2   │
│             admin · info · draw · destilacion · torneo · xoft    │
│             model_switcher · dream_quest · media_guard · curse   │
│             mouthwash · dashboard · server_memory · zzz_builds  │
│             nexus_observer · message_logger                      │
├─────────────────────────────────────────────────────────────────┤
│  Utils: orchestrator · llm_client · discord_tools · database    │
│         embed_engine · security · credit_economy · api_server   │
│         repetition_shield · message_transforms · graph_analyzer │
│         template_engine · svg_engine · tts_engine · and more    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Flujo de un Mensaje (Pipeline Agentic)

```
Discord Message
  │
  ├─ NLPHandlerCog.on_message
  │    ├─ can_use_youkai_nl() → permission check (OWNER or Reader role)
  │    ├─ Media extraction (images, video frames via cv2)
  │    └─ Orchestrator.process_message()
  │         │
  │         ├─ Rate limit (8 req/60s per user)
  │         ├─ Circuit breaker (3 failures → 60s cooldown)
  │         ├─ _prepare_content() → strip bot mention, resolve mentions
  │         ├─ Nexus context snapshot
  │         ├─ Lazy Loading Gates:
  │         │    ├─ _should_recall() → DB auto-recall (3-5 messages)
  │         │    ├─ Server memory injection
  │         │    ├─ _detect_skill_intent() → auto-load skill .md
  │         │    ├─ ZZZ RAG injection
  │         │    └─ _should_include_channels() → channel list
  │         ├─ Build conversation history (token-budgeted)
  │         ├─ _route_tools_semantic() → hybrid keyword+semantic routing
  │         └─ LLM.generate_with_tools()
  │              │
  │              ├─ Loop (max 20 rounds, 18 tool executions):
  │              │    ├─ API call (with retry + backoff)
  │              │    ├─ Tool calls → ToolExecutor.execute() → compress results
  │              │    ├─ Sniffer (detect text-based tool calls)
  │              │    └─ Continue until text response
  │              └─ Return final text
  │
  ├─ RepetitionShield.check() → anti-loop guard
  ├─ Inline tool processing (Qwen3 only)
  └─ smart_chunk() → split into Discord-sized messages → send
```

---

## Archivos Core

### main.py (19KB)
| Componente | Función |
|------------|---------|
| `_bootstrap_venv()` | Auto-crea venv, instala deps, re-exec dentro del venv |
| `YoukaiBot(commands.Bot)` | Clase principal del bot |
| `setup_hook()` | Inicializa DB → Nexus → Embedder → LLM → Orchestrator → TTS → SVG → Cogs → API |
| `daily_db_prune` | Task loop: purga mensajes >30 días |
| `notify_listener_change()` | Hot-reload de reglas de listeners |
| `CRITICAL_COGS` | nlp_handler, nexus_observer, message_logger |
| `OPTIONAL_COGS` | 17 cogs que pueden fallar sin tumbar el bot |

### config.py (7.5KB)
| Campo | Default | Propósito |
|-------|---------|-----------|
| `llm_provider` | "google" | Selector: google/openrouter/custom/nim |
| `google_model_name` | "gemma-4-26b-a4b-it" | Modelo Google |
| `nim_model_name` | "qwen/qwen3-next-80b-a3b-instruct" | Modelo NIM |
| `FORBIDDEN_FUNCTIONS` | 6 funciones | Nunca ejecutables (delete_channel, mass_ban, etc.) |
| `spam_*` | varios | Parámetros de detección de spam |
| `raid_*` | 600s/5 joins | Detección de raid |
| `trust_threshold_*` | 50 msgs/14 días | Umbral de confianza |

---

## Utils — Módulos Principales

### orchestrator.py (35KB)
| Función | Propósito |
|---------|-----------|
| `Orchestrator.process_message()` | Pipeline principal (staff/readers) |
| `Orchestrator.process_message_public()` | Pipeline público (créditos) |
| `_route_tools_semantic()` | Routing híbrido: keyword + embeddings semánticos |
| `_route_tools()` | Routing por keywords (fallback) |
| `_should_recall()` | Gate: skip auto-recall para mensajes casuales |
| `_should_include_channels()` | Gate: skip channels si no se necesitan |
| `_detect_skill_intent()` | Regex → auto-inyección de skill .md |
| `_fix_inline_markers()` | Corrige marcadores [tool] malformados (Qwen) |
| `_process_inline_tools()` | Ejecuta tools inline en texto (Qwen) |

### llm_client.py (75KB)
| Clase/Función | Propósito |
|---------------|-----------|
| `LLMClient` (ABC) | Interfaz base multi-provider |
| `GoogleLLM` | Google AI Studio (Gemma 4) con thinking |
| `OpenRouterLLM` | OpenRouter (Nemotron, GPT-OSS, etc.) |
| `CustomLLM` | OpenAI-compatible (NIM, DeepSeek) |
| `create_llm_client()` | Factory por provider |
| `_build_tool_system_prompt()` | Prompt agentic genérico (~12K chars) |
| `_build_tool_system_prompt_qwen()` | Prompt optimizado Qwen (~6.8K chars) |
| `_compress_tool_result()` | Compresión columnar + filtrado low-signal |
| `_retry_openai_call()` | Retry con backoff (5 intentos, 2s→30s) |
| `_sniff_text_tool_calls()` | Detecta tool calls emitidos como texto |
| `filter_thoughts()` | Strip `<thought>` tags y `---ANSWER---` |

### discord_tools.py (232KB)
| Componente | Propósito |
|------------|-----------|
| `TOOL_DECLARATIONS` | 124 tools declaradas para el LLM |
| `ToolExecutor` | Dispatcher: ejecuta tools con permisos y timeouts |
| `FORBIDDEN` | Set de funciones bloqueadas permanentemente |
| `_fix_json()` | Repara JSON malformado del LLM |
| Helpers: `_str()`, `_int()`, `_bool()`, `_decl()` | Constructores de schemas (con soporte enum) |

### database.py (89KB)
| Tabla | Propósito |
|-------|-----------|
| `guild_config` | Configuración por servidor |
| `youkai_readers` | Roles con acceso al LLM |
| `warnings` | Advertencias de moderación |
| `messages` | Historial completo de mensajes (FTS5) |
| `user_seals` | Usuarios sellados (aislamiento) |
| `guild_listeners` | Reglas automáticas |
| `listener_trigger_log` | Log de disparos de reglas |
| `user_credits` | Sistema de créditos (pipeline público) |
| `trust_scores` | Puntuación de confianza por usuario |
| `youkai_audit` | Log de auditoría |

### embed_engine.py (8.5KB)
| Función | Propósito |
|---------|-----------|
| `EmbedEngine.encode()` | Genera embeddings (all-MiniLM-L6-v2) |
| `get_response()` | Retrieval semántico de respuestas pre-escritas |
| `classify_intent()` | Clasificación zero-shot (MODERATION/QUERY/CONFIG/CHAT) |

### security.py (3.9KB)
| Nivel | Nombre | Acceso |
|-------|--------|--------|
| 5 | OWNER | Todo |
| 4 | ADMIN | Administrator de Discord |
| 3 | MOD | Permisos de moderación |
| 2 | READER | Puede hablar con el LLM |
| 1 | USER | Comandos públicos básicos |
| 0 | NONE | Sin acceso |

### credit_economy.py (2.6KB)
| Constante | Valor | Propósito |
|-----------|-------|-----------|
| `COST_WITH_TOOLS` | 300 | Costo por llamada LLM con tools |
| `COST_SIMPLE` | 100 | Costo por llamada LLM simple |
| `DAILY_EARN_CAP` | 750 | Máximo créditos/día |
| `DAILY_CALL_CAP` | 10 | Máximo llamadas/día |

---

## Cogs — Funcionalidades

### Críticos (el bot no arranca sin ellos)
| Cog | Propósito |
|-----|-----------|
| `nlp_handler` | Procesa mensajes → LLM. Extrae media, aplica RepetitionShield |
| `nexus_observer` | Mantiene contexto de identidad (aliases, IDs) |
| `message_logger` | Persiste todos los mensajes en DB para búsqueda |

### Moderación
| Cog | Propósito |
|-----|-----------|
| `moderation` | Slash commands: /ban, /kick, /mute, /warn |
| `automod_v2` | Risk scoring automático: floods, spam, obfuscation, raids |
| `listeners` | Motor de reglas heurísticas (regex + semántico + scored) |
| `media_guard` | Detección de media duplicada/prohibida (MobileNetV3 + HNSW) |

### Entretenimiento
| Cog | Propósito |
|-----|-----------|
| `dream_quest` | Aventura de texto Lovecraftiana (Kadath) |
| `torneo` | Sistema de torneos con LLM como Game Master |
| `xoft` | Sistema Xoft (juego de cartas/colección) |
| `curse` | "Maldición": traduce mensajes a idiomas random |
| `mouthwash` | "Lavado de boca": filtro local con GGUF |
| `zzz_builds` | Builds de Zenless Zone Zero |

### Utilidades
| Cog | Propósito |
|-----|-----------|
| `admin` | Comandos administrativos del bot |
| `info` | Información del servidor/usuarios |
| `draw` | Generación de imágenes |
| `destilacion` | Destilación de personalidades de usuarios |
| `model_switcher` | Hot-swap de modelo LLM (/modelo) |
| `dashboard` | Dashboard web local |
| `server_memory` | Memoria persistente del servidor |

---

## Tools del LLM (124 total)

### Por Categoría
| Categoría | Tools | Ejemplos |
|-----------|-------|----------|
| Moderación | 16 | ban_user, mute_user, seal_user, mass_timeout |
| Canales | 13 | purge_messages, lock_channel, create_thread |
| Roles | 8 | assign_role, create_role, bulk_assign_role_all |
| Búsqueda | 8 | search_messages, aggregate_messages, investigate_topic |
| Info servidor | 9 | server_dashboard, get_leaderboard, detect_newcomers |
| Usuarios | 6 | get_user_by_name, batch_user_lookup, filter_members |
| Visual | 3 | render_template, generate_svg_image, send_embed |
| Listeners | 7 | create_listener, list_listeners, edit_listener |
| Social graph | 6 | analyze_social_graph, find_communities |
| Scheduling | 5 | schedule_message, create_poll, broadcast |
| Web | 2 | web_fetch, fetch_url_preview |
| Core | 7 | send_message, add_reaction, read_skill |
| Otros | 33 | curse_user, wash_mouth, backup_server |
<!-- 2026-05-15 (Wave 1, SEC-01): `execute_code` eliminado por RCE; ver .code-review/04-report.md -->


### Routing
- **Keyword matching**: 40+ keywords → categorías
- **Semantic retrieval**: all-MiniLM-L6-v2 embeddings, cosine similarity, top-18
- **Híbrido**: keyword primero, semantic como suplemento
- **Nunca envía las 124**: máximo 25 tools por request

---

## Skills (16 archivos .md)

| Skill | Propósito | Se activa cuando... |
|-------|-----------|---------------------|
| `sherlock_kai` | Investigación profunda multi-fuente | "quién es X", "investiga", "es tóxico" |
| `rules` | Schema completo de listeners | create_listener necesita docs |
| `tierlists` | Templates visuales disponibles | "tierlist", "gráfico", "perfil" |
| `embed_design` | Diseño de embeds elaborados | "embed", "anuncio" |
| `data_mastery` | Optimización de queries | Análisis estadísticos complejos |
| `antiraid` | Protocolo anti-raid | "raid" (análisis, no urgente) |
| `apodos` | Generación de apodos creativos | "apodo", "nickname" |
| `ascii_art` | Arte ASCII | "ascii", "arte texto" |
| `onboarding` | Bienvenida de nuevos miembros | "bienvenida", "onboarding" |
| `eventos` | Planificación de eventos | "evento", "torneo" |
| `sellar` | Protocolo de sellado | "protocolo de sello" |
| `traduccion` | Sistema de traducción | "traduce" |
| `zzz_terminos` | Terminología de ZZZ | Preguntas sobre el juego |
| `obscura-web` | Búsqueda web | "busca en internet" |
| `investigacion` | Protocolos de investigación | Investigación de moderación |
| `sherlock` | Sherlock original (legacy) | Reemplazado por sherlock_kai |

---

## Templates SVG (19 Jinja2)

| Template | Uso |
|----------|-----|
| `love_graph` | Gráfico de relaciones/ships |
| `leaderboard` | Ranking de actividad |
| `profile_card` | Tarjeta de perfil de usuario |
| `tierlist` | Tier list S/A/B/C/D |
| `bar_chart` | Gráfico de barras |
| `heatmap` | Mapa de calor (actividad semanal) |
| `radar_chart` | Gráfico radar/spider |
| `donut_chart` | Gráfico de dona |
| `timeline` | Línea de tiempo |
| `investigation_timeline` | Timeline de investigación |
| `graph_network` | Red social/grafo |
| `correlation_matrix` | Matriz de correlación |
| `comparison` | Comparación X vs Y |
| `stat_grid` | Grid de estadísticas |
| `banner` | Banner/anuncio visual |
| `achievement_card` | Tarjeta de logro |
| `_theme_neo_eridu` | Tema visual Neo Eridu |
| `_theme_hollow` | Tema visual Hollow |
| `_theme_observatory` | Tema visual Observatory |

---

## Modelos Locales

| Modelo | Ubicación | Propósito |
|--------|-----------|-----------|
| all-MiniLM-L6-v2 | models/embed/ | Embeddings semánticos (384 dims) |
| MobileNetV3-Small | data/mobilenetv3_small.onnx | Embeddings de imágenes (media_guard) |
| Qwen3-0.6B Q4_K_M | models/mouthwash/ | Filtro local "lavado de boca" |
| qwen2.5-0.5b Q4_0 | models/mouthwash/ | Filtro local alternativo |
| smollm2-135m Q4_0 | models/mouthwash/ | Filtro ultra-ligero |
| NLLB-200-distilled-600M | models/curse/ | Traducción multi-idioma (maldición) |
| Piper ES-low | models/piper/ | TTS en español |

---

## Base de Datos

- **Motor**: SQLite 3 con WAL mode + aiosqlite
- **Tamaño**: ~176 MB
- **Extensiones**: FTS5 (full-text search), sqlite-vec (KNN vectorial)
- **Embeddings**: int8 quantizados (75% menos espacio que float32)
- **Retención**: 30 días de mensajes (prune automático diario)
- **15 tablas** principales + índices optimizados

---

## Optimizaciones Recientes (Mayo 2026)

| Cambio | Impacto |
|--------|---------|
| Semantic Tool Router | -12K tokens/request (keyword + embeddings híbrido) |
| Enum compression | -3.5K tokens (enums en schemas, descriptions comprimidas) |
| Columnar results | -40% por resultado de tool (formato columnar) |
| Lazy Loading gates | -2K tokens promedio (skip recall/channels si innecesario) |
| Qwen3-Next prompt | -50% tokens de system prompt (6.8K vs 12.4K) |
| Retry con backoff | 5 intentos, 2s→30s (NIM 503/429 ya no crashean) |
| Fuzzy matching | Case-insensitive + typo tolerance en listeners |
| presence_penalty=1.0 | Elimina loops de repetición en Qwen |

---

## Seguridad

- **Permisos**: 6 niveles (NONE→OWNER), verificación por rol + jerarquía
- **FORBIDDEN**: 6 funciones permanentemente bloqueadas
- **Rate limiting**: 8 req/60s por usuario
- **Circuit breaker**: 3 fallos → 60s cooldown
- **API server**: solo localhost, X-API-Key auth
- **Automod**: risk scoring, raid detection, trust system
- **Media guard**: detección de contenido prohibido por similitud visual

---

## Métricas de Rendimiento (estimadas)

| Métrica | Valor |
|---------|-------|
| Tokens/request (input) | ~10-16K (post-optimización) |
| Tools por request | ~15-20 (vs 124 antes) |
| Latencia LLM | 1-5s (Gemma 4), 2-8s (NIM) |
| Routing semántico | ~20ms |
| Boot time | ~15-20s |
| DB size | ~176 MB |
| Cogs cargados | 20/20 |
