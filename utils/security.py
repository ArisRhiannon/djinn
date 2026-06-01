"""
Seguridad de Fairy — control de acceso basado en roles.

Niveles de permiso:
  OWNER   → dueño del servidor (puede todo)
  ADMIN   → Administrator en Discord
  MOD     → tiene permisos de moderación
  READER  → puede usar lenguaje natural con Fairy
  USER    → comandos públicos básicos
  NONE    → sin acceso a Fairy
"""

from __future__ import annotations
from enum import IntEnum
from typing import Optional

import discord
from loguru import logger


class PermLevel(IntEnum):
    NONE   = 0
    USER   = 1
    READER = 2
    MOD    = 3
    ADMIN  = 4
    OWNER  = 5


async def get_perm_level(member: discord.Member, db) -> PermLevel:
    """Determina el nivel de permiso de un miembro."""
    if member.id == member.guild.owner_id:
        return PermLevel.OWNER

    if member.guild_permissions.administrator:
        return PermLevel.ADMIN

    if _has_mod_permissions(member):
        return PermLevel.MOD

    reader_roles = await db.get_youkai_readers(member.guild.id)
    if any(role.id in reader_roles for role in member.roles):
        return PermLevel.READER

    return PermLevel.USER


def _has_mod_permissions(member: discord.Member) -> bool:
    p = member.guild_permissions
    return any([
        p.kick_members,
        p.ban_members,
        p.moderate_members,
        p.manage_messages,
        p.manage_roles,
    ])


def require_level(level: PermLevel):
    """
    Decorador para app_commands que verifica el nivel de permiso.
    Uso: @require_level(PermLevel.MOD)
    """
    from discord import app_commands
    from discord.app_commands import CheckFailure

    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not isinstance(member, discord.Member):
            raise CheckFailure("Este comando solo funciona en servidores.")

        user_level = await get_perm_level(member, interaction.client.db)

        if user_level < level:
            level_names = {
                PermLevel.MOD:    "moderador",
                PermLevel.ADMIN:  "administrador",
                PermLevel.OWNER:  "dueño del servidor",
                PermLevel.READER: "lector de Fairy",
            }
            needed = level_names.get(level, str(level))
            raise CheckFailure(f"Necesitas ser {needed} para usar este comando.")
        return True

    return app_commands.check(predicate)


async def can_use_youkai_nl(member: discord.Member, db) -> bool:
    """Solo el owner del server o miembros con rol en la reader list pueden usar LLM.
    
    Los moderadores NO tienen acceso automatico al LLM — deben ser agregados
    a la reader list por un admin si se desea que hablen con Fairy.
    """
    # Owner del server siempre puede
    if member.id == member.guild.owner_id:
        return True

    # Verificar reader list explicitamente
    reader_roles = await db.get_youkai_readers(member.guild.id)
    if reader_roles and any(role.id in reader_roles for role in member.roles):
        return True

    return False


async def can_mod(member: discord.Member, db) -> bool:
    """¿Puede este miembro ejecutar comandos de moderación?"""
    return await get_perm_level(member, db) >= PermLevel.MOD


def target_is_protected(
    actor: discord.Member,
    target: discord.Member,
) -> bool:
    """
    ¿Está el target protegido de ser moderado por este actor?

    Un actor no puede moderar a:
      - El dueño del servidor.
      - Alguien cuyo rol más alto sea igual o superior al suyo
        (a menos que el actor sea Administrator).
    """
    # El dueño siempre está protegido
    if target.id == target.guild.owner_id:
        return True

    # Los administradores no pueden moderarse entre sí salvo el dueño
    if actor.guild_permissions.administrator:
        return False

    # Protección de jerarquía de roles
    return actor.top_role <= target.top_role


# ═══════════════════════════════════════════════════════════════════════════
# SSRF protection — F0.2 (Wave 2, 2026-05-15, SEC-02)
# ═══════════════════════════════════════════════════════════════════════════
import ipaddress
import socket
from urllib.parse import urlparse


class URLSafetyError(ValueError):
    """URL bloqueada por validación SSRF."""


_BLOCKED_HOSTNAMES: frozenset[str] = frozenset({
    "localhost", "ip6-localhost", "ip6-loopback",
    "metadata.google.internal",  # GCP metadata
    "metadata.aws",  # alias informal
})

_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})


