"""Tests for utils/safe_domains.py — domain whitelist loader."""

from __future__ import annotations

from utils.safe_domains import is_safe_domain, reload_safe_domains, safe_domains


class TestSafeDomains:

    def test_loads_dataset(self):
        s = safe_domains()
        assert len(s) > 5_000, "esperaba miles de dominios cargados"

    def test_well_known_domains_pass(self):
        for d in ("google.com", "youtube.com", "github.com", "wikipedia.org"):
            assert is_safe_domain(d) is True, f"{d} debería estar safe"

    def test_unknown_domain_fails(self):
        # Hash random improbable de estar en la lista
        assert is_safe_domain("xyz-totally-fake-zzz-9999.example") is False

    def test_subdomain_match(self):
        # Si "google.com" está, "mail.google.com" debe matchear por subdominio
        if is_safe_domain("google.com"):
            assert is_safe_domain("mail.google.com") is True
            assert is_safe_domain("a.b.c.google.com") is True

    def test_case_insensitive(self):
        assert is_safe_domain("GOOGLE.COM") == is_safe_domain("google.com")

    def test_trailing_dot_handled(self):
        assert is_safe_domain("google.com.") == is_safe_domain("google.com")

    def test_empty_input(self):
        assert is_safe_domain("") is False
        assert is_safe_domain("   ") is False
        assert is_safe_domain(None) is False  # type: ignore[arg-type]

    def test_ip_string_not_in_list(self):
        # IPs no son dominios → no matchean
        assert is_safe_domain("127.0.0.1") is False
        assert is_safe_domain("8.8.8.8") is False

    def test_reload_returns_count(self):
        n = reload_safe_domains()
        assert n > 5_000
