"""Cog: ModelSwitcher — Cambia el proveedor/modelo LLM desde Discord (solo owner).

Persiste la elección en data/model_config.json para que sobreviva reinicios.
Ofrece 4 opciones DeepSeek: v4 Pro / Flash, con y sin thinking.
"""

from __future__ import annotations

import json
import asyncio
import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("youkai.model_switcher")

OWNER_ID: int = 239550977638793217
CONFIG_PATH: Path = Path("data/model_config.json")

# Opciones de proveedor/modelo.
# Formato del value: "custom:<model_name>:<thinking_flag>"
#   thinking_flag = "think" (ON) | "nothink" (OFF)
PROVIDER_CHOICES: list[app_commands.Choice] = [
    app_commands.Choice(name="Google (Gemma 4 26B)",          value="google"),
    app_commands.Choice(name="Google (Gemma 4 31B)",          value="google:gemma-4-31b-it"),
    app_commands.Choice(name="Google (Gemini 3.1 Flash Lite Preview)", value="google:gemini-3.1-flash-lite-preview"),
    app_commands.Choice(name="NIM (Qwen3.5 397B A17B)",       value="nim:qwen/qwen3.5-397b-a17b"),
    app_commands.Choice(name="NIM (Kimi K2)",                  value="nim:moonshotai/kimi-k2-instruct"),
    app_commands.Choice(name="NIM (Llama 4 Maverick 17B)",    value="nim:meta/llama-4-maverick-17b-128e-instruct"),
    app_commands.Choice(name="NIM (DeepSeek V4 Flash)",       value="nim:deepseek-ai/deepseek-v4-flash"),
    app_commands.Choice(name="OpenRouter (Nemotron 3 Super)", value="openrouter:nvidia/nemotron-3-super-120b-a12b:free"),
    app_commands.Choice(name="OpenRouter (GPT-OSS 120B)",     value="openrouter:openai/gpt-oss-120b:free"),
    app_commands.Choice(name="OpenRouter (Owl Alpha)",        value="openrouter:openrouter/owl-alpha"),
    app_commands.Choice(name="OpenRouter",                     value="openrouter"),
    app_commands.Choice(name="DeepSeek v4 Pro",                value="custom:deepseek-v4-pro:think"),
    app_commands.Choice(name="DeepSeek v4 Pro (no think)",     value="custom:deepseek-v4-pro:nothink"),
    app_commands.Choice(name="DeepSeek v4 Flash",              value="custom:deepseek-v4-flash:think"),
    app_commands.Choice(name="DeepSeek v4 Pro + Search",       value="custom:deepseek-v4-pro-search:think"),
    app_commands.Choice(name="DeepSeek v4 Flash + Search",     value="custom:deepseek-v4-flash-search:think"),
    app_commands.Choice(name="DeepSeek v4 Vision",             value="custom:deepseek-v4-vision:think"),
    app_commands.Choice(name="Kiro (MiniMax M2.5)",              value="kiro:minimax-m2.5"),
    app_commands.Choice(name="Kiro (Auto)",                      value="kiro:auto-kiro"),
    app_commands.Choice(name="Kiro (GLM-5 744B)",                value="kiro:glm-5"),
    app_commands.Choice(name="Kiro (DeepSeek 3.2)",              value="kiro:deepseek-3.2"),
    app_commands.Choice(name="Kiro (Claude Sonnet 4.6)",         value="kiro:claude-sonnet-4.6"),
    app_commands.Choice(name="Kiro (Claude Opus 4.6)",           value="kiro:claude-opus-4.6"),
]


def _parse_provider_value(value: str) -> tuple[str, str, bool]:
    """Parsea el valor del proveedor → (provider, model_name, disable_thinking).

    Formatos soportados:
      - "google" o "openrouter" → (provider, "", False)
      - "google:model_name" o "openrouter:model_name" → (provider, model_name, False)
      - "nim:model_name" → ("nim", model_name, False)
      - "custom:model_name:think|nothink" → ("custom", model_name, disable_thinking)
    """
    parts = value.split(":")
    if len(parts) == 3 and parts[0] == "custom":
        return "custom", parts[1], parts[2] == "nothink"
    if len(parts) >= 2 and parts[0] in ("google", "openrouter", "nim", "kiro"):
        # Rejoin everything after the provider (preserves :free suffix or org/model)
        model_name = ":".join(parts[1:])
        return parts[0], model_name, False
    # Fallback: valor genérico (google, openrouter, o "custom" sin sufijo)
    return value, "", False


