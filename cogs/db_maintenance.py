"""
Cog: DB Maintenance — backup automático y VACUUM.

Wave 3 (2026-05-15):
  • F1.2 — Backup diario automático con retención (default 7 días).
  • F2.2 — VACUUM semanal (incremental por defecto, full opcional).
  • Comandos admin: /fairy db_backup_now, /fairy db_stats, /fairy db_vacuum.

Variables de entorno:
  FAIRY_DB_BACKUP_DIR        — destino (default: <db_dir>/backups)
  FAIRY_DB_BACKUP_RETAIN     — días a retener (default: 7)
  FAIRY_DB_BACKUP_HOUR_UTC   — hora del backup diario (default: 4 = 04:00 UTC)
  FAIRY_DB_VACUUM_DAY        — día de la semana para VACUUM (0=lun..6=dom; default: 6)
  FAIRY_DB_VACUUM_HOUR_UTC   — hora del VACUUM (default: 5 = 05:00 UTC)
  FAIRY_DB_VACUUM_DISABLED   — '1' para deshabilitar VACUUM completamente.
"""

from __future__ import annotations

import asyncio
import gzip
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks
from loguru import logger

from utils.security import PermLevel, require_level


def _backup_dir(db_path: str) -> Path:
    env = os.environ.get("FAIRY_DB_BACKUP_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return Path(db_path).resolve().parent / "backups"


def _retention_days() -> int:
    try:
        return max(1, int(os.environ.get("FAIRY_DB_BACKUP_RETAIN", "7")))
    except ValueError:
        return 7


def _backup_hour() -> int:
    try:
        return max(0, min(23, int(os.environ.get("FAIRY_DB_BACKUP_HOUR_UTC", "4"))))
    except ValueError:
        return 4


def _vacuum_day() -> int:
    try:
        return max(0, min(6, int(os.environ.get("FAIRY_DB_VACUUM_DAY", "6"))))
    except ValueError:
        return 6


def _vacuum_hour() -> int:
    try:
        return max(0, min(23, int(os.environ.get("FAIRY_DB_VACUUM_HOUR_UTC", "5"))))
    except ValueError:
        return 5


async def perform_backup(db_path: str, dst_dir: Path, *, gzip_output: bool = True) -> dict:
    """
    Crea un backup atómico de la DB SQLite usando el método nativo backup() de
    aiosqlite (NO usar shutil.copy con WAL: corrompe).

    Returns:
        dict con: success, path, size_bytes, duration_ms, gzipped.
    """
    src = Path(db_path).resolve()
    if not src.exists():
        return {"success": False, "error": f"DB no existe: {src}"}

    dst_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    raw_dst = dst_dir / f"fairy_{ts}.db"
    final_dst = raw_dst.with_suffix(".db.gz") if gzip_output else raw_dst

    started = datetime.now(timezone.utc)
    try:
        # Backup atómico via API nativa de SQLite.
        async with aiosqlite.connect(str(src)) as src_conn:
            async with aiosqlite.connect(str(raw_dst)) as dst_conn:
                await src_conn.backup(dst_conn)

        if gzip_output:
            # Comprimir en hilo aparte para no bloquear el event loop.
            def _gzip_to(src_path: Path, dst_path: Path) -> None:
                with open(src_path, "rb") as f_in, gzip.open(dst_path, "wb", compresslevel=6) as f_out:
                    shutil.copyfileobj(f_in, f_out, length=1024 * 1024)
            await asyncio.to_thread(_gzip_to, raw_dst, final_dst)
            try:
                raw_dst.unlink()
            except OSError:
                pass

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return {
            "success": True,
            "path": str(final_dst),
            "size_bytes": final_dst.stat().st_size,
            "duration_ms": elapsed_ms,
            "gzipped": gzip_output,
        }
    except (aiosqlite.Error, OSError) as exc:
        logger.exception("DB backup falló: {}", exc)
        # Limpieza si quedó archivo parcial
        for p in (raw_dst, final_dst):
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}


