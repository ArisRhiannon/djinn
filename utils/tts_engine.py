"""
Motor TTS de Fairy — Piper TTS (subprocess).
Las rutas al binario y al modelo se leen desde YoukaiConfig,
eliminando las rutas absolutas hardcodeadas de la versión anterior.
"""

from __future__ import annotations
import io
import os
import re
import logging
import subprocess
from typing import List, Optional

import discord

logger = logging.getLogger("youkai.tts")


class TTSEngine:
    def __init__(self, config) -> None:
        self.config = config
        self._piper_bin: str    = config.piper_bin
        self._model: str        = config.piper_model
        self._model_config: str = config.piper_config_path
        self._ready: bool       = False

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def load(self) -> bool:
        """
        Verifica que el binario de Piper y el modelo existan.
        No realiza síntesis — solo comprueba disponibilidad.
        """
        import shutil

        bin_path = shutil.which(self._piper_bin) or (
            self._piper_bin if os.path.isfile(self._piper_bin) else None
        )
        if not bin_path:
            logger.error(
                "Binario de Piper no encontrado: '{}'. "
                "Instala piper-tts o ajusta PIPER_BIN en .env.",
                self._piper_bin,
            )
            return False

        if not os.path.isfile(self._model):
            logger.error(
                "Modelo Piper no encontrado: '{}'. "
                "Ajusta PIPER_MODEL en .env.",
                self._model,
            )
            return False

        self._piper_bin = bin_path   # guardar la ruta resuelta
        self._ready = True
        logger.info("PiperTTS listo. Modelo: {}", self._model)
        return True

    @property
    def available(self) -> bool:
        return self._ready

    # ── Síntesis ───────────────────────────────────────────────────────────

    def synthesize(self, text: str) -> Optional[bytes]:
        """
        Sintetiza texto a audio WAV usando Piper (síncrono).
        Debe llamarse siempre desde run_in_executor.
        """
        if not self._ready:
            return None

        cmd = [self._piper_bin, "--model", self._model]
        if os.path.isfile(self._model_config):
            cmd += ["--config", self._model_config]
        cmd += ["--output-raw"]   # PCM crudo sin cabecera WAV

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = proc.communicate(
                input=text.encode("utf-8"), timeout=30
            )
            if proc.returncode != 0:
                logger.error("Piper error (rc={}): {}", proc.returncode, stderr.decode())
                return None
            return stdout
        except subprocess.TimeoutExpired:
            proc.kill()
            logger.error("Piper tardó más de 30s — proceso cancelado.")
            return None
        except Exception:
            logger.exception("Error en síntesis Piper.")
            return None

    async def speak(self, text: str, voice_client: discord.VoiceClient) -> None:
        """Sintetiza y reproduce audio en el VoiceClient (async wrapper)."""
        audio_bytes = self.synthesize(text)
        if not audio_bytes:
            return
        try:
            source = discord.FFmpegPCMAudio(io.BytesIO(audio_bytes))
            voice_client.play(source)
        except Exception:
            logger.exception("Error reproduciendo audio en VC.")

    # ── Utilidades de texto ────────────────────────────────────────────────

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """
        Divide el texto en frases para síntesis progresiva.
        Minimiza la latencia percibida al reproducir frase por frase.
        """
        # Separar en '.', '!', '?', ';' y saltos de línea
        sentences = re.split(r"(?<=[.!?;])\s+|\n+", text.strip())
        return [s.strip() for s in sentences if s.strip()]
