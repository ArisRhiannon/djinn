"""Suite completa del dispatcher de ToolExecutor (utils/discord_tools.py).

Objetivo: red de regresión que blinde el split del god object (M1). El split
reorganiza DÓNDE viven los handlers `_do_*`, pero el CONTRATO del dispatcher
(`_dispatch`/`execute`/`execute_by_name`) debe permanecer idéntico:

  1. FORBIDDEN          → error "permanently disabled"
  2. A1 permission layer→ enforce bloquea / log-only deja pasar
  3. handler inexistente→ "Unknown function"
  4. DB-required sin db → "Database unavailable"
  5. _check_bot_permissions → "Bot lacks..." / "Bot not found in guild."
  6. timeout            → "timed out"
  7. discord.Forbidden / NotFound / HTTPException → mensajes mapeados
  8. Exception genérica → "Unexpected error"
  9. resultado no-dict  → envuelto en {"result": ...}
 10. éxito             → dict tal cual
 11. execute(call) y execute_by_name(name, args) → mismo dispatch

Los handlers se inyectan por instancia (setattr `_do_<name>`) para probar el
dispatcher de forma aislada, sin depender de la lógica de cada tool.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import discord
import pytest

from utils.discord_tools import ToolExecutor, FORBIDDEN
from utils.tools._constants import _DB_REQUIRED_TOOLS


# ── Helpers de mock ──────────────────────────────────────────────────────────

class _Perms:
    """Imita discord.Permissions: atributo no definido → False."""
    def __init__(self, **flags):
        self._flags = flags
    def __getattr__(self, name):
        return self._flags.get(name, False)


def _make_guild(owner_id: int = 1, bot_perms: dict | None = None, has_me: bool = True):
    guild = MagicMock()
    guild.owner_id = owner_id
    guild._members = {}
    guild.get_member = lambda uid: guild._members.get(uid)
    if has_me:
        me = MagicMock()
        me.guild_permissions = _Perms(**(bot_perms or {}))
        guild.me = me
    else:
        guild.me = None
    return guild


def _add_member(guild, uid: int, **perms):
    m = MagicMock()
    m.id = uid
    m.guild = guild
    m.guild_permissions = _Perms(**perms)
    guild._members[uid] = m
    return m


def _exec(guild=None, channel=None, db=None, **kw) -> ToolExecutor:
    return ToolExecutor(guild or _make_guild(), channel or MagicMock(), db, **kw)


def _inject(executor: ToolExecutor, name: str, fn):
    """Inyecta un handler async `_do_<name>` en la instancia."""
    setattr(executor, f"_do_{name}", fn)


def _discord_exc(cls, status: int):
    resp = MagicMock()
    resp.status = status
    resp.reason = "test"
    return cls(resp, "boom")


# ═══════════════════════════════════════════════════════════════════════════
# 1. Guards previos a la ejecución
# ═══════════════════════════════════════════════════════════════════════════

class TestDispatchGuards:
    async def test_forbidden_tool_blocked(self):
        ex = _exec()
        res = await ex.execute_by_name("delete_channel", {})
        assert "disabled" in res["error"].lower()

    async def test_all_forbidden_tools_blocked(self):
        ex = _exec()
        for name in FORBIDDEN:
            res = await ex.execute_by_name(name, {})
            assert "error" in res and "disabled" in res["error"].lower(), name

    async def test_unknown_tool(self):
        ex = _exec()
        res = await ex.execute_by_name("definitely_not_a_real_tool_xyz", {})
        assert "Unknown function" in res["error"]

    async def test_db_required_without_db(self):
        # search_messages está en _DB_REQUIRED_TOOLS y tiene handler real.
        assert "search_messages" in _DB_REQUIRED_TOOLS
        ex = _exec(db=None)
        res = await ex.execute_by_name("search_messages", {})
        assert "Database unavailable" in res["error"]

    async def test_bot_missing_permission(self):
        # ban_user requiere ban_members en el bot; sin él → error.
        ex = _exec(guild=_make_guild(bot_perms={}), db=MagicMock())
        res = await ex.execute_by_name("ban_user", {"user_id": "5"})
        assert "lacks required permission" in res["error"]
        assert "ban_members" in res["error"]

    async def test_bot_not_in_guild(self):
        ex = _exec(guild=_make_guild(has_me=False), db=MagicMock())
        res = await ex.execute_by_name("ban_user", {"user_id": "5"})
        assert "Bot not found in guild" in res["error"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. Permission layer A1 (usuario que originó el mensaje)
# ═══════════════════════════════════════════════════════════════════════════

class TestPermissionLayerA1:
    async def test_enforce_blocks_user_without_perm(self, monkeypatch):
        monkeypatch.setenv("FAIRY_TOOL_PERMS_ENFORCE", "1")
        guild = _make_guild(bot_perms={"ban_members": True})
        _add_member(guild, 42)  # sin ban_members
        ex = _exec(guild=guild, db=MagicMock(), public_user_id=42, author_id=42)
        res = await ex.execute_by_name("ban_user", {"user_id": "5"})
        assert res.get("required_perm") == "ban_members"

    async def test_logonly_allows_but_proceeds(self, monkeypatch):
        # Sin enforce: el check sólo loggea; la tool debe proceder.
        monkeypatch.delenv("FAIRY_TOOL_PERMS_ENFORCE", raising=False)
        guild = _make_guild(bot_perms={"ban_members": True})
        _add_member(guild, 42)  # sin ban_members
        ex = _exec(guild=guild, db=MagicMock(), public_user_id=42, author_id=42)
        sentinel = {"reached_handler": True}
        _inject(ex, "ban_user", _async_return(sentinel))
        res = await ex.execute_by_name("ban_user", {"user_id": "5"})
        assert res == sentinel  # no fue bloqueado

    async def test_admin_actor_bypasses(self, monkeypatch):
        monkeypatch.setenv("FAIRY_TOOL_PERMS_ENFORCE", "1")
        guild = _make_guild(bot_perms={"ban_members": True})
        _add_member(guild, 99, administrator=True)
        ex = _exec(guild=guild, db=MagicMock(), public_user_id=99, author_id=99)
        sentinel = {"ok": True}
        _inject(ex, "ban_user", _async_return(sentinel))
        res = await ex.execute_by_name("ban_user", {"user_id": "5"})
        assert res == sentinel

    async def test_author_id_used_when_no_public_user_id(self, monkeypatch):
        # A1 fix: la ruta principal pasa author_id (no public_user_id).
        monkeypatch.setenv("FAIRY_TOOL_PERMS_ENFORCE", "1")
        guild = _make_guild(bot_perms={"ban_members": True})
        _add_member(guild, 7)  # sin perm
        ex = _exec(guild=guild, db=MagicMock(), author_id=7)  # public_user_id=0
        res = await ex.execute_by_name("ban_user", {"user_id": "5"})
        assert res.get("required_perm") == "ban_members"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Manejo de resultados y entrypoints
# ═══════════════════════════════════════════════════════════════════════════

class TestResultHandling:
    async def test_success_dict_passthrough(self):
        ex = _exec()
        _inject(ex, "echo", _async_return({"ok": 1}))
        assert await ex.execute_by_name("echo", {}) == {"ok": 1}

    async def test_nondict_result_wrapped(self):
        ex = _exec()
        _inject(ex, "echo", _async_return("hola"))
        assert await ex.execute_by_name("echo", {}) == {"result": "hola"}

    async def test_args_forwarded_to_handler(self):
        ex = _exec()
        async def _h(**kw):
            return {"got": kw}
        _inject(ex, "echo", _h)
        res = await ex.execute_by_name("echo", {"a": 1, "b": "x"})
        assert res["got"] == {"a": 1, "b": "x"}

    async def test_execute_entrypoint_uses_call_name_args(self):
        ex = _exec()
        _inject(ex, "echo", _async_return({"ok": True}))
        call = SimpleNamespace(name="echo", args={"k": "v"})
        assert await ex.execute(call) == {"ok": True}

    async def test_execute_with_none_args(self):
        ex = _exec()
        _inject(ex, "echo", _async_return({"ok": True}))
        call = SimpleNamespace(name="echo", args=None)
        assert await ex.execute(call) == {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# 4. Mapeo de excepciones
# ═══════════════════════════════════════════════════════════════════════════

class TestExceptionMapping:
    async def test_timeout(self, monkeypatch):
        monkeypatch.setattr("utils.discord_tools._DEFAULT_TOOL_TIMEOUT", 0.05)
        ex = _exec()
        async def _slow(**_):
            await asyncio.sleep(1)
        _inject(ex, "slowtool", _slow)
        res = await ex.execute_by_name("slowtool", {})
        assert "timed out" in res["error"]

    async def test_forbidden_mapped(self):
        ex = _exec()
        _inject(ex, "boom", _async_raise(_discord_exc(discord.Forbidden, 403)))
        res = await ex.execute_by_name("boom", {})
        assert "Missing Discord permissions" in res["error"]

    async def test_notfound_mapped(self):
        ex = _exec()
        _inject(ex, "boom", _async_raise(_discord_exc(discord.NotFound, 404)))
        res = await ex.execute_by_name("boom", {})
        assert "not found" in res["error"].lower()

    async def test_httpexception_mapped(self):
        ex = _exec()
        _inject(ex, "boom", _async_raise(_discord_exc(discord.HTTPException, 500)))
        res = await ex.execute_by_name("boom", {})
        assert "Discord API error" in res["error"]

    async def test_generic_exception_mapped(self):
        ex = _exec()
        _inject(ex, "boom", _async_raise(ValueError("kaboom")))
        res = await ex.execute_by_name("boom", {})
        assert "Unexpected error" in res["error"]
        assert "ValueError" in res["error"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. Invariante para el split (M1): toda tool declarada debe seguir resolviendo
#    a un handler invocable EN LA INSTANCIA (atrapa un mixin no heredado, un
#    handler movido a otro módulo que no se enganchó, etc.).
# ═══════════════════════════════════════════════════════════════════════════

class TestHandlerInvariant:
    def test_every_declared_tool_resolves_on_instance(self):
        from utils.discord_tools import TOOL_DECLARATIONS
        ex = _exec()
        missing = [
            d.name for d in TOOL_DECLARATIONS
            if not callable(getattr(ex, f"_do_{d.name}", None))
        ]
        assert not missing, f"Tools declaradas sin handler invocable en instancia: {missing}"

    def test_executor_constructs_with_minimal_args(self):
        # El split no debe romper la firma del constructor.
        ex = ToolExecutor(_make_guild(), MagicMock(), None)
        assert ex.guild is not None


# ── Factories de handlers async ──────────────────────────────────────────────

def _async_return(value):
    async def _h(**_):
        return value
    return _h


def _async_raise(exc):
    async def _h(**_):
        raise exc
    return _h
