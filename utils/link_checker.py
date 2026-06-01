"""
Verificador de links — detecta dominios maliciosos, phishing y links de invitación.

Heurísticas usadas (sin APIs externas):
  1. Lista negra de dominios conocidos (bad_domains.txt)
  2. Patrones de phishing (imitaciones de Discord, Steam, etc.)
  3. Dominios de typosquatting
  4. Links de invitación de bots de spam (discord.gg masivo)
  5. URLs sospechosas por estructura (acortadores + redirect)
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse

from loguru import logger


class LinkRisk(Enum):
    SAFE = auto()
    SUSPICIOUS = auto()
    MALICIOUS = auto()
    INVITE = auto()           # Discord invite (puede ser legítima o spam)


@dataclass
class LinkResult:
    url: str
    risk: LinkRisk
    reason: str = ""


# Patrones de phishing comunes
PHISHING_PATTERNS = [
    r"disc[o0]rd\.g[i1]ft",
    r"disc[o0]rdapp\.c[o0]m",
    r"disc[o0]rd-n[i1]tr[o0]",
    r"d[i1]sc[o0]rd\.c[o0]m\.[a-z]{2,}",
    r"st[e3]amcomm?un[i1]ty",
    r"free-n[i1]tr[o0]",
    r"n[i1]tr[o0]-d[i1]sc[o0]rd",
    r"cl[a@]im.*n[i1]tr[o0]",
    r"steam.*tr[a@]de.*[o0]ffer",
    r"win.*giveaway.*click",
]

# Extensiones de archivos ejecutables en URLs
DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".jar",
    ".dmg", ".pkg", ".sh", ".msi", ".apk", ".deb",
}

# URL shorteners conocidos (no son malos per se, pero requieren más análisis)
URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "ow.ly", "buff.ly",
    "goo.gl", "rb.gy", "cutt.ly", "short.io", "tiny.cc",
}


class LinkChecker:
    def __init__(self, bad_domains_path: str = "data/bad_domains.txt"):
        self._bad_domains: Set[str] = set()
        self._phishing_re = [re.compile(p, re.IGNORECASE) for p in PHISHING_PATTERNS]
        self._load_bad_domains(bad_domains_path)

    def _load_bad_domains(self, path: str):
        p = Path(path)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip().lower()
                    if line and not line.startswith("#"):
                        self._bad_domains.add(line)
            logger.debug(f"LinkChecker: {len(self._bad_domains)} dominios bloqueados cargados")

    def extract_urls(self, text: str) -> List[str]:
        """Extrae todas las URLs de un texto."""
        pattern = r"https?://[^\s<>\"'(){}|\\^`\[\]]+"
        return re.findall(pattern, text)

    def check(self, url: str) -> LinkResult:
        """Analiza una URL y retorna el nivel de riesgo."""
        url_lower = url.lower()

        try:
            parsed = urlparse(url_lower)
            domain = parsed.netloc.lstrip("www.")
            path = parsed.path
        except Exception:
            return LinkResult(url, LinkRisk.SUSPICIOUS, "URL malformada")

        # ── Lista negra ────────────────────────────────────────────────────
        if domain in self._bad_domains:
            return LinkResult(url, LinkRisk.MALICIOUS, f"Dominio bloqueado: {domain}")

        # Comprobar subdominios también
        domain_parts = domain.split(".")
        for i in range(len(domain_parts) - 1):
            parent = ".".join(domain_parts[i:])
            if parent in self._bad_domains:
                return LinkResult(url, LinkRisk.MALICIOUS, f"Dominio bloqueado: {parent}")

        # ── Patrones de phishing ───────────────────────────────────────────
        for pattern in self._phishing_re:
            if pattern.search(url_lower):
                return LinkResult(
                    url, LinkRisk.MALICIOUS,
                    f"Patrón de phishing detectado"
                )

        # ── Invitaciones de Discord ────────────────────────────────────────
        if re.search(r"discord\.(gg|io|me|li)/[a-zA-Z0-9]+", url_lower):
            return LinkResult(url, LinkRisk.INVITE, "Invitación de Discord")

        # ── Extensiones peligrosas ─────────────────────────────────────────
        ext = Path(parsed.path).suffix.lower()
        if ext in DANGEROUS_EXTENSIONS:
            return LinkResult(
                url, LinkRisk.SUSPICIOUS,
                f"Archivo ejecutable ({ext})"
            )

        # ── Acortadores (requieren más contexto del usuario) ───────────────
        if domain in URL_SHORTENERS:
            return LinkResult(url, LinkRisk.SUSPICIOUS, "URL acortada")

        # ── IP directa (raramente legítimo en chat) ────────────────────────
        if re.match(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", domain):
            return LinkResult(url, LinkRisk.SUSPICIOUS, "IP directa en URL")

        return LinkResult(url, LinkRisk.SAFE)

    def check_text(self, text: str) -> List[LinkResult]:
        """Extrae y verifica todos los links de un texto."""
        urls = self.extract_urls(text)
        return [self.check(url) for url in urls]

    def has_malicious_link(self, text: str) -> bool:
        """Quick check: ¿hay algún link malicioso en el texto?"""
        for result in self.check_text(text):
            if result.risk == LinkRisk.MALICIOUS:
                return True
        return False

    def reload_bad_domains(self, path: str):
        """Recarga la lista negra en caliente."""
        self._bad_domains.clear()
        self._load_bad_domains(path)
