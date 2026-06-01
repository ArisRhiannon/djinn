"""Tests for utils/security.py — SSRF guard + permission map.

Wave 7 (F5.1).  Cubre:
  • is_url_safe: schemes válidos/inválidos, IPs privadas, link-local,
    loopback, multicast, IPv6 ::1, hostnames bloqueados, DNS resolution.
  • member_has_tool_permission: owner/admin/normal user, mapping correcto.
  • tool_required_perm: lookups y casos sin permiso requerido.
"""

from __future__ import annotations

import pytest

from utils.security import (
    URLSafetyError,
    is_url_safe,
    member_has_tool_permission,
    tool_required_perm,
    TOOL_REQUIRED_PERMS,
)


# ─── is_url_safe ────────────────────────────────────────────────────────────


class TestIsUrlSafe:

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/",
        "https://127.0.0.1:8080/api/v1/status",
        "http://localhost/x",
        "http://localhost:8080",
        "http://[::1]/",
        "http://10.0.0.1/",
        "http://10.255.255.255/foo",
        "http://172.16.0.1/",
        "http://172.31.255.254/",
        "http://192.168.1.1/",
        "http://192.168.0.0/",
        "http://169.254.169.254/latest/meta-data/",  # AWS metadata
        "http://0.0.0.0/",
        "ftp://example.com/",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "",
    ])
    def test_blocked(self, url):
        ok, reason = is_url_safe(url)
        assert ok is False
        assert reason  # non-empty motivo

    @pytest.mark.parametrize("url", [
        "https://google.com/",
        "https://www.google.com/search?q=foo",
        "http://wttr.in/Madrid",
        "https://api.openai.com/v1/chat/completions",
        "https://raw.githubusercontent.com/foo/bar/main/README.md",
    ])
    def test_allowed(self, url):
        ok, reason = is_url_safe(url)
        # Estas URLs reales pueden fallar resolución DNS en entornos sin red,
        # pero NO por la lógica de filtrado. Si hay reason por DNS, lo aceptamos.
        if not ok:
            assert "DNS" in reason or "resolución" in reason
        else:
            assert reason == ""

    def test_invalid_scheme_caps(self):
        ok, reason = is_url_safe("HTTP://google.com/")  # scheme normalizado a lower
        # Igual: la parsing devuelve scheme normalizado; debe permitir.
        # Si DNS falla en el sandbox, aceptamos.
        if not ok:
            assert "DNS" in reason or "resolución" in reason

    def test_none_input(self):
        ok, reason = is_url_safe(None)  # type: ignore[arg-type]
        assert ok is False
        assert "vacía" in reason or "string" in reason

    def test_allow_localhost_flag(self):
        ok, _ = is_url_safe("http://127.0.0.1/x", allow_localhost=True)
        assert ok is True
        ok, _ = is_url_safe("http://localhost/x", allow_localhost=True)
        assert ok is True


# ─── tool_required_perm ─────────────────────────────────────────────────────


class TestToolRequiredPerm:

    def test_returns_perm_for_destructive_tool(self):
        assert tool_required_perm("ban_user") == "ban_members"
        assert tool_required_perm("purge_messages") == "manage_messages"
        assert tool_required_perm("create_role") == "manage_roles"
        assert tool_required_perm("backup_server") == "manage_guild"

    def test_returns_none_for_unrestricted_tool(self):
        assert tool_required_perm("send_message") is None
        assert tool_required_perm("read_skill") is None
        assert tool_required_perm("search_messages") is None

    def test_returns_none_for_unknown_tool(self):
        assert tool_required_perm("totally_made_up_tool_xyz") is None

    def test_destructive_tools_present(self):
        # Sanity: las tools obvias tienen permiso requerido
        for t in ("ban_user", "kick_user", "mute_user", "purge_messages",
                  "delete_message", "add_role", "remove_role"):
            assert t in TOOL_REQUIRED_PERMS, f"{t} should require permission"


# ─── member_has_tool_permission ─────────────────────────────────────────────


class TestMemberHasToolPermission:

    def test_owner_passes_anything(self, make_member, fake_guild):
        owner = make_member(fake_guild.owner_id)  # sin permisos explícitos
        # owner_id == member.id → owner detected
        ok, _ = member_has_tool_permission(owner, "ban_user")
        assert ok is True

    def test_administrator_passes_anything(self, make_member):
        admin = make_member(42, administrator=True)
        ok, _ = member_has_tool_permission(admin, "ban_user")
        assert ok is True
        ok, _ = member_has_tool_permission(admin, "purge_messages")
        assert ok is True

    def test_user_with_specific_perm_allowed(self, make_member):
        m = make_member(99, ban_members=True)
        ok, _ = member_has_tool_permission(m, "ban_user")
        assert ok is True

    def test_user_without_perm_blocked(self, make_member):
        m = make_member(99)  # sin permisos
        ok, missing = member_has_tool_permission(m, "ban_user")
        assert ok is False
        assert missing == "ban_members"

    def test_unrestricted_tool_always_allowed(self, make_member):
        m = make_member(99)
        ok, missing = member_has_tool_permission(m, "send_message")
        assert ok is True
        assert missing is None

    def test_none_member_allows_for_compatibility(self):
        ok, missing = member_has_tool_permission(None, "ban_user")
        assert ok is True
        assert missing is None

    def test_user_with_other_perm_still_blocked(self, make_member):
        m = make_member(99, manage_messages=True)
        # tiene manage_messages pero no ban_members
        ok, missing = member_has_tool_permission(m, "ban_user")
        assert ok is False
        assert missing == "ban_members"
        # pero sí puede purgar
        ok2, _ = member_has_tool_permission(m, "purge_messages")
        assert ok2 is True


# ─── URLSafetyError ─────────────────────────────────────────────────────────


def test_url_safety_error_is_value_error():
    """URLSafetyError debe ser subclase de ValueError para compat con except."""
    assert issubclass(URLSafetyError, ValueError)
