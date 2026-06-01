# Validation Scope: Djinn Discord Agentic Bot (Audit Update - June 2026)

## 1. Target & Context
- **Target Repository**: `/home/ubuntu/projects/djinn`
- **Application**: Djinn (Fairy/Youkai Bot) — An agentic Discord bot inspired by Zenless Zone Zero.
- **Primary Languages**: Python 3.11+
- **Conventions**:
  - Code identifiers in **English**.
  - Comments, documentation, and user-facing UI in **Spanish**.
  - Centralized DB interaction via `self.bot.db` (`utils/database.py`).
  - Loguru-based logger with daily rotation under `logs/`.

## 2. Tech Stack Summary
- **Framework**: `discord.py` >= 2.4.0 (using 2.7.0 features)
- **Database**: SQLite (via `aiosqlite` + WAL mode)
- **AI/LLM Providers**:
  - Google AI Studio (using `google-genai` SDK) [Default Core Agentic Engine]
  - DeepSeek v4 (via custom HTTP client)
  - OpenRouter API
- **Embeddings & Vector Backend**: ChromaDB (`ChromaMemory` wrapper) for semantic search
- **Vision & Guards**: `onnxruntime` (`mobilenetv3_small` for `cogs/media_guard/`)
- **TTS**: `Piper` (external binary wrapper, currently disabled/commented out)
- **Moderation Engine**: `goodfaith` package (integrated)

## 3. Scope of Validation
- **Latest Fixes Under Review**:
  - Integration of `CircuitBreaker` utility in `utils/llm_client.py` inside `_retry_api_call`.
  - Deletion/deprecation of the stale `sqlite-vec` vector pipeline and centralizing search around **ChromaDB**.
  - Realignment of `ARCHITECTURE.md` (correcting GGUF local model active status, mapping active databases, and documenting vector purging stubs).
  - Validation of the test suite execution status using the `/home/ubuntu/youkai/venv` virtual environment interpreter.
