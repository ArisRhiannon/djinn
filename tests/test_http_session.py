"""Tests for utils/http_session.py."""

from __future__ import annotations

import pytest

from utils import http_session


@pytest.fixture(autouse=True)
async def _reset_session():
    yield
    # cleanup tras cada test
    await http_session.close_shared_session()


@pytest.mark.asyncio
async def test_lazy_init_creates_session():
    assert not http_session.is_initialized()
    s = await http_session.shared_session()
    assert s is not None
    assert http_session.is_initialized()


@pytest.mark.asyncio
async def test_returns_same_instance():
    a = await http_session.shared_session()
    b = await http_session.shared_session()
    assert a is b


@pytest.mark.asyncio
async def test_close_releases():
    await http_session.shared_session()
    assert http_session.is_initialized()
    await http_session.close_shared_session()
    assert not http_session.is_initialized()


@pytest.mark.asyncio
async def test_recreate_after_close():
    a = await http_session.shared_session()
    await http_session.close_shared_session()
    b = await http_session.shared_session()
    assert b is not a  # nueva instancia


@pytest.mark.asyncio
async def test_close_when_uninitialized_is_noop():
    # No debe lanzar excepción si nunca se creó
    await http_session.close_shared_session()
    await http_session.close_shared_session()