def prune_old_backups(dst_dir: Path, retain_days: int) -> int:
    """Elimina backups con mtime más antiguo que `retain_days` días. Devuelve nº borrados."""
    if not dst_dir.exists():
        return 0
    cutoff = datetime.now(timezone.utc).timestamp() - retain_days * 86400
    removed = 0
    for p in dst_dir.glob("fairy_*.db*"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except OSError:
            continue
    return removed


async def perform_vacuum(db_path: str, *, full: bool = False) -> dict:
    """
    Ejecuta VACUUM. Si `full=False` usa `PRAGMA incremental_vacuum`
    (no requiere espacio doble). Si `full=True` ejecuta VACUUM full
    (recomendado tras backup, libera más espacio pero es más caro).
    """
    src = Path(db_path).resolve()
    if not src.exists():
        return {"success": False, "error": f"DB no existe: {src}"}

    started = datetime.now(timezone.utc)
    size_before = src.stat().st_size
    try:
        async with aiosqlite.connect(str(src)) as conn:
            if full:
                await conn.execute("VACUUM;")
            else:
                # incremental_vacuum solo funciona si auto_vacuum está activado.
                # En DB existente sin auto_vacuum, el efecto es nulo (no falla).
                await conn.execute("PRAGMA incremental_vacuum;")
            await conn.commit()
        size_after = src.stat().st_size
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return {
            "success": True,
            "mode": "full" if full else "incremental",
            "size_before_bytes": size_before,
            "size_after_bytes": size_after,
            "freed_bytes": max(0, size_before - size_after),
            "duration_ms": elapsed_ms,
        }
    except aiosqlite.Error as exc:
        logger.exception("DB VACUUM falló: {}", exc)
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}


# ═══════════════════════════════════════════════════════════════════════════
# COG
# ═══════════════════════════════════════════════════════════════════════════


