"""
Cog: Link Fixer — Corrige enlaces de Twitter, X, TikTok e Instagram para previsualizaciones.

Usa webhooks para simular la autoría original y mantener el chat limpio,
con soporte para hilos y descargas de adjuntos, además de fallbacks automáticos.
"""
from __future__ import annotations

import logging
import re
from typing import Optional, Tuple
from urllib.parse import urlparse

import aiohttp
import discord
from discord.ext import commands, tasks

logger = logging.getLogger("youkai.link_fixer")

# Regex para extraer URLs
URL_REGEX = re.compile(r'(https?://[^\s]+)')


def fix_links(text: str, instagram_proxy: str = "eeinstagram.com") -> Tuple[str, bool]:
    """Procesa un texto y reemplaza los enlaces que no se previsualizan bien.
    
    Excluye URLs que se encuentren dentro de bloques de código (backticks).
    Retorna (texto_corregido, hubo_reemplazos).
    """
    # Extraer bloques de código para evitar modificar URLs dentro de ellos
    code_blocks = []
    
    def replace_block(match):
        placeholder = f"__YOUKAI_CODE_BLOCK_{len(code_blocks)}__"
        code_blocks.append(match.group(0))
        return placeholder

    # Reemplazar bloques de tres acentos graves y luego de uno para protegerlos
    temp_text = re.sub(r'```[\s\S]*?```', replace_block, text)
    temp_text = re.sub(r'`[^`\n]+`', replace_block, temp_text)

    urls = URL_REGEX.findall(temp_text)
    if not urls:
        return text, False

    replaced = False
    new_text = temp_text

    for url in urls:
        # Conservar puntuación al final de la URL
        clean_url = url
        suffix = ""
        match_end = re.search(r'([.,;:?!)]+)$', url)
        if match_end:
            suffix = match_end.group(1)
            clean_url = url[:-len(suffix)]

        try:
            parsed = urlparse(clean_url)
            netloc = parsed.netloc.lower()
            path = parsed.path

            new_url = None

            # 1. Twitter / X
            if netloc in ("twitter.com", "www.twitter.com", "mobile.twitter.com", "x.com", "www.x.com"):
                new_url = parsed._replace(netloc="fxtwitter.com").geturl()

            # 2. TikTok
            elif netloc in ("tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"):
                if netloc == "vm.tiktok.com":
                    new_netloc = "vm.tnktok.com"
                elif netloc == "vt.tiktok.com":
                    new_netloc = "vt.tnktok.com"
                else:
                    new_netloc = "tnktok.com"
                new_url = parsed._replace(netloc=new_netloc).geturl()

            # 3. Instagram (solo posts, reels, IGTV, share)
            elif netloc in ("instagram.com", "www.instagram.com"):
                is_post_or_reel = any(
                    path.startswith(prefix) for prefix in (
                        "/p/", "/reel/", "/reels/", "/tv/", "/share/p/", "/share/reel/", "/share/reels/"
                    )
                )
                if is_post_or_reel:
                    new_path = path
                    if path.startswith("/reels/"):
                        new_path = path.replace("/reels/", "/reel/", 1)
                    elif path.startswith("/share/reels/"):
                        new_path = path.replace("/share/reels/", "/share/reel/", 1)
                    new_url = parsed._replace(netloc=instagram_proxy, path=new_path).geturl()

            # 4. Facebook (posts, videos, fb.watch shorts)
            elif netloc in ("facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch"):
                new_url = parsed._replace(netloc="fixfacebook.com").geturl()

            # 5. Reddit (threads, posts, old interface)
            elif netloc in ("reddit.com", "www.reddit.com", "old.reddit.com"):
                new_url = parsed._replace(netloc="rxddit.com").geturl()

            if new_url and new_url != clean_url:
                new_text = new_text.replace(clean_url, new_url)
                replaced = True

        except Exception:
            continue

    # Restaurar bloques de código originales
    for i, block in enumerate(code_blocks):
        new_text = new_text.replace(f"__YOUKAI_CODE_BLOCK_{i}__", block)

    return new_text, replaced


