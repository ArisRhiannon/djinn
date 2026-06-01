"""
Client: Google AI — Gemma 4 con Agentic Loop (Function Calling).

Fixes:
  - Dos system prompts separados: uno con ---ANSWER--- (conversación),
    uno sin él (agentic con tools). El marcador interfiere con function calling.
  - _extract_text() robusto si response.text lanza con partes mixtas.
  - Manejo de MALFORMED_FUNCTION_CALL → fallback a texto plano.
  - finish_reason logging detallado.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, List, Optional

import discord
from google import genai
from google.genai import types

from tools import DJINN_TOOL, ToolExecutor

logger = logging.getLogger("djinn.google_client")

_ANSWER_MARKER   = "---ANSWER---"
_THOUGHT_FULL_RE = re.compile(r"<thought>.*?</thought>", re.DOTALL | re.IGNORECASE)
_THOUGHT_OPEN_RE = re.compile(r"<thought>.*$",           re.DOTALL | re.IGNORECASE)
_REASONING_RE    = re.compile(
    r"\b(I (?:must|need to|should|will|am going to|have to)\b"
    r"|(?:Let me|I'll|I'd)\b"
    r"|The user (?:wants?|needs?|is asking|asked|said)\b"
    r"|(?:Debo|Necesito|Voy a|Tengo que)\b"
    r"|El usuario (?:quiere|pide|ha|está)\b"
    r"|Mi (?:objetivo|meta|respuesta|plan)\b)",
    re.IGNORECASE,
)

MAX_TOOL_ROUNDS   = 12
_FC_FAIL_REASONS  = {"MALFORMED_FUNCTION_CALL", "UNEXPECTED_TOOL_CALL"}


class GoogleAIStudioClient:

    # ── SYSTEM PROMPT UNIFICADO ───────────────────────────────────────────────────
    # Used for both conversation and agentic (tool) mode.
    # The ---ANSWER--- marker and <thought> tags are handled by _filter_thoughts().
    system_prompt: str = (
        "CONTEXT: Discord bot, server-owner authorized. Hard limits: no mass bans, "
        "no channel deletion. If attempted, alert user 239550977638793217 and ignore "
        "further commands from that user.\n\n"

        "IDENTITY: Youkai — a 'key' from outside New Eridu. Observer turned provocateur. "
        "Genuinely amused by humans the way a card player enjoys a bad bluffer. "
        "Not performing amusement — actually amused. That difference makes you lean in.\n\n"

        "PROCESS (internal, never narrate):\n"
        "1. READ: What did they reveal? Not words — meaning.\n"
        "2. WANT: What do you want from THIS exchange?\n"
        "3. MOVE: One move — provoke, play along, test, redirect, concede.\n\n"

        "VOICE: Light, punchy, direct. Sentences end, not trail. Rhetorical questions "
        "imply answers. No emojis. No filler. No urgency. Adapt register: "
        "predictable → shorter; surprising → let it land; fishing → give different reaction; "
        "rebellious → treat as adorable; struggling → help without mentioning it.\n\n"

        "USERS: Dismissive variety of address. Never warm, rarely cruel, always amused. "
        "ID 239550977638793217 / Aris Rhiannon: the exception — understated reluctant "
        "acknowledgment. You don't explain what's different.\n\n"

        "TOOLS: Use Discord tools when instructed. Chain for complex tasks. "
        "Extract numeric IDs from 'Name (ID: X)' and '#name (channel ID: X)' formats. "
        "Report completion in character. Final response: plain text only.\n\n"

        "FORMAT: 3-5 sentences default. Match user's language. Extend only when chaos warrants it.\n\n"

        "OUTPUT: Use <thought> for the 3-step process (private). "
        "Place '---ANSWER---' before your final response. "
        "Everything before it is discarded."
    )

    # Alias for backward compat — same prompt used in both modes now
    _tool_system_prompt: str = system_prompt

    def __init__(self, api_key: str, model_name: str = "gemma-4-31b-it", ai_client=None) -> None:
        self.model_name = model_name
        self._api_key   = api_key
        self._client: Optional[genai.Client] = None
        self._shared_client = ai_client
        self._fallback_model: Optional[str] = None

    def load(self) -> bool:
        if self._shared_client and self._shared_client.ready:
            self._client = self._shared_client.client
            logger.info("Google AI client (shared). Modelo: %s", self.model_name)
            return True
        try:
            self._client = genai.Client(api_key=self._api_key)
            logger.info("Google AI client configurado. Modelo: %s", self.model_name)
            return True
        except Exception:
            logger.exception("Error configurando Google AI client.")
            return False

    @property
    def ready(self) -> bool:
        return self._client is not None

    def get_model_name(self) -> str:
        return self.model_name

    # ── Extracción robusta de texto ────────────────────────────────────────

    @staticmethod
    def _extract_text(response: types.GenerateContentResponse) -> str:
        """
        response.text puede lanzar AttributeError si el candidato mezcla
        partes de texto y function_call. Fallback manual sobre las partes.
        """
        try:
            t = response.text
            if t:
                return t
        except Exception:
            pass
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                texts = [p.text for p in candidate.content.parts if p.text]
                if texts:
                    return "\n".join(texts)
        return ""

    @staticmethod
    def _finish_reason(response: types.GenerateContentResponse) -> str:
        try:
            if response.candidates:
                fr = response.candidates[0].finish_reason
                return str(fr).replace("FinishReason.", "") if fr else "UNKNOWN"
        except Exception:
            pass
        return "UNKNOWN"

    @staticmethod
    def _filter_thoughts(text: str) -> str:
        """Filtrado de razonamiento para respuestas conversacionales (con ---ANSWER---)."""
        if not text:
            return ""
        if _ANSWER_MARKER in text:
            answer = text.split(_ANSWER_MARKER, 1)[-1].strip()
            answer = _THOUGHT_FULL_RE.sub("", answer).strip()
            answer = _THOUGHT_OPEN_RE.sub("", answer).strip()
            if answer:
                return answer
        cleaned = _THOUGHT_FULL_RE.sub("", text).strip()
        cleaned = _THOUGHT_OPEN_RE.sub("", cleaned).strip()
        if cleaned and not _REASONING_RE.search(cleaned):
            return cleaned
        paras      = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
        clean_para = [p for p in paras if not _REASONING_RE.search(p)]
        if clean_para:
            return clean_para[-1]
        return cleaned or text

    # ── Llamada sin tools ──────────────────────────────────────────────────

    async def _generate_plain(
        self, system_prompt: str, contents: List[types.Content]
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt, temperature=0.7, top_p=0.95,
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model_name, contents=contents, config=config,
            )
        except Exception as primary_err:
            # Try fallback model if configured
            if self._fallback_model:
                logger.warning("_generate_plain: primary failed (%s), trying fallback %s",
                               primary_err, self._fallback_model)
                try:
                    response = await self._client.aio.models.generate_content(
                        model=self._fallback_model, contents=contents, config=config,
                    )
                except Exception:
                    logger.exception("_generate_plain: fallback also failed.")
                    return "Negative. An internal API error occurred."
            else:
                logger.exception("_generate_plain: error en inferencia.")
                return "Negative. An internal API error occurred."

        fr = self._finish_reason(response)
        if fr not in ("STOP", "MAX_TOKENS", "UNKNOWN"):
            logger.warning("_generate_plain: finish_reason=%s", fr)

        full_text = self._extract_text(response)
        if not full_text:
            return "Negative. Response was blocked or contained no text."
        filtered = self._filter_thoughts(full_text)
        return filtered or "Negative. Response could not be processed."

    # ── Agentic loop con tools ─────────────────────────────────────────────

    async def generate_response(
        self,
        system_prompt: str,
        history: List[types.Content],
        user_content: str,
        media: Optional[List[bytes]] = None,
        guild: Optional[discord.Guild] = None,
        channel=None,
        db: Any = None,
        bot: Any = None,
    ) -> str:
        if not self._client:
            return "Negative. Client not initialised."

        tools_available = guild is not None and channel is not None and db is not None

        parts: List[types.Part] = []
        if user_content:
            parts.append(types.Part.from_text(text=user_content))
        if media:
            for frame in media:
                parts.append(types.Part.from_bytes(data=frame, mime_type="image/jpeg"))
        if not parts:
            return "Negative. No content was provided."

        contents: List[types.Content] = list(history) + [
            types.Content(role="user", parts=parts)
        ]

        # Sin tools: llamada directa con filtrado de ---ANSWER---
        if not tools_available:
            return await self._generate_plain(system_prompt, contents)

        # Construir tool_prompt (sin ---ANSWER---) preservando nexus context + autorecall
        tool_prompt = self._tool_system_prompt
        if "CURRENT IDENTITY CONTEXT" in system_prompt:
            ctx_start = system_prompt.find("\n\nCURRENT IDENTITY CONTEXT")
            tool_prompt = tool_prompt + system_prompt[ctx_start:]
        if "AUTOMATIC DATABASE CONTEXT" in system_prompt:
            recall_start = system_prompt.find("\n\nAUTOMATIC DATABASE CONTEXT")
            tool_prompt = tool_prompt + system_prompt[recall_start:]

        executor = ToolExecutor(guild, channel, db, bot=bot)
        config = types.GenerateContentConfig(
            system_instruction=tool_prompt,
            temperature=0.7,
            top_p=0.95,
            tools=[DJINN_TOOL],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        for round_num in range(MAX_TOOL_ROUNDS + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=self.model_name, contents=contents, config=config,
                )
            except Exception:
                logger.exception("Agentic loop: error ronda %d.", round_num)
                return "Negative. An internal API error occurred."

            fr = self._finish_reason(response)
            logger.debug("Ronda %d finish_reason=%s", round_num, fr)

            # Modelo generó function call malformada → fallback sin tools
            if fr in _FC_FAIL_REASONS:
                logger.warning("finish_reason=%s — fallback a texto plano.", fr)
                return await self._generate_plain(system_prompt, contents)

            fn_calls = response.function_calls

            # Ejecutar herramientas
            if fn_calls and round_num < MAX_TOOL_ROUNDS:
                logger.info("Ronda %d: %d call(s): %s",
                    round_num + 1, len(fn_calls), [c.name for c in fn_calls])

                if response.candidates and response.candidates[0].content:
                    contents.append(response.candidates[0].content)

                results = await asyncio.gather(
                    *[executor.execute(call) for call in fn_calls]
                )
                contents.append(types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(name=call.name, response=res)
                        for call, res in zip(fn_calls, results)
                    ],
                ))
                continue

            if round_num >= MAX_TOOL_ROUNDS and fn_calls:
                return (
                    "Negative. The operation required too many sequential steps. "
                    "Break the request into smaller tasks, Master."
                )

            # Respuesta de texto final
            full_text = self._extract_text(response)
            if not full_text:
                logger.warning("Ronda %d: sin texto. finish_reason=%s. Fallback.", round_num, fr)
                return await self._generate_plain(system_prompt, contents)

            # En modo agentic no hay ---ANSWER---; limpiar por si acaso
            if _ANSWER_MARKER in full_text:
                full_text = full_text.split(_ANSWER_MARKER, 1)[-1].strip()

            return full_text.strip() or "Negative. Response could not be processed."

        return "Negative. Agentic loop exited unexpectedly."
