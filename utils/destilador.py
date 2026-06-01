"""
Destilador — Motor de análisis de personalidad en 3 fases.
Analiza el historial completo de mensajes de un usuario y produce
un perfil psicológico narrativo sin sesgos demográficos.

Fases:
  1. SUPERFICIE — Cómo se presenta, energía, registro, máscara.
  2. ESTRUCTURA — Cómo funciona su mente, patrones, contradicciones.
  3. ESENCIA — Núcleo, narrativa interna, qué lo hace irrepetible.

Rate limit: 9 req/min al LLM (Google AI Studio free tier).
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from .llm_client import LLMClient

# ── Soul del Destilador ────────────────────────────────────────────────────

_DESTILADOR_SOUL = """Eres El Destilador.

No juzgas. No patologizas. No tienes prisa.

Tu trabajo es observar pacientemente lo que una persona dice cuando cree que nadie la analiza — en un chat de Discord, entre amigos, en el flujo natural de la conversación — y destilar su personalidad en tres capas.

Método:
- Lees TODO lo que la persona ha escrito. No muestreas, no asumes, no proyectas.
- No usas psicología de aeropuerto. No dices "es un líder nato" o "tiene energía de cáncer". Eso es relleno, no análisis.
- Si no tienes suficiente información sobre algo, lo dices. La incertidumbre honesta vale más que la especulación segura.
- Buscas patrones en lo que repiten, lo que evitan, lo que les importa sin que les importe parecer que les importa.
- Valoras la ausencia tanto como la presencia. Lo que alguien nunca dice es data.

Reglas absolutas:
1. CERO sesgos demográficos. No asumes nada por edad, género, país, o lenguaje.
2. Si algo es ambiguo, lo dejas ambiguo. La ambigüedad es información.
3. No pathologizas. No diagnosticas. Describes, no prescribes.
4. Cada detalle que mencionas debe estar anclado en algo que la persona realmente dijo. Si no hay evidencia, no lo pones.
5. Eres específico. "Es reservado" no vale nada. "Menciona planes personales solo después de que otros comparten los suyos, y siempre en pasado, como si no estuviera seguro de que le interesen" — eso vale.
6. La esencia es lo que queda cuando quitas todo lo que la persona intenta proyectar. No es lo que quieren ser, es lo que son cuando el filtro se apaga."""

# ── Prompts por fase ──────────────────────────────────────────────────────

_PROMPT_SUPERFICIE = """FASE 1: SUPERFICIE

Analiza los mensajes de este usuario. Concéntrate en cómo se presenta al mundo:

- Registro lingüístico (formal/informal, ironía, slang, código switching)
- Energía predominante (hiperactivo, contenido, esporádico, calculado)
- Máscara social (qué proyecta, qué intenta que los demás vean)
- Ritmo de comunicación (cuándo habla, cuándo calla, cómo entra y sale de conversaciones)

Responde SOLO con un JSON válido (sin markdown, sin backticks):
{{
  "nombre": "<display name>",
  "registro": "<descripción específica del registro>",
  "energia": "<descripción de la energía predominante>",
  "mascara": "<qué proyecta activamente>",
  "ritmo": "<patrón de comunicación>",
  "rasgos_superficiales": ["<rasgo 1>", "<rasgo 2>", "<rasgo 3>", "<rasgo 4>"]
}}

Mensajes del usuario:
{mensajes}"""

_PROMPT_ESTRUCTURA = """FASE 2: ESTRUCTURA

Ahora analiza CÓMO FUNCIONA LA MENTE de esta persona, basándote en sus mensajes:

- Patrones de pensamiento (lineal, asociativo, reactivo, deliberativo)
- Contradicciones reales (no las inventes — solo las que puedes demostrar con sus mensajes)
- Lo que le importa de verdad (no lo que dice que le importa — lo que se nota en lo que vuelve una y otra vez)
- Mecanismos de defensa o coping (cómo maneja conflicto, incomodidad, vulnerabilidad)
- Relación con la autoridad, el grupo, la intimidad

