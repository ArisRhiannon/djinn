"""
Configuración central de Fairy — cargada desde variables de entorno.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DjinnConfig:
    # ── Discord ────────────────────────────────────────────────────────────
    discord_token: str = ""

    # ── LLM Provider ──────────────────────────────────────────────────────
    llm_provider: str = "google"  # "google" o "openrouter"

    # ── Google AI (google-genai SDK) ───────────────────────────────────────
    google_api_key: str = ""
    google_model_name: str = "gemma-4-26b-a4b-it"

    # ── OpenRouter (openai SDK) ────────────────────────────────────────────
    openrouter_api_key: str = ""
    openrouter_model_name: str = "google/gemma-4-26b-a4b-it:free"

    # ── Custom Provider (OpenAI-compatible API — DeepSeek v4) ──────────────
    custom_base_url: str = "http://localhost:5001/v1"
    custom_api_key: str = ""
    custom_model_name: str = "deepseek-v4-pro"
    custom_disable_thinking: bool = False  # True para deepseek-v4-flash

    # ── NVIDIA NIM ─────────────────────────────────────────────────────────
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_api_key: str = ""
    nim_model_name: str = "qwen/qwen3-next-80b-a3b-instruct"

    # ── Kiro Gateway (OpenAI-compatible, local) ────────────────────────────
    kiro_base_url: str = "http://localhost:8000/v1"
    kiro_api_key: str = ""
    kiro_model_name: str = "minimax-m2.5"

    # ── Owner (ID del dueno del server, para system prompts) ──────────────
    owner_user_id: Optional[int] = None

    # ── Rutas — base de datos ──────────────────────────────────────────────
    db_path: str = "db/fairy.db"

    # ── Piper TTS ──────────────────────────────────────────────────────────
    tts_enabled: bool = True
    piper_bin: str = "piper"                                    # nombre o ruta completa
    piper_model: str = "models/piper/es_ES-low.onnx"
    piper_config_path: str = "models/piper/es_ES-low.onnx.json"
    tts_sample_rate: int = 24000

    # ── EmbedEngine (sentence-transformers) ───────────────────────────────
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embed_cache_dir: str = "models/embed"

    # ── Rutas de datos ─────────────────────────────────────────────────────
    responses_path: str = "data/fairy_responses.json"
    bad_domains_path: str = "data/bad_domains.txt"

    # ── Seguridad / Automod ────────────────────────────────────────────────
    FORBIDDEN_FUNCTIONS: frozenset = field(default_factory=lambda: frozenset({
        "delete_channel",
        "delete_category",
        "delete_vc",
        "mass_ban",
        "delete_all_channels",
        "nuke_server",
    }))

    spam_window_seconds: int = 10
    spam_max_messages: int = 8
    spam_max_mentions: int = 5
    spam_max_duplicates: int = 4
    trust_threshold_messages: int = 50
    trust_threshold_days: int = 14

    # ── Anti-raid ──────────────────────────────────────────────────────────
    raid_join_window: int = 600       # segundos de ventana de detección de raid
    raid_join_threshold: int = 5      # entradas nuevas en ese tiempo para activar

    # ── Comportamiento de moderación ───────────────────────────────────────
    max_purge_messages: int = 100
    max_warn_before_action: int = 3
    mute_unit_multipliers: dict = field(default_factory=lambda: {
        "s": 1, "m": 60, "h": 3600, "d": 86400,
    })

    # ── Canales de respuestas del bot ──────────────────────────────────────
    max_response_chunk: int = 1_900

    @classmethod
    def from_env(cls) -> "DjinnConfig":
        _try_load_dotenv()
        return cls(
        discord_token=os.getenv("DISCORD_TOKEN", ""),
        llm_provider=os.getenv("LLM_PROVIDER", "google"),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        google_model_name=os.getenv("GOOGLE_MODEL_NAME", "gemma-4-26b-a4b-it"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_model_name=os.getenv("OPENROUTER_MODEL_NAME", "nvidia/nemotron-3-super-120b-a12b:free"),
        owner_user_id=int(os.getenv("OWNER_USER_ID", "0")) or None,
            db_path=os.getenv("DB_PATH", "db/fairy.db"),
            tts_enabled=os.getenv("TTS_ENABLED", "true").lower() == "true",
            piper_bin=os.getenv("PIPER_BIN", "piper"),
            piper_model=os.getenv("PIPER_MODEL", "models/piper/es_ES-low.onnx"),
            piper_config_path=os.getenv("PIPER_CONFIG", "models/piper/es_ES-low.onnx.json"),
            embed_model=os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            embed_cache_dir=os.getenv("EMBED_CACHE_DIR", "models/embed"),
            responses_path=os.getenv("RESPONSES_PATH", "data/fairy_responses.json"),
            bad_domains_path=os.getenv("BAD_DOMAINS_PATH", "data/bad_domains.txt"),
            # ── Custom provider ──
            custom_base_url=os.getenv("CUSTOM_BASE_URL", "http://localhost:5001/v1"),
            custom_api_key=os.getenv("CUSTOM_API_KEY", ""),
            custom_model_name=os.getenv("CUSTOM_MODEL_NAME", "deepseek-v4-pro"),
            custom_disable_thinking=os.getenv("CUSTOM_DISABLE_THINKING", "false").lower() == "true",
            nim_base_url=os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            nim_api_key=os.getenv("NIM_API_KEY", ""),
            nim_model_name=os.getenv("NIM_MODEL_NAME", "qwen/qwen3-next-80b-a3b-instruct"),
            kiro_base_url=os.getenv("KIRO_BASE_URL", "http://localhost:8000/v1"),
            kiro_api_key=os.getenv("KIRO_API_KEY", ""),
            kiro_model_name=os.getenv("KIRO_MODEL_NAME", "minimax-m2.5"),
        )

    def parse_duration(self, duration_str: str) -> int:
        """'10m' → 600, '2h' → 7200. Retorna -1 si inválido."""
        if not duration_str:
            return -1
        duration_str = duration_str.strip().lower()
        unit = duration_str[-1]
        try:
            value = int(duration_str[:-1])
            return value * self.mute_unit_multipliers.get(unit, -1)
        except (ValueError, IndexError):
            return -1


def _try_load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass
