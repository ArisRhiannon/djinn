"""Media source resolution for Discord messages.

Handles three sources:
  1. Direct attachments (image/gif content types)
  2. Direct links to image/GIF URLs
  3. Web page links (extracts OpenGraph image or largest <img>)
"""

from __future__ import annotations

import io
import logging
from typing import List, Optional
from urllib.parse import urlparse

import aiohttp
import discord
from bs4 import BeautifulSoup

logger = logging.getLogger("youkai.mediaguard.resolver")

# ── Recognized image/GIF content types ──────────────────────────────────────
IMAGE_CONTENT_TYPES: frozenset[str] = frozenset({
    "image/png", "image/jpeg", "image/jpg", "image/gif",
    "image/webp", "image/bmp", "image/tiff",
})

# ── Discord CDN domains (direct image access) ──────────────────────────────
DISCORD_CDN_DOMAINS: frozenset[str] = frozenset({
    "cdn.discordapp.com",
    "media.discordapp.net",
})

# ── Known image hosting extensions (skip HTML fetch for these) ──────────────
IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff",
})


class MediaSource:
    """A resolved media source ready for download."""

    __slots__ = ("url", "source_type", "content_type_hint")

    def __init__(self, url: str, source_type: str, content_type_hint: str = ""):
        self.url = url
        self.source_type = source_type  # "attachment", "direct_link", "web_page"
        self.content_type_hint = content_type_hint

    def __repr__(self) -> str:
        return f"MediaSource({self.source_type}: {self.url[:60]})"


def extract_media_sources(message: discord.Message) -> List[MediaSource]:
    """Extract all media sources from a Discord message.

    Returns a list of MediaSource objects that can be downloaded.
    Handles duplicates (same URL from embed + link).
    """
    sources: List[MediaSource] = []
    seen_urls: set[str] = set()

    # ── 1. Direct attachments ────────────────────────────────────────────
    for attachment in message.attachments:
        ct = attachment.content_type or ""
        if ct and any(ct.startswith(t) for t in ("image/",)):
            url = attachment.url
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append(MediaSource(url, "attachment", ct))

    # ── 2. Embeds (Discord auto-generated previews) ──────────────────────
    for embed in message.embeds:
        # Image embed
        if embed.image and embed.image.url:
            url = embed.image.url
            if url not in seen_urls:
                seen_urls.add(url)
                sources.append(MediaSource(url, "embed_image"))
        # Thumbnail embed
        if embed.thumbnail and embed.thumbnail.url:
            url = embed.thumbnail.url
            if url not in seen_urls:
                seen_urls.add(url)
                sources.append(MediaSource(url, "embed_thumbnail"))

    # ── 3. Links in message content ─────────────────────────────────────
    if message.content:
        # Simple URL extraction via regex
        import re
        urls = re.findall(r"https?://[^\s<>\"']+", message.content)
        for url in urls:
            # Strip trailing punctuation
            url = url.rstrip(".,;:!?)]}")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()

            # Discord CDN — direct image
            if domain in DISCORD_CDN_DOMAINS:
                sources.append(MediaSource(url, "direct_link"))
                continue

            # Known image extension — direct link
            if any(path.endswith(ext) for ext in IMAGE_EXTENSIONS):
                sources.append(MediaSource(url, "direct_link"))
                continue

            # Unknown — will need HTML fetch (web page)
            # Rewrite social media links to their friendly proxies to bypass scraping walls
            rewritten_url = url
            if domain in ("twitter.com", "www.twitter.com", "mobile.twitter.com", "x.com", "www.x.com"):
                rewritten_url = parsed._replace(netloc="fxtwitter.com").geturl()
            elif domain in ("instagram.com", "www.instagram.com"):
                rewritten_url = parsed._replace(netloc="eeinstagram.com").geturl()
            elif domain in ("tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"):
                if domain == "vm.tiktok.com":
                    rewritten_url = parsed._replace(netloc="vm.tnktok.com").geturl()
                elif domain == "vt.tiktok.com":
                    rewritten_url = parsed._replace(netloc="vt.tnktok.com").geturl()
                else:
                    rewritten_url = parsed._replace(netloc="tnktok.com").geturl()
            
            sources.append(MediaSource(rewritten_url, "web_page"))

    return sources


async def download_media(
    source: MediaSource,
    session: aiohttp.ClientSession | None = None,
    timeout: float = 10.0,
) -> Optional[bytes]:
    """Download media bytes from a MediaSource.

    For web_page sources, fetches the HTML and extracts the OpenGraph image
    first, then downloads that image.

    Args:
        source: The media source to download.
        session: Optional aiohttp session (one is created if None).
        timeout: Download timeout in seconds.

    Returns:
        Raw bytes or None if download failed.
    """
    own_session = session is None

    try:
        if own_session:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            session = aiohttp.ClientSession(timeout=timeout_obj)

        if source.source_type == "web_page":
            # Extract OpenGraph image from HTML
            image_url = await _extract_og_image(source.url, session, timeout)
            if not image_url:
                logger.debug("No OpenGraph image found for %s", source.url[:80])
                return None
            url_to_fetch = image_url
        else:
            url_to_fetch = source.url

        return await _fetch_bytes(url_to_fetch, session, timeout)

    except asyncio.TimeoutError:
        logger.debug("Download timeout: %s", source.url[:80])
        return None
    except aiohttp.ClientError as e:
        logger.debug("Download failed for %s: %s", source.url[:80], e)
        return None
    except Exception as e:
        logger.warning("Unexpected download error for %s: %s", source.url[:80], e)
        return None
    finally:
        if own_session and session:
            await session.close()


async def _fetch_bytes(
    url: str,
    session: aiohttp.ClientSession,
    timeout: float,
) -> Optional[bytes]:
    """Fetch raw bytes from a URL with robust browser headers."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                logger.debug("HTTP %d for %s", resp.status, url[:80])
                return None
            # Limit to 50MB to avoid memory bombs
            data = await resp.read()
            if len(data) > 50 * 1024 * 1024:
                logger.debug("Media too large (%d MB): %s", len(data) // 1024 // 1024, url[:80])
                return None
            return data
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None


async def _extract_og_image(
    url: str,
    session: aiohttp.ClientSession,
    timeout: float,
) -> Optional[str]:
    """Extract OpenGraph image or largest <img> from an HTML page with robust browser headers."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None
            # Limit HTML size
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return None  # Not an HTML page
            html = await resp.text()
            if len(html) > 5 * 1024 * 1024:  # 5MB
                html = html[:5 * 1024 * 1024]
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Try og:image meta tag
        meta = soup.find("meta", property="og:image")
        if meta and meta.get("content"):
            return _make_absolute_url(url, meta["content"])

        # Fallback: find largest <img> tag
        imgs = soup.find_all("img", src=True)
        if imgs:
            return _make_absolute_url(url, imgs[0]["src"])

    except Exception as e:
        logger.debug("HTML parse error for %s: %s", url[:80], e)

    return None


def _make_absolute_url(base_url: str, img_url: str) -> str:
    """Resolve a relative image URL against the page URL."""
    if img_url.startswith(("http://", "https://", "//")):
        if img_url.startswith("//"):
            return "https:" + img_url
        return img_url
    # Relative URL
    from urllib.parse import urljoin
    return urljoin(base_url, img_url)


# asyncio import for TimeoutError
import asyncio