class ModelSwitcher(commands.Cog):
    """Comando /modelo para cambiar el LLM en caliente."""

    def __init__(self, bot) -> None:
        self.bot = bot

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_current_model(self) -> str:
        provider = self.bot.config.llm_provider
        if provider == "google":
            return self.bot.config.google_model_name
        if provider == "openrouter":
            return self.bot.config.openrouter_model_name
        if provider == "nim":
            return self.bot.config.nim_model_name
        if provider == "kiro":
            return self.bot.config.kiro_model_name
        return self.bot.config.custom_model_name

    def _save_config(self) -> None:
        """Guarda la config actual de modelo a disco."""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "llm_provider": self.bot.config.llm_provider,
            "google_model_name": self.bot.config.google_model_name,
            "openrouter_model_name": self.bot.config.openrouter_model_name,
            "custom_model_name": self.bot.config.custom_model_name,
            "custom_disable_thinking": self.bot.config.custom_disable_thinking,
            "nim_model_name": self.bot.config.nim_model_name,
            "kiro_model_name": self.bot.config.kiro_model_name,
        }
        CONFIG_PATH.write_text(json.dumps(data, indent=2))

    # ── Comando /modelo ──────────────────────────────────────────────────

    @app_commands.command(
        name="modelo",
        description="Cambia el proveedor/modelo LLM (solo owner)",
    )
    @app_commands.describe(
        proveedor="Proveedor de LLM a usar (vacío = ver actual)",
        pipeline="Pipeline a cambiar (default: staff)",
    )
    @app_commands.choices(
        proveedor=PROVIDER_CHOICES,
        pipeline=[
            app_commands.Choice(name="staff", value="staff"),
            app_commands.Choice(name="public", value="public"),
        ],
    )
    async def modelo(
        self,
        interaction: discord.Interaction,
        proveedor: str | None = None,
        pipeline: str = "staff",
    ) -> None:
        # ── Owner gate ──
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "⛔ No autorizado.", ephemeral=True
            )
            return

        # ── Modo consulta ──
        if proveedor is None:
            current = self._get_current_model()
            thinking = ""
            if (
                self.bot.config.llm_provider == "custom"
                and self.bot.config.custom_disable_thinking
            ):
                thinking = " (thinking OFF)"
            # Public model
            pub_model = "mismo que staff"
            if hasattr(self.bot, 'orchestrator') and self.bot.orchestrator:
                pub_llm = self.bot.orchestrator.llm_public
                if pub_llm is not self.bot.orchestrator.llm:
                    pub_model = pub_llm.get_model_name()
            await interaction.response.send_message(
                f"**Staff:** `{self.bot.config.llm_provider}` → `{current}`{thinking}\n"
                f"**Public:** `{pub_model}`",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # ── Parsear el valor del proveedor ──
        provider_key, model_name, disable_thinking = _parse_provider_value(proveedor)

        # ── Guardar estado actual para rollback ──
        old_llm = self.bot.llm
        old_provider = self.bot.config.llm_provider
        old_google_model = self.bot.config.google_model_name
        old_openrouter_model = self.bot.config.openrouter_model_name
        old_custom_model = self.bot.config.custom_model_name
        old_disable_thinking = self.bot.config.custom_disable_thinking
        old_kiro_model = self.bot.config.kiro_model_name

        # ── Actualizar config ──
        self.bot.config.llm_provider = provider_key
        if provider_key == "google":
            # Si no se especifica modelo, usar el default (26b)
            self.bot.config.google_model_name = model_name or "gemma-4-26b-a4b-it"
        elif provider_key == "openrouter":
            if model_name:
                self.bot.config.openrouter_model_name = model_name
        elif provider_key == "nim":
            self.bot.config.nim_model_name = model_name or "qwen/qwen3-next-80b-a3b-instruct"
        elif provider_key == "kiro":
            self.bot.config.kiro_model_name = model_name or "minimax-m2.5"
        else:  # custom
            self.bot.config.custom_model_name = model_name
            self.bot.config.custom_disable_thinking = disable_thinking

        # ── Persistir ANTES de recrear ──
        self._save_config()

        # ── Recrear LLMClient ──
        from utils.llm_client import create_llm_client, GoogleLLM, OpenRouterLLM, CustomLLM

        try:
            new_llm = create_llm_client(self.bot.config)

            # CORRECCIÓN: load() puede ser async o sync. Intentamos ambos.
            ok = False
            try:
                if asyncio.iscoroutinefunction(new_llm.load):
                    ok = await asyncio.wait_for(new_llm.load(), timeout=15.0)
                else:
                    ok = new_llm.load()
            except Exception as load_exc:
                logger.error("Error en load() del nuevo cliente: {}", load_exc)
                ok = False

            if not ok:
                # ROLLBACK: Restaurar config y cliente anterior
                self.bot.config.llm_provider = old_provider
                self.bot.config.google_model_name = old_google_model
                self.bot.config.openrouter_model_name = old_openrouter_model
                self.bot.config.custom_model_name = old_custom_model
                self.bot.config.custom_disable_thinking = old_disable_thinking
                self.bot.config.kiro_model_name = old_kiro_model
                self._save_config()

                await interaction.followup.send(
                    f"❌ No se pudo inicializar `{provider_key}`. "
                    "Se restauró el modelo anterior. "
                    "Revisa las credenciales en .env.",
                    ephemeral=True,
                )
                return

            # ── Resultado ──
            actual_model = new_llm.get_model_name()

            thinking = ""
            if provider_key == "custom" and self.bot.config.custom_disable_thinking:
                thinking = " (thinking OFF)"
            await interaction.followup.send(
                f"✅ LLM ({pipeline}) → `{provider_key}` : `{actual_model}`{thinking}",
                ephemeral=True,
            )

            # ── Cerrar cliente anterior antes de swap ──
            if old_llm is not None and old_llm is not new_llm:
                try:
                    if hasattr(old_llm, 'close'):
                        if asyncio.iscoroutinefunction(old_llm.close):
                            await asyncio.wait_for(old_llm.close(), timeout=5.0)
                        else:
                            old_llm.close()
                except Exception as close_exc:
                    logger.warning("Error cerrando cliente anterior: {}", close_exc)

            # ── Swap en caliente ──
            if pipeline == "public":
                old_pub = self.bot.orchestrator.llm_public
                self.bot.orchestrator.llm_public = new_llm
                if old_pub is not None and old_pub is not new_llm and old_pub is not self.bot.orchestrator.llm:
                    try:
                        if hasattr(old_pub, 'close') and asyncio.iscoroutinefunction(old_pub.close):
                            await asyncio.wait_for(old_pub.close(), timeout=5.0)
                    except Exception:
                        pass
            else:
                self.bot.llm = new_llm
                self.bot.orchestrator.llm = new_llm

            logger.info(
                "ModelSwitcher: swapped to {} ({}) | previous was {}",
                provider_key, actual_model, old_provider,
            )

        except Exception as exc:
            # ROLLBACK en caso de excepción no manejada
            self.bot.config.llm_provider = old_provider
            self.bot.config.google_model_name = old_google_model
            self.bot.config.openrouter_model_name = old_openrouter_model
            self.bot.config.custom_model_name = old_custom_model
            self.bot.config.custom_disable_thinking = old_disable_thinking
            self.bot.config.kiro_model_name = old_kiro_model
            self._save_config()

            logger.exception("Error al cambiar modelo")
            await interaction.followup.send(
                f"❌ Error crítico: {exc}. Se restauró el modelo anterior.", ephemeral=True
            )


async def setup(bot) -> None:
    await bot.add_cog(ModelSwitcher(bot))