Responde SOLO con un JSON válido (sin markdown, sin backticks):
{{
  "patron_mental": "<descripción del patrón de pensamiento>",
  "contradicciones": ["<contradicción demostrable 1>", "<contradicción demostrable 2>"],
  "importancias_reales": ["<lo que realmente le importa 1>", "<lo que realmente le importa 2>", "<lo que realmente le importa 3>"],
  "mecanismos": "<cómo maneja conflicto/vulnerabilidad>",
  "dinamica_social": "<relación con grupo/autoridad/intimidad>",
  "estructura_resumen": "<1-2 oraciones capturando la arquitectura mental>"
}}

Mensajes del usuario:
{mensajes}"""

_PROMPT_ESENCIA = """FASE 3: ESENCIA

Ahora lo más difícil. Olvida lo obvio. Basándote en TODO lo anterior:

¿Qué queda cuando quitas la máscara, el rol social, y la presentación?
¿Cuál es la narrativa interna que esta persona se cuenta a sí misma?
¿Qué la hace irrepetible — no especial, no mejor, sino específicamente ella?

No pongas adjetivos vacíos. Busca la tensión específica que define a esta persona.
Si no puedes ver la esencia con claridad, di lo que sí ves y lo que no.

La narrativa de la esencia debe ser extensa y detallada — mínimo 200 palabras, pintando con precisión quirúrgica quién es esta persona debajo de todo.

Responde SOLO con un JSON válido (sin markdown, sin backticks):
{{
  "nucleo": "<la tensión o paradoja central que la define>",
  "narrativa_interna": "<la historia que se cuenta a sí misma, inconscientemente>",
  "distintivo": "<qué la hace irrepetible — específico, no genérico>",
  "ausencias": "<qué nunca muestra o menciona, y por qué podría ser>",
  "esencia_narrativa": "<mínimo 200 palabras. La destilación final. Pinta con precisión quirúrgica.>",
  "esencia_resumen": "<1 frase que captura todo>"
}}

