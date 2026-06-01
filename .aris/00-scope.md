# Aris Scope — Djinn Discord Agentic Bot

**Date**: 2026-06-01  
**Reviewer**: Aris Validator  
**Role**: code-reviewer  
**Base commit**: ebe2e1d  
**Head commit**: 3a360f1  

## Project
Python 3.11 Discord bot. ~47k lines deleted in cleanup. Key files reviewed:
- main.py, config.py
- utils/llm_client.py, utils/orchestrator.py, utils/discord_tools.py
- utils/tools/_declarations.py, utils/database.py
- utils/security.py, utils/api_server.py, utils/circuit_breaker.py
- cogs/automod_v3.py, cogs/nlp_handler.py, cogs/media_guard/
- tests/ (21 test files)

## Stack
Python 3.11, discord.py, aiosqlite (WAL), ChromaDB, google-genai, openai SDK, goodfaith, aiohttp, loguru

## Pillars
SLOP · CLAIMS · QUALITY