def _ip_is_blocked(ip_str: str) -> tuple[bool, str]:
    """Devuelve (blocked, motivo) para una IP en formato string."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True, f"IP malformada: {ip_str!r}"

    if ip.is_loopback:
        return True, "loopback (127.0.0.0/8 o ::1)"
    if ip.is_private:
        return True, "RFC1918 / private (10/8, 172.16-31, 192.168/16, fc00::/7)"
    if ip.is_link_local:
        # 169.254.0.0/16 — incluye AWS/Azure metadata 169.254.169.254
        return True, "link-local (incluye cloud metadata)"
    if ip.is_multicast:
        return True, "multicast"
    if ip.is_reserved:
        return True, "reserved"
    if ip.is_unspecified:
        return True, "unspecified (0.0.0.0)"
    return False, ""


def is_url_safe(url: str, *, allow_localhost: bool = False) -> tuple[bool, str]:
    """
    Valida que ``url`` no apunte a IPs internas, loopback, link-local, ni
    cloud metadata. No hace la petición — solo resuelve DNS y filtra.

    Returns:
        (True, "")               si la URL es segura.
        (False, "<motivo>")      si la URL está bloqueada.

    Notes:
        - Solo permite schemes http/https.
        - Resuelve el hostname con ``socket.getaddrinfo`` y rechaza si CUALQUIER
          IP resuelta cae en un rango bloqueado (defensa contra DNS rebinding).
        - ``allow_localhost`` solo debe usarse para tests, nunca para tools
          expuestas al LLM.
    """
    if not url or not isinstance(url, str):
        return False, "URL vacía o no-string"

    try:
        parsed = urlparse(url.strip())
    except Exception as exc:
        return False, f"URL malformada: {exc}"

    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        return False, f"scheme no permitido: {scheme!r} (solo http/https)"

    host = (parsed.hostname or "").lower()
    if not host:
        return False, "URL sin hostname"

    if host in _BLOCKED_HOSTNAMES and not allow_localhost:
        return False, f"hostname bloqueado: {host!r}"

    # Si el host ya es una IP literal, validamos directamente.
    try:
        ipaddress.ip_address(host)
        blocked, reason = _ip_is_blocked(host)
        if blocked and not allow_localhost:
            return False, f"IP bloqueada ({reason}): {host}"
        return True, ""
    except ValueError:
        pass  # No es IP literal, hace falta resolver DNS.

    # Resolver DNS — chequear todas las IPs (A y AAAA).
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return False, f"DNS no resuelve {host!r}: {exc}"
    except OSError as exc:
        return False, f"resolución de host falló: {exc}"

    seen_ips: set[str] = set()
    for fam, _socktype, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        if ip_str in seen_ips:
            continue
        seen_ips.add(ip_str)
        blocked, reason = _ip_is_blocked(ip_str)
        if blocked and not allow_localhost:
            return False, f"{host} resuelve a IP bloqueada ({reason}): {ip_str}"

    return True, ""


# ═══════════════════════════════════════════════════════════════════════════
# Permission layer para tools del LLM — F0.4 (Wave 2, 2026-05-15, SEC-04)
# ═══════════════════════════════════════════════════════════════════════════
#
# Mapa: tool_name → permiso de Discord requerido en el usuario que originó
# el mensaje. Si el usuario no tiene el permiso, la tool no debe ejecutarse,
# independientemente de que el LLM la haya elegido (defensa contra prompt
# injection via mensaje del usuario).
#
# `None` o ausencia = sin restricción (USER level).
# Solo cubrimos las tools destructivas / con impacto en el servidor; el resto
# permanece sin restricción para no romper UX.
#

# Atributos de discord.Permissions.  Ver:
# https://discordpy.readthedocs.io/en/stable/api.html#discord.Permissions
TOOL_REQUIRED_PERMS: dict[str, str] = {
    # Moderación destructiva
    "ban_user":               "ban_members",
    "unban_user":             "ban_members",
    "kick_user":              "kick_members",
    "mass_timeout":           "moderate_members",
    "timeout_user":           "moderate_members",
    "mute_user":              "moderate_members",
    "unmute_user":            "moderate_members",
    "warn_user":              "moderate_members",
    "seal_user":              "moderate_members",
    "purge_messages":         "manage_messages",
    "delete_message":         "manage_messages",

    # Roles
    "add_role":               "manage_roles",
    "remove_role":            "manage_roles",
    "create_role":            "manage_roles",
    "delete_role":            "manage_roles",
    "bulk_assign_role_all":   "manage_roles",
    "bulk_remove_role_all":   "manage_roles",

    # Canales
    "create_channel":         "manage_channels",
    "edit_channel":           "manage_channels",
    "set_topic":              "manage_channels",
    "set_slowmode":           "manage_channels",
    "move_member":            "move_members",

    # Servidor / configuración
    "edit_guild_settings":    "manage_guild",
    "set_guild_config":       "manage_guild",
    "backup_server":          "manage_guild",
    "create_invite":          "create_instant_invite",

    # Auditoría / información sensible
    "get_audit_log":          "view_audit_log",

    # Banco / Tesorería (Y O U K A I · B A N K)
    "treasury_grant_credits": "manage_guild",
    "treasury_deposit":       "manage_guild",
}


def tool_required_perm(tool_name: str) -> str | None:
    """Devuelve el permiso de Discord requerido para una tool, o ``None`` si
    no hay restricción especial (cualquier usuario puede invocarla)."""
    return TOOL_REQUIRED_PERMS.get(tool_name)


def member_has_tool_permission(member, tool_name: str) -> tuple[bool, str | None]:
    """
    ¿Tiene este ``member`` el permiso de Discord necesario para esta tool?

    Returns:
        (True,  None)      si la tool no requiere permiso especial o el
                           member tiene el permiso.
        (False, "<perm>")  si la tool requiere un permiso que el member no
                           tiene; el segundo elemento es el nombre del permiso.

    Notes:
        - El owner del servidor pasa siempre.
        - Los administradores también pasan automáticamente (Discord les da
          todos los permisos).
        - Si ``member`` es ``None`` (LLM disparado por sistema, no por usuario),
          permitimos por compatibilidad — el caller debe asegurarse de no
          delegar tools sensibles desde contextos sin actor humano.
    """
    if member is None:
        return True, None

    required = tool_required_perm(tool_name)
    if required is None:
        return True, None

    # Owner / admin automático
    try:
        if hasattr(member, "guild") and getattr(member, "id", None) == getattr(
            getattr(member, "guild", None), "owner_id", -1
        ):
            return True, None
        perms = getattr(member, "guild_permissions", None)
        if perms is None:
            return True, None  # DM context o similar; no aplica
        if perms.administrator:
            return True, None
        if getattr(perms, required, False):
            return True, None
    except Exception as exc:  # pragma: no cover — defensivo
        logger.warning("Error chequeando permiso {} para tool {}: {}", required, tool_name, exc)
        return True, None

    return False, required