class LinkFixerCog(commands.Cog, name="LinkFixer"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.instagram_proxy = "eeinstagram.com"
        self.check_proxies_task.start()

    def cog_unload(self) -> None:
        self.check_proxies_task.cancel()

    @tasks.loop(minutes=10)
    async def check_proxies_task(self) -> None:
        """Comprueba periódicamente qué proxies de Instagram están activos y sanos."""
        candidates = [
            "eeinstagram.com",
            "ddinstagram.com",
        ]
        
        async with aiohttp.ClientSession() as session:
            for domain in candidates:
                url = f"https://{domain}/"
                try:
                    headers = {"User-Agent": "Discordbot/2.0 (https://discordapp.com)"}
                    async with session.get(url, headers=headers, timeout=3.0, allow_redirects=False) as resp:
                        if resp.status == 200:
                            self.instagram_proxy = domain
                            logger.info("LinkFixer: Proxy de Instagram activo detectado: %s", domain)
                            return
                except Exception as exc:
                    logger.debug("LinkFixer: Error probando proxy %s: %s", domain, exc)
                    
        logger.warning("LinkFixer: Ningún proxy de Instagram respondió correctamente. Usando fallback por defecto: %s", self.instagram_proxy)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Escucha mensajes y corrige enlaces no amigables sin borrar el mensaje original."""
        if message.author.bot or not message.guild:
            return

        # Verificar si hay enlaces a corregir usando el proxy activo
        instagram_proxy = getattr(self, "instagram_proxy", "eeinstagram.com")
        fixed_text, replaced = fix_links(message.content, instagram_proxy=instagram_proxy)
        if not replaced:
            return

        logger.info("LinkFixer: Detectado enlace corregible de %s en G:%s C:%s", message.author.name, message.guild.id, message.channel.id)

        guild = message.guild
        me = guild.me
        permissions = message.channel.permissions_for(me)

        # Ocultar la previsualización del mensaje original si tenemos permisos de gestionar mensajes
        if permissions.manage_messages:
            try:
                await message.edit(suppress=True)
                logger.info("LinkFixer: Previsualización del mensaje original oculta con éxito.")
            except discord.HTTPException as exc:
                logger.error("LinkFixer: No se pudo ocultar la previsualización del mensaje original: %s", exc)

        # Extraer solo los enlaces corregidos (sin repetir texto original o menciones)
        code_blocks = []
        def replace_block(match):
            placeholder = f"__YOUKAI_CODE_BLOCK_{len(code_blocks)}__"
            code_blocks.append(match.group(0))
            return placeholder

        temp_text = re.sub(r'```[\s\S]*?```', replace_block, message.content)
        temp_text = re.sub(r'`[^`\n]+`', replace_block, temp_text)

        urls = URL_REGEX.findall(temp_text)
        fixed_urls = []
        seen = set()
        for url in urls:
            # Conservar puntuación al final de la URL
            clean_url = url
            suffix = ""
            match_end = re.search(r'([.,;:?!)]+)$', url)
            if match_end:
                suffix = match_end.group(1)
                clean_url = url[:-len(suffix)]

            fixed_url, url_replaced = fix_links(clean_url, instagram_proxy=instagram_proxy)
            if url_replaced and fixed_url not in seen:
                seen.add(fixed_url)
                
                # Formatear el enlace de manera interactiva y elegante
                parsed_fixed = urlparse(fixed_url)
                netloc_fixed = parsed_fixed.netloc.lower()
                path_fixed = parsed_fixed.path
                
                if "fxtwitter.com" in netloc_fixed:
                    parts = path_fixed.strip("/").split("/")
                    username = None
                    if len(parts) >= 3 and parts[1] == "status":
                        username = parts[0]
                    
                    if username and username != "i":
                        formatted_link = f"[Tweet](<{clean_url}>) • [@{username}](<https://x.com/{username}>) • [FxTwitter]({fixed_url})"
                    else:
                        formatted_link = f"[Tweet](<{clean_url}>) • [FxTwitter]({fixed_url})"
                elif "tnktok.com" in netloc_fixed:
                    formatted_link = f"[TikTok](<{clean_url}>) • [tnkTok]({fixed_url})"
                elif "instagram.com" in netloc_fixed or instagram_proxy in netloc_fixed:
                    formatted_link = f"[Instagram](<{clean_url}>) • [eeInstagram]({fixed_url})"
                elif "fixfacebook.com" in netloc_fixed:
                    formatted_link = f"[Facebook](<{clean_url}>) • [FixFacebook]({fixed_url})"
                elif "rxddit.com" in netloc_fixed:
                    formatted_link = f"[Reddit](<{clean_url}>) • [rxddit]({fixed_url})"
                else:
                    formatted_link = fixed_url

                fixed_urls.append(formatted_link)

        if not fixed_urls:
            return

        fixed_msg = "\n".join(fixed_urls)
        try:
            reply_msg = await message.reply(fixed_msg, mention_author=False)
            logger.info("LinkFixer: Enlaces corregidos enviados con éxito.")
            
            # Registrar el ID del mensaje como inerte para evitar disparar el NLP en respuestas
            if not hasattr(self.bot, "inert_message_ids"):
                self.bot.inert_message_ids = set()
            self.bot.inert_message_ids.add(reply_msg.id)
            if len(self.bot.inert_message_ids) > 1000:
                self.bot.inert_message_ids.pop()
        except Exception as exc:
            logger.error("LinkFixer: No se pudo enviar el mensaje corregido: %s", exc)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LinkFixerCog(bot))
