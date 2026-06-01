"""
Utilidad de audit log — envía acciones de Fairy a un canal de Discord configurado.
"""

from __future__ import annotations
import discord
from typing import Optional


COLORS = {
    "ban": 0xED4245,
    "kick": 0xE67E22,
    "mute": 0xFEE75C,
    "unmute": 0x57F287,
    "warn": 0xFBB848,
    "purge": 0x9B59B6,
    "lock": 0x3498DB,
    "unlock": 0x57F287,
    "automod": 0xFF6B6B,
    "raid": 0xED4245,
    "role": 0x5865F2,
    "default": 0x95A5A6,
}


async def send_audit(
    guild: discord.Guild,
    db,
    action: str,
    actor: Optional[discord.Member] = None,
    target: Optional[discord.Member] = None,
    reason: str = "",
    extra: Optional[dict] = None,
):
    """
    Envía un embed al canal de audit log configurado para el servidor.
    Si no hay canal configurado, solo registra en la BD.
    """
    # Guardar en BD siempre
    await db.log_action(
        guild_id=guild.id,
        action=action,
        actor_id=actor.id if actor else None,
        target_id=target.id if target else None,
        details={"reason": reason, **(extra or {})},
    )

    # Buscar canal de audit
    config = await db.get_guild_config(guild.id)
    audit_ch_id = config.get("audit_ch")
    if not audit_ch_id:
        return

    channel = guild.get_channel(audit_ch_id)
    if not channel or not isinstance(channel, discord.TextChannel):
        return

    color = COLORS.get(action.split("_")[0], COLORS["default"])

    embed = discord.Embed(
        title=f"📋 {action.replace('_', ' ').title()}",
        color=color,
    )

    if actor:
        embed.set_author(name=f"{actor.display_name}", icon_url=actor.display_avatar.url)

    if target:
        embed.add_field(
            name="Usuario",
            value=f"{target.mention} (`{target.id}`)",
            inline=True,
        )

    if reason:
        embed.add_field(name="Razón", value=reason[:500], inline=False)

    if extra:
        for k, v in extra.items():
            if k not in ("reason",) and v:
                embed.add_field(name=k.replace("_", " ").title(), value=str(v), inline=True)

    embed.set_footer(text="Fairy Audit Log")
    import time
    embed.timestamp = discord.utils.utcnow()

    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        pass
    except Exception:
        pass
