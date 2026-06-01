"""Shared pytest fixtures for the Fairy/Youkai test suite.

Wave 7 (F5.1, 2026-05-15): foundation de tests. Las fixtures aquí no dependen
de Discord ni del venv para ejecución — funcionan contra in-memory SQLite y
mocks ligeros.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Asegurar que el repo está en el path antes de importar utils.*
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── pytest-asyncio config ──────────────────────────────────────────────────
# Modo 'auto' = los `async def test_*` se ejecutan sin necesidad de marker
# explícito.  Esto se configura también vía pyproject.toml (ver bloque
# `[tool.pytest.ini_options]`).


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def env_clean(monkeypatch):
    """Limpia variables de entorno controladas por nuestros módulos.

    Evita que tests heredan FAIRY_TOOL_PERMS_ENFORCE u otras flags del shell.
    """
    for var in (
        "FAIRY_TOOL_PERMS_ENFORCE",
        "FAIRY_CIRCUIT_BREAKER_DISABLED",
        "FAIRY_DB_VACUUM_DISABLED",
        "FAIRY_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


# ── Mocks de Discord (mínimos, sin importar discord.py) ────────────────────


class _FakePerms:
    """Mimics discord.Permissions: cualquier atributo no definido → False."""

    def __init__(self, **flags):
        self._flags = flags

    def __getattr__(self, name):
        return self._flags.get(name, False)


class _FakeGuild:
    def __init__(self, owner_id: int = 1):
        self.owner_id = owner_id
        self._members: dict[int, _FakeMember] = {}

    def get_member(self, uid: int):
        return self._members.get(uid)

    def add_member(self, member: "_FakeMember"):
        self._members[member.id] = member


class _FakeMember:
    def __init__(self, id: int, guild: _FakeGuild, **perms):
        self.id = id
        self.guild = guild
        self.guild_permissions = _FakePerms(**perms)
        guild.add_member(self)


@pytest.fixture
def fake_guild():
    return _FakeGuild(owner_id=1)


@pytest.fixture
def make_member(fake_guild):
    """Factory: make_member(123, ban_members=True, administrator=False, ...)"""
    def _factory(uid: int, **perms) -> _FakeMember:
        return _FakeMember(uid, fake_guild, **perms)
    return _factory