class DBMaintenanceCog(commands.Cog, name="DBMaintenance"):
    """Backup automático y VACUUM de la DB SQLite."""

    def __init__(self, bot):
        self.bot = bot
        self._daily_backup_loop.start()
        if os.environ.get("FAIRY_DB_VACUUM_DISABLED", "0") != "1":
            self._weekly_vacuum_loop.start()
        self._monthly_archive_loop.start()

    def cog_unload(self):
        self._daily_backup_loop.cancel()
        self._monthly_archive_loop.cancel()
        try:
            self._weekly_vacuum_loop.cancel()
        except RuntimeError:
            pass

    # ── Daily backup ──────────────────────────────────────────────────────

    @tasks.loop(hours=24)
    async def _daily_backup_loop(self):
        try:
            db_path = getattr(self.bot.config, "db_path", None)
            if not db_path:
                logger.warning("db_maintenance: bot.config.db_path no disponible — skip backup")
                return

            dst_dir = _backup_dir(db_path)
            result = await perform_backup(db_path, dst_dir, gzip_output=True)
            if result.get("success"):
                size_mb = result["size_bytes"] / (1024 * 1024)
                logger.info(
                    "DB backup OK: {} ({:.1f} MB en {} ms)",
                    result["path"], size_mb, result["duration_ms"],
                )
                pruned = prune_old_backups(dst_dir, _retention_days())
                if pruned:
                    logger.info("DB backups antiguos purgados: {}", pruned)
            else:
                logger.error("DB backup FALLÓ: {}", result.get("error"))
        except Exception as exc:  # defensa: nunca matar el loop
            logger.exception("db_maintenance daily backup unexpected error: {}", exc)

    @_daily_backup_loop.before_loop
    async def _wait_for_backup_hour(self):
        await self.bot.wait_until_ready()
        # Esperar al primer arranque hasta la hora deseada en UTC, máx 24h.
        target_h = _backup_hour()
        now = datetime.now(timezone.utc)
        target = now.replace(hour=target_h, minute=0, second=0, microsecond=0)
        if target <= now:
            target = target.replace(day=now.day + 1) if now.day < 28 else target
            # Aproximación: si ya pasamos la hora, dormimos hasta la próxima.
            wait = (target - now).total_seconds()
            if wait <= 0 or wait > 86400:
                wait = 86400 - (now.hour * 3600 + now.minute * 60 + now.second) + target_h * 3600
        else:
            wait = (target - now).total_seconds()
        wait = max(60, min(86400, int(wait)))  # entre 1 min y 24h
        logger.debug("db_maintenance: primer backup en {}s ({}h objetivo UTC)", wait, target_h)
        await asyncio.sleep(wait)

    # ── Weekly VACUUM ─────────────────────────────────────────────────────

    @tasks.loop(hours=24)
    async def _weekly_vacuum_loop(self):
        # Solo ejecutar si hoy es el día configurado.
        now = datetime.now(timezone.utc)
        if now.weekday() != _vacuum_day():
            return
        try:
            db_path = getattr(self.bot.config, "db_path", None)
            if not db_path:
                return
            # SAFETY: backup primero
            dst_dir = _backup_dir(db_path)
            backup_result = await perform_backup(db_path, dst_dir, gzip_output=True)
            if not backup_result.get("success"):
                logger.error("VACUUM saltado: backup previo falló — {}", backup_result.get("error"))
                return
            # Vacuum incremental (no requiere espacio doble)
            vac = await perform_vacuum(db_path, full=False)
            if vac.get("success"):
                freed_mb = vac["freed_bytes"] / (1024 * 1024)
                logger.info(
                    "DB VACUUM ({}) OK: liberado {:.1f} MB en {} ms",
                    vac["mode"], freed_mb, vac["duration_ms"],
                )
            else:
                logger.error("DB VACUUM FALLÓ: {}", vac.get("error"))
        except Exception as exc:
            logger.exception("db_maintenance weekly vacuum unexpected error: {}", exc)

    @_weekly_vacuum_loop.before_loop
    async def _wait_for_vacuum_hour(self):
        await self.bot.wait_until_ready()
        target_h = _vacuum_hour()
        now = datetime.now(timezone.utc)
        seconds_today = now.hour * 3600 + now.minute * 60 + now.second
        target_seconds = target_h * 3600
        if target_seconds > seconds_today:
            wait = target_seconds - seconds_today
        else:
            wait = 86400 - seconds_today + target_seconds
        wait = max(60, min(86400, wait))
        logger.debug("db_maintenance: primer chequeo de VACUUM en {}s", wait)
        await asyncio.sleep(wait)

    # ── Admin commands ────────────────────────────────────────────────────

    fairy_group = app_commands.Group(
        name="fairy_db",
        description="Mantenimiento de la base de datos de Fairy",
        guild_only=True,
    )

    @fairy_group.command(name="backup_now", description="Crea un backup inmediato de la DB")
    @require_level(PermLevel.ADMIN)
    async def cmd_backup_now(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        db_path = getattr(self.bot.config, "db_path", None)
        if not db_path:
            await interaction.followup.send("❌ db_path no configurado.", ephemeral=True)
            return
        dst_dir = _backup_dir(db_path)
        r = await perform_backup(db_path, dst_dir, gzip_output=True)
        if r.get("success"):
            size_mb = r["size_bytes"] / (1024 * 1024)
            await interaction.followup.send(
                f"✅ Backup OK\n`{r['path']}`\n`{size_mb:.1f} MB · {r['duration_ms']} ms`",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(f"❌ {r.get('error')}", ephemeral=True)

    @fairy_group.command(name="stats", description="Tamaño y estado de la DB")
    @require_level(PermLevel.ADMIN)
    async def cmd_stats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        db_path = getattr(self.bot.config, "db_path", None)
        if not db_path or not Path(db_path).exists():
            await interaction.followup.send("❌ DB no encontrada.", ephemeral=True)
            return
        size = Path(db_path).stat().st_size / (1024 * 1024)
        wal = Path(db_path + "-wal")
        shm = Path(db_path + "-shm")
        wal_mb = wal.stat().st_size / (1024 * 1024) if wal.exists() else 0
        shm_mb = shm.stat().st_size / (1024 * 1024) if shm.exists() else 0

        try:
            async with aiosqlite.connect(db_path) as conn:
                async with conn.execute("PRAGMA page_count;") as c:
                    pages = (await c.fetchone())[0]
                async with conn.execute("PRAGMA page_size;") as c:
                    page_size = (await c.fetchone())[0]
                async with conn.execute("PRAGMA freelist_count;") as c:
                    freelist = (await c.fetchone())[0]
                async with conn.execute("PRAGMA auto_vacuum;") as c:
                    auto_vac = (await c.fetchone())[0]
        except aiosqlite.Error as exc:
            await interaction.followup.send(f"❌ DB query error: {exc}", ephemeral=True)
            return

        backups_dir = _backup_dir(db_path)
        backup_files = list(backups_dir.glob("fairy_*.db*")) if backups_dir.exists() else []
        backups_total_mb = sum(p.stat().st_size for p in backup_files) / (1024 * 1024)

        embed = discord.Embed(title="📊 DB Stats", color=0x5865F2)
        embed.add_field(name="DB", value=f"{size:.1f} MB", inline=True)
        embed.add_field(name="WAL", value=f"{wal_mb:.1f} MB", inline=True)
        embed.add_field(name="SHM", value=f"{shm_mb:.1f} MB", inline=True)
        embed.add_field(name="Pages", value=f"{pages:,} × {page_size}B", inline=True)
        embed.add_field(name="Freelist", value=f"{freelist:,}", inline=True)
        avname = {0: "off", 1: "full", 2: "incremental"}.get(auto_vac, str(auto_vac))
        embed.add_field(name="auto_vacuum", value=avname, inline=True)
        embed.add_field(
            name="Backups",
            value=f"{len(backup_files)} archivos · {backups_total_mb:.1f} MB · `{backups_dir}`",
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @fairy_group.command(name="vacuum", description="Ejecuta VACUUM (incremental por defecto)")
    @app_commands.describe(full="Si True, hace VACUUM completo (más caro)")
    @require_level(PermLevel.ADMIN)
    async def cmd_vacuum(self, interaction: discord.Interaction, full: bool = False):
        await interaction.response.defer(ephemeral=True)
        db_path = getattr(self.bot.config, "db_path", None)
        if not db_path:
            await interaction.followup.send("❌ db_path no configurado.", ephemeral=True)
            return
        # SAFETY: backup primero si es full
        if full:
            dst_dir = _backup_dir(db_path)
            br = await perform_backup(db_path, dst_dir, gzip_output=True)
            if not br.get("success"):
                await interaction.followup.send(
                    f"❌ Backup previo falló — VACUUM cancelado: {br.get('error')}",
                    ephemeral=True,
                )
                return
        r = await perform_vacuum(db_path, full=full)
        if r.get("success"):
            freed_mb = r["freed_bytes"] / (1024 * 1024)
            await interaction.followup.send(
                f"✅ VACUUM ({r['mode']}) OK · liberado {freed_mb:.1f} MB · {r['duration_ms']} ms",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(f"❌ {r.get('error')}", ephemeral=True)

    # ── Embedding tiered archival (monthly) ────────────────────────────────

    @tasks.loop(hours=24)
    async def _monthly_archive_loop(self):
        """On the 1st of each month, archive >3mo embeddings and purge >12mo."""
        now = datetime.now(timezone.utc)
        if now.day != 1:
            return
        db = getattr(self.bot, "db", None)
        if not db:
            return
        try:
            archived = await db.archive_old_embeddings(age_days=90, batch_size=500)
            if archived:
                logger.info("Embedding archival: {} embeddings moved to warm tier (int8[128])", archived)
            await db.purge_ancient_embeddings(age_days=365)
            logger.info("Embedding purge: removed >12mo embeddings from archive")
        except Exception as exc:
            logger.error("Embedding archival error: {}", exc)

    @_monthly_archive_loop.before_loop
    async def _wait_for_archive(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(DBMaintenanceCog(bot))