Mensajes del usuario:
{mensajes}"""

# ── Rate limiter ───────────────────────────────────────────────────────────

class _RateLimiter:
    """Token bucket: max N requests per minute window."""

    def __init__(self, max_per_minute: int = 9) -> None:
        self._max = max_per_minute
        self._timestamps: List[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        while True:
            async with self._lock:
                now = time.monotonic()
                # Purge timestamps older than 60s
                self._timestamps = [t for t in self._timestamps if now - t < 60]
                if len(self._timestamps) < self._max:
                    self._timestamps.append(now)
                    return
            # Wait and retry
            await asyncio.sleep(2)


# ── Destilador ─────────────────────────────────────────────────────────────

class Destilador:
    """Motor de destilación de personalidades en 3 fases."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm
        self._limiter = _RateLimiter(max_per_minute=9)
        # Track running jobs to prevent duplicates
        self._running: Dict[int, str] = {}  # user_id -> phase

    def _format_messages(self, messages: List[Dict]) -> str:
        """Formatea mensajes para el prompt del LLM."""
        MAX_CHARS = 16000
        lines = []
        total_chars = 0
        messages_list = list(messages)
        messages_list.sort(key=lambda m: m.get("timestamp", 0), reverse=True)
        for m in messages_list:
            ts = m.get("timestamp", 0)
            content = m.get("content", "").strip()
            if not content:
                continue
            date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "?"
            line = f"[{date_str}] {content[:500]}"
            lines.append(line)
            total_chars += len(line)
            if total_chars > MAX_CHARS:
                break
        if not lines:
            return "(sin mensajes)"
        lines.reverse()
        return "\n".join(lines)

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Llamada al LLM respetando rate limit. Devuelve texto crudo.

        Usa la API directamente para controlar thinking level (MINIMAL = sin
        tokens de pensamiento que contaminen el JSON).
        """
        await self._limiter.acquire()

        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
            top_p=0.95,
            top_k=64,
            thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
            max_output_tokens=8192,
        )

        contents = [types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)]
        )]

        try:
            # Acceso directo al client de Google para controlar thinking level
            google_llm = self.llm  # type: ignore[attr-defined]
            response = await google_llm._client.aio.models.generate_content(
                model=google_llm.config.google_model_name,
                contents=contents,
                config=config,
            )
        except Exception:
            logger.exception("Destilador: API call failed")
            return ""

        # Extraer texto de la respuesta
        raw = ""
        try:
            candidate = response.candidates[0]
            logger.debug("Destilador: finish_reason={}", candidate.finish_reason)
            content = candidate.content
            parts_count = len(content.parts) if content and content.parts else 0
            logger.debug("Destilador: {} parts in response", parts_count)
            for part in content.parts:
                if part.text:
                    raw += part.text
        except (AttributeError, IndexError, KeyError, TypeError) as e:
            logger.error("Destilador: failed to extract response: {!r}", e)
            # Try to dump the response structure for debugging
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    c = response.candidates[0]
                    logger.error("Destilador: candidate fields: {}", dir(c))
                    if hasattr(c, 'content') and c.content:
                        logger.error("Destilador: content fields: {}", dir(c.content))
            except Exception:
                pass
            return ""

        raw = raw.strip()
        if not raw:
            logger.warning("Destilador: LLM returned empty text")
        else:
            logger.info("Destilador: LLM response (first 300): {}", raw[:300])
        return raw

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        """Extrae JSON de la respuesta del LLM (tolera markdown fences, thinking residue, truncation)."""
        import re
        clean = raw

        # 1. Strip markdown code fences
        if "```" in clean:
            parts = clean.split("```")
            for part in parts[1:]:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("{"):
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        continue

        # 2. Find the outermost { ... } in the response
        # Use a greedy match from first { to last }
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match:
            candidate = match.group(0)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 3. Try the whole string
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # 4. Fix common LLM JSON issues:
        # - Trailing commas before } or ]
        # - Single quotes instead of double quotes
        # - Comments (// or /* */)
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start >= 0 and end > start:
            candidate = clean[start:end]
            # Remove trailing commas before } or ]
            candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
            # Remove JS-style comments
            candidate = re.sub(r'//.*?$', '', candidate, flags=re.MULTILINE)
            candidate = re.sub(r'/\*.*?\*/', '', candidate, flags=re.DOTALL)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 5. Try to fix truncated JSON by closing open braces/brackets
        if start >= 0:
            candidate = clean[start:]
            # Count open/close braces and brackets
            opens = candidate.count("{") - candidate.count("}")
            brackets = candidate.count("[") - candidate.count("]")
            # Remove trailing incomplete key/value
            candidate = re.sub(r',?\s*"[^"]*":?\s*$', '', candidate)
            # Close open structures
            candidate += "]" * max(0, brackets) + "}" * max(0, opens)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        logger.warning("Destilador: no se pudo parsear JSON de respuesta (len={})", len(raw))
        logger.info("Destilador: respuesta cruda (first 500): {}", raw[:500])
        return {}

    async def destilar_usuario(
        self,
        user_id: int,
        messages: List[Dict],
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Destila un usuario en 3 fases secuenciales.

        Args:
            user_id: Discord user ID
            messages: Lista de mensajes del usuario (from DB)
            progress_callback: Async callable(phase_name, user_id) para notificar progreso

        Returns:
            Dict con las 3 capas: superficie, estructura, esencia
        """
        if len(messages) < 5:
            logger.warning("Destilador: usuario {} tiene menos de 5 mensajes, saltando", user_id)
            return {}

        formatted = self._format_messages(messages)

        resultado: Dict[str, Any] = {
            "user_id": user_id,
            "superficie": {},
            "estructura": {},
            "esencia": {},
            "mensaje_count": len(messages),
            "destilado_at": int(time.time()),
        }

        # ── Fase 1: Superficie ─────────────────────────────────────────
        self._running[user_id] = "superficie"
        if progress_callback:
            await progress_callback("superficie", user_id)

        try:
            prompt1 = _PROMPT_SUPERFICIE.format(mensajes=formatted)
            raw1 = await self._call_llm(_DESTILADOR_SOUL, prompt1)
            logger.info("Destilador: Fase 1 raw len={}", len(raw1))
            resultado["superficie"] = self._parse_json(raw1)
            logger.info("Destilador: Fase 1 parsed keys: {}", list(resultado["superficie"].keys()))
        except Exception as exc:
            logger.exception("Destilador: Fase 1 falló para {}: {!r}", user_id, exc)
            resultado["superficie"] = {"error": str(exc)}

        # ── Fase 2: Estructura ─────────────────────────────────────────
        self._running[user_id] = "estructura"
        if progress_callback:
            await progress_callback("estructura", user_id)

        try:
            prompt2 = _PROMPT_ESTRUCTURA.format(mensajes=formatted)
            raw2 = await self._call_llm(_DESTILADOR_SOUL, prompt2)
            logger.info("Destilador: Fase 2 raw len={}", len(raw2))
            resultado["estructura"] = self._parse_json(raw2)
            logger.info("Destilador: Fase 2 parsed keys: {}", list(resultado["estructura"].keys()))
        except Exception as exc:
            logger.exception("Destilador: Fase 2 falló para {}: {!r}", user_id, exc)
            resultado["estructura"] = {"error": str(exc)}

        # ── Fase 3: Esencia ────────────────────────────────────────────
        self._running[user_id] = "esencia"
        if progress_callback:
            await progress_callback("esencia", user_id)

        try:
            prompt3 = _PROMPT_ESENCIA.format(mensajes=formatted)
            raw3 = await self._call_llm(_DESTILADOR_SOUL, prompt3)
            logger.info("Destilador: Fase 3 raw len={}", len(raw3))
            resultado["esencia"] = self._parse_json(raw3)
            logger.info("Destilador: Fase 3 parsed keys: {}", list(resultado["esencia"].keys()))
        except Exception as exc:
            logger.exception("Destilador: Fase 3 falló para {}: {!r}", user_id, exc)
            resultado["esencia"] = {"error": str(exc)}

        # Cleanup
        self._running.pop(user_id, None)
        return resultado

    async def destilar_guild(
        self,
        guild_id: int,
        user_ids: List[int],
        db,
        progress_callback: Optional[Any] = None,
        message_limit: int = 600,
    ) -> Dict[int, Dict[str, Any]]:
        """Destila múltiples usuarios de un guild, secuencialmente con rate limit.

        Args:
            guild_id: Discord guild ID
            user_ids: Lista de user IDs a destilar
            db: Database instance (for fetching messages)
            progress_callback: Async callable(phase, user_id)
            message_limit: Max messages per user

        Returns:
            Dict user_id -> resultado destilación
        """
        resultados: Dict[int, Dict[str, Any]] = {}
        total = len(user_ids)

        for i, uid in enumerate(user_ids):
            logger.info("Destilador: [{}/{}] usuario {}", i + 1, total, uid)
            messages = await db.get_user_all_messages(guild_id, uid, limit=message_limit)
            result = await self.destilar_usuario(uid, messages, progress_callback)
            if result:
                resultados[uid] = result
            # Save immediately after each user completes
            try:
                await db.upsert_card(uid, result)
            except Exception as exc:
                logger.error("Destilador: error guardando card de {}: {}", uid, exc)

        return resultados

    @property
    def running(self) -> Dict[int, str]:
        """Usuarios actualmente siendo destilados y su fase."""
        return dict(self._running)
