"""
Cog: NLP Handler — procesa menciones, gestiona attachments, delega al
Orchestrator, aplica Repetition Shield y smart chunking.

Flujo:
  mensaje → permisos → media → Orchestrator → RepetitionShield
    → (si spam: reintento con budget reducido) → smart_chunk → send
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import cv2
import discord
from discord.ext import commands
from loguru import logger

from utils.repetition_shield import RepetitionShield, smart_chunk
from utils.security import can_use_youkai_nl

# ── Límites de seguridad ───────────────────────────────────────────────────────
MAX_ATTACHMENT_SIZE_MB: int = 50
MAX_ATTACHMENTS: int = 5
MAX_VIDEO_FRAMES: int = 60

# Smart chunking: párrafos → oraciones → palabras (en lugar de cortar a ciegas)
MAX_CHUNK_CHARS: int = 1_900
MAX_CHUNKS: int = 10  # 10 * 1900 = 19K chars ≈ 5.4K tokens — más que suficiente

# Reintento anti-spam
_RETRY_MAX_OUTPUT_TOKENS: int = 2_048  # budget reducido en reintento
_MAX_RETRIES: int = 1  # solo 1 reintento para evitar loop

# Semáforo para limitar procesamiento concurrente de vídeos
_VIDEO_SEMAPHORE = asyncio.Semaphore(2)


class NLPHandlerCog(commands.Cog, name="NLP"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Procesamiento de vídeo ─────────────────────────────────────────────

    def _extract_frames_sync(self, tmp_path: str) -> list[bytes]:
        """
        Extrae 1 frame por segundo del vídeo (hasta MAX_VIDEO_FRAMES).
        SÍNCRONO — llamar siempre desde run_in_executor.
        """
        frames: list[bytes] = []
        cap = cv2.VideoCapture(tmp_path)
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                logger.error("NLP: no se pudo determinar FPS del vídeo.")
                return frames

            frame_interval = max(1, int(fps))

            for count in range(MAX_VIDEO_FRAMES):
                cap.set(cv2.CAP_PROP_POS_FRAMES, count * frame_interval)
                success, frame = cap.read()
                if not success:
                    break
                ok, buffer = cv2.imencode(".jpg", frame)
                if ok:
                    frames.append(buffer.tobytes())
        finally:
            cap.release()

        logger.info("NLP: {} frames extraídos del vídeo.", len(frames))
        return frames

    async def _process_video(self, attachment: discord.Attachment) -> list[bytes]:
        suffix = os.path.splitext(attachment.filename)[1] or ".mp4"
        async with _VIDEO_SEMAPHORE:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = tmp.name
                await attachment.save(tmp_path)

            try:
                loop = asyncio.get_running_loop()
                frames = await loop.run_in_executor(
                    None, self._extract_frames_sync, tmp_path
                )
            except Exception:
                logger.exception("NLP: error extrayendo frames de '{}'.", attachment.filename)
                frames = []
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        return frames

    # ── Listener principal ─────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild:
            return

        # Fairy overseer bot — permitido en su canal dedicado
        _FAIRY_BOT_ID = 1488300519234470108
        _FAIRY_CHANNEL_ID = 1503470561605451896
        is_fairy = (message.author.id == _FAIRY_BOT_ID and message.channel.id == _FAIRY_CHANNEL_ID)

        # Webhooks solo en Bernkastel Mukaide
        is_webhook = bool(message.webhook_id)
        if is_webhook and message.guild.id != 1154524624743317605:
            return

        # Ignorar bots excepto Fairy y webhooks permitidos
        if message.author.bot and not is_fairy and not is_webhook:
            return

        # ── Passive credit earning (all non-reader users) ──────────────
        if not is_webhook and not is_fairy and not await can_use_youkai_nl(message.author, self.bot.db):
            try:
                from utils.credit_economy import earn_passive
                await earn_passive(self.bot.db, message)
            except Exception:
                pass

        if self.bot.user not in message.mentions:
            return

        # Ignorar si es una respuesta a un mensaje inerte (como el corrector de enlaces)
        if message.reference and message.reference.resolved:
            resolved = message.reference.resolved
            if isinstance(resolved, discord.Message) and resolved.author.id == self.bot.user.id:
                is_inert = False
                if hasattr(self.bot, "inert_message_ids") and resolved.id in self.bot.inert_message_ids:
                    is_inert = True
                else:
                    # Fallback por contenido (si el bot se reinició y se limpió la caché en memoria)
                    content = resolved.content
                    if isinstance(content, str):
                        content = content.strip()
                        if content:
                            import re
                            fixed_domains = (
                                "fxtwitter.com", "vxtiktok.com", "toinstagram.com", 
                                "vxinstagram.com", "eeinstagram.com", "fixfacebook.com", 
                                "rxddit.com"
                            )
                            # Limpiar enlaces con formato markdown [Nombre](<url>) y [Nombre](url)
                            cleaned = re.sub(r'\[[^\]]+\]\(<[^>]+>\)', '', content)
                            cleaned = re.sub(r'\[[^\]]+\]\(https?://[^\s)]+\)', '', cleaned)
                            # Limpiar URLs planas
                            cleaned = re.sub(r'https?://[^\s]+', '', cleaned)
                            # Limpiar separadores y espacios
                            cleaned = cleaned.replace('•', '').replace('\n', '').replace(' ', '').strip()
                            
                            # Si solo quedaron enlaces y separadores, y hay al menos un dominio corregido
                            if not cleaned and any(domain in content for domain in fixed_domains):
                                is_inert = True
                    
                    # Fallback por embeds de acciones de rol interactivo (hug, kiss, pat, heal)
                    if not is_inert and resolved.embeds:
                        emb = resolved.embeds[0]
                        desc = (emb.description or "").lower()
                        action_keywords = (
                            "abrazo", "abrazó",
                            "beso", "besó",
                            "acarició", "caricia",
                            "curación", "curó"
                        )
                        if any(kw in desc for kw in action_keywords):
                            is_inert = True
                
                if is_inert:
                    logger.info("NLP: Ignorando mención por ser respuesta a un mensaje inerte.")
                    return

        logger.info(
            "NLP: mención de {} en '{}'", message.author, message.guild.name
        )

        # El Orchestrator se encarga del strip de menciones y whitespace.
        # Aquí solo verificamos que haya algo que procesar.
        has_content = bool(message.content.strip()) or bool(message.attachments)
        if not has_content:
            return

        # Verificar permisos (webhooks y Fairy se tratan como reader)
        if not is_webhook and not is_fairy and not await can_use_youkai_nl(message.author, self.bot.db):
            # ── Public pipeline (credit-gated) ─────────────────────────
            await self._handle_public_pipeline(message)
            return

        # ── Recopilar media ────────────────────────────────────────────────
        media_content: list[bytes] = []
        max_bytes = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024

        attachments = message.attachments[:MAX_ATTACHMENTS]
        if len(message.attachments) > MAX_ATTACHMENTS:
            logger.warning(
                "NLP: {} attachments — se procesan solo los primeros {}.",
                len(message.attachments), MAX_ATTACHMENTS,
            )

        for attachment in attachments:
            if attachment.size > max_bytes:
                logger.warning(
                    "NLP: '{}' ({} MB) supera el límite de {} MB — omitido.",
                    attachment.filename,
                    attachment.size // (1024 * 1024),
                    MAX_ATTACHMENT_SIZE_MB,
                )
                continue

            content_type = attachment.content_type or ""
            try:
                if "image" in content_type:
                    media_content.append(await attachment.read())
                elif "video" in content_type:
                    frames = await self._process_video(attachment)
                    media_content.extend(frames)
            except (discord.HTTPException, discord.NotFound) as exc:
                logger.warning(
                    "NLP: no se pudo descargar '{}': {}", attachment.filename, exc
                )

        # ── Llamada al Orchestrator + Repetition Shield ────────────────────
        async with message.channel.typing():
            try:
                logger.info(
                    "NLP: enviando al Orchestrator — text='{}', media={}",
                    message.content[:50], len(media_content),
                )
                _ARIS_ID = 239550977638793217
                result = await self.bot.orchestrator.process_message(
                    message, media=media_content,
                    system_override=(message.author.id == _ARIS_ID),
                )

                if not result:
                    # Orchestrator devolvio None => error transitorio de API,
                    # mensaje vacio tras strip, o media-only sin prompt procesable.
                    # Reaccionar discretamente en vez de enviar texto tecnico.
                    logger.warning("NLP: Orchestrator devolvio resultado vacio.")
                    try:
                        await message.add_reaction("⚠️")
                    except (discord.HTTPException, discord.Forbidden):
                        pass
                    return

                # ── Repetition Shield ──────────────────────────────────────
                shield_result = RepetitionShield.check(result)

                if not shield_result.clean:
                    logger.warning(
                        "NLP: RepetitionShield detectó {} (score={:.2f}). "
                        "Preview: '{}'",
                        shield_result.reason,
                        shield_result.score,
                        result[:80],
                    )

                    # Reintento con budget reducido
                    retry_text = await self._retry_without_spam(
                        message, media_content, shield_result
                    )
                    if retry_text:
                        result = retry_text
                    else:
                        # Usar texto trimmeado del shield como fallback
                        result = shield_result.trimmed_text

                # ── Smart chunking + envío ──────────────────────────────────
                await self._send_fragmented(message, result)

            except Exception:
                logger.exception("NLP: error critico en el flujo de procesamiento.")
                # Reaccion discreta en vez de reply con mensaje tecnico
                try:
                    await message.add_reaction("⚠️")
                except (discord.HTTPException, discord.Forbidden):
                    pass

    # ── Public pipeline (credit-gated) ─────────────────────────────────────

    async def _handle_public_pipeline(self, message: discord.Message) -> None:
        from utils.credit_economy import can_spend, COST_WITH_TOOLS

        ok, reason, info = await can_spend(
            self.bot.db, message.author.id, message.guild.id, COST_WITH_TOOLS
        )
        if not ok:
            await message.add_reaction("🔒")
            loan_cog = self.bot.get_cog("LoanShark")
            if loan_cog:
                await loan_cog.offer_loan(message, cost=COST_WITH_TOOLS, balance=info.get("balance", 0))
            else:
                try:
                    await message.reply(
                        f"⚡ {reason} Gana créditos participando en el server.",
                        mention_author=False, delete_after=10,
                    )
                except discord.HTTPException:
                    pass
            return

        async with message.channel.typing():
            result = await self.bot.orchestrator.process_message_public(message)

        if not result:
            await message.add_reaction("⚠️")
            return

        # Deduct credits
        new_balance = await self.bot.db.spend_credits(
            message.author.id, message.guild.id, COST_WITH_TOOLS, reason="llm"
        )
        updated = await self.bot.db.get_credits(message.author.id, message.guild.id)

        # Inject footer with score
        score_data = await self.bot.db.get_loan_score(message.author.id, message.guild.id)
        active_loan = await self.bot.db.get_active_loan(message.author.id, message.guild.id)
        score_str = f" • 📊 {score_data['score']}"
        debt_str = f" • ⚠️ Deuda: {active_loan['remaining_debt']}" if active_loan else ""
        footer = f"\n-# ⚡ -{COST_WITH_TOOLS} • Saldo: {new_balance} • Hoy: {updated['calls_today']}/10{score_str}{debt_str}"
        result += footer

        await self._send_fragmented(message, result)

    # ── Reintento anti-spam ────────────────────────────────────────────────

    async def _retry_without_spam(
        self,
        message: discord.Message,
        media_content: list[bytes],
        shield_result,
    ) -> str | None:
        """
        Reintento con max_output_tokens reducido y prompt anti-repetición.
        Retorna la nueva respuesta o None si falla.
        """
        try:
            # Inyectar aviso anti-repetición en el historial del canal
            channel_id = message.channel.id
            history = self.bot.orchestrator._get_history(channel_id)

            # Añadir un turno de sistema como user para forzar corrección
            from google.genai import types
            correction = (
                "[SYSTEM NOTICE: Your previous response was flagged as repetitive "
                f"(reason: {shield_result.reason}). "
                "Be concise and direct. Do NOT repeat phrases or patterns.]"
            )
            # Guardar longitud para revertir después
            original_len = len(history)
            history.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=correction)],
            ))

            result = await self.bot.orchestrator.process_message(
                message, media=media_content
            )

            # Revertir el historial: eliminar los 2 turnos añadidos (correction + response)
            while len(history) > original_len:
                history.pop()

            # Verificar que el reintento tampoco es spam
            if result:
                retry_shield = RepetitionShield.check(result)
                if retry_shield.clean:
                    logger.info("NLP: reintento exitoso — respuesta limpia.")
                    return result
                else:
                    logger.warning(
                        "NLP: reintento también es spam ({}). Usando trimmed.",
                        retry_shield.reason,
                    )
                    return retry_shield.trimmed_text

        except Exception:
            logger.exception("NLP: error en reintento anti-spam.")

        return None

    # ── Envío fragmentado con smart chunking ───────────────────────────────

    async def _expand_placeholders(self, message: discord.Message, text: str) -> str:
        """Replace [placeholder] tokens with real data."""
        if "[lista_cumpleaños]" not in text and "[birthday_list]" not in text:
            return text

        try:
            cog = self.bot.get_cog("Birthdays")
            if not cog or not message.guild:
                return text.replace("[lista_cumpleaños]", "_(sin datos)_").replace("[birthday_list]", "_(no data)_")

            rows = await cog.get_all_birthdays(message.guild.id)
            if not rows:
                replacement = "_(No hay cumpleaños registrados)_"
            else:
                months = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
                          "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
                lines = []
                for r in rows:
                    member = message.guild.get_member(r["user_id"])
                    name = member.display_name if member else (r.get("name") or str(r["user_id"]))
                    lines.append(f"`{r['day']:02d}/{months[r['month']]}` {name}")
                replacement = " · ".join(lines)

            text = text.replace("[lista_cumpleaños]", replacement)
            text = text.replace("[birthday_list]", replacement)
        except Exception:
            pass
        return text

    async def _send_fragmented(
        self, message: discord.Message, text: str
    ) -> None:
        """
        Envía respuesta usando smart_chunk:
        1. Corta en párrafos (\\n\\n)
        2. Si un párrafo > 1900, corta en oraciones (. ! ?)
        3. Si una oración > 1900, corta en la palabra más cercana a 1900
        4. Máximo 10 chunks (~19K chars ≈ 5.4K tokens)

        Fallback: si message.reply() falla (mensaje borrado por automod),
        usa channel.send() en su lugar.
        """
        # ── Placeholder expansion ──
        text = await self._expand_placeholders(message, text)

        async def _safe_send(content: str, reply: bool = True) -> None:
            try:
                if reply:
                    await message.reply(content, mention_author=False)
                else:
                    await message.channel.send(content)
            except discord.HTTPException:
                # El mensaje original fue borrado (automod, etc.)
                await message.channel.send(content)

        if len(text) <= 2_000:
            await _safe_send(text)
            return

        chunks = smart_chunk(text, max_chunk=MAX_CHUNK_CHARS, max_chunks=MAX_CHUNKS)
        total = len(chunks)

        if total == 1:
            await _safe_send(text[:2_000])
            return

        for i, chunk in enumerate(chunks, start=1):
            await _safe_send(f"[{i}/{total}]\n{chunk}", reply=(i == 1))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NLPHandlerCog(bot))
