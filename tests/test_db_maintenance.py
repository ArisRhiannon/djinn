"""Tests for cogs/db_maintenance.py — funciones puras de backup/vacuum."""

from __future__ import annotations

import gzip
import importlib.util
from pathlib import Path

import aiosqlite
import pytest

# Cargar el módulo sin pasar por discord.ext (que requiere contexto bot)
_SPEC = importlib.util.spec_from_file_location(
    "cogs.db_maintenance",
    Path(__file__).resolve().parent.parent / "cogs" / "db_maintenance.py",
)
_DBM = importlib.util.module_from_spec(_SPEC)  # type: ignore[arg-type]
_SPEC.loader.exec_module(_DBM)  # type: ignore[union-attr]


@pytest.fixture
async def sample_db(tmp_path):
    """Crea una DB SQLite mínima con una tabla y un par de filas."""
    db_path = tmp_path / "sample.db"
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT);")
        await conn.execute("INSERT INTO t (v) VALUES ('a'), ('b'), ('c');")
        await conn.commit()
    return db_path


# ─── perform_backup ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_backup_creates_file(sample_db, tmp_path):
    dst = tmp_path / "backups"
    res = await _DBM.perform_backup(str(sample_db), dst, gzip_output=False)
    assert res["success"] is True
    assert Path(res["path"]).exists()
    assert res["size_bytes"] > 0


@pytest.mark.asyncio
async def test_backup_gzipped(sample_db, tmp_path):
    dst = tmp_path / "backups"
    res = await _DBM.perform_backup(str(sample_db), dst, gzip_output=True)
    assert res["success"] is True
    p = Path(res["path"])
    assert p.exists()
    assert p.suffix == ".gz"
    # gzip válido
    with gzip.open(p, "rb") as fh:
        head = fh.read(16)
    assert head.startswith(b"SQLite format 3"), "el contenido descomprimido debe ser SQLite"


@pytest.mark.asyncio
async def test_backup_missing_source(tmp_path):
    res = await _DBM.perform_backup(str(tmp_path / "missing.db"), tmp_path, gzip_output=False)
    assert res["success"] is False
    assert "no existe" in res["error"]


@pytest.mark.asyncio
async def test_backup_creates_dst_dir(sample_db, tmp_path):
    dst = tmp_path / "deep" / "nested" / "backups"
    assert not dst.exists()
    res = await _DBM.perform_backup(str(sample_db), dst, gzip_output=False)
    assert res["success"] is True
    assert dst.exists()


# ─── prune_old_backups ──────────────────────────────────────────────────────


def test_prune_removes_old_files(tmp_path):
    import os
    import time
    dst = tmp_path
    fresh = dst / "fairy_2026-05-15.db"
    old = dst / "fairy_old.db"
    fresh.write_bytes(b"x")
    old.write_bytes(b"x")
    # Forzamos mtime antiguo (10 días atrás)
    very_old = time.time() - 10 * 86400
    os.utime(old, (very_old, very_old))

    removed = _DBM.prune_old_backups(dst, retain_days=7)
    assert removed == 1
    assert fresh.exists()
    assert not old.exists()


def test_prune_no_dir(tmp_path):
    assert _DBM.prune_old_backups(tmp_path / "nope", 7) == 0


def test_prune_keeps_all_when_recent(tmp_path):
    (tmp_path / "fairy_a.db").write_bytes(b"x")
    (tmp_path / "fairy_b.db.gz").write_bytes(b"x")
    assert _DBM.prune_old_backups(tmp_path, retain_days=30) == 0


# ─── perform_vacuum ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vacuum_full(sample_db):
    res = await _DBM.perform_vacuum(str(sample_db), full=True)
    assert res["success"] is True
    assert res["mode"] == "full"
    assert "size_before_bytes" in res
    assert "size_after_bytes" in res


@pytest.mark.asyncio
async def test_vacuum_incremental(sample_db):
    res = await _DBM.perform_vacuum(str(sample_db), full=False)
    assert res["success"] is True
    assert res["mode"] == "incremental"


@pytest.mark.asyncio
async def test_vacuum_missing_db(tmp_path):
    res = await _DBM.perform_vacuum(str(tmp_path / "nope.db"))
    assert res["success"] is False
