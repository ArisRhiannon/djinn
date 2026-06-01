"""Tests for utils/database.py — credit ledger and atomic credit transactions.

Wave 9: Verification of schema migrations, user_credits, credit_ledger,
and concurrent safe transactions.
"""

from __future__ import annotations

import asyncio
import pytest
import aiosqlite
from pathlib import Path

from utils.database import Database


@pytest.mark.asyncio
async def test_database_credits_migration_and_basic_flow(tmp_path):
    db_path = tmp_path / "test_credits.db"
    db = Database(str(db_path))
    await db.initialize()

    # 1. Check that SCHEMA was executed and migration v9 was run
    async with db._db.execute("PRAGMA user_version") as cur:
        row = await cur.fetchone()
        assert row[0] >= 9

    # 2. Check tables exist
    async with db._db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
        tables = {r["name"] for r in await cur.fetchall()}
        assert "user_credits" in tables
        assert "credit_ledger" in tables

    # 3. Test initial state
    creds = await db.get_credits(123, 456)
    assert creds["balance"] == 0
    assert creds["earned_today"] == 0
    assert creds["spent_today"] == 0

    # 4. Test adding credits
    new_bal = await db.add_credits(123, 456, 100, reason="test_add", ref="ref1")
    assert new_bal == 100

    creds = await db.get_credits(123, 456)
    assert creds["balance"] == 100
    assert creds["earned_today"] == 100

    # 5. Test spending credits
    new_bal = await db.spend_credits(123, 456, 40, reason="test_spend", ref="ref2")
    assert new_bal == 60

    creds = await db.get_credits(123, 456)
    assert creds["balance"] == 60
    assert creds["spent_today"] == 40

    # 6. Verify ledger content
    async with db._db.execute("SELECT * FROM credit_ledger ORDER BY rowid ASC") as cur:
        ledger_rows = [dict(r) for r in await cur.fetchall()]
        assert len(ledger_rows) == 2

        # Row 1 (Add credits)
        assert ledger_rows[0]["uid"] == 123
        assert ledger_rows[0]["gid"] == 456
        assert ledger_rows[0]["delta"] == 100
        assert ledger_rows[0]["bal"] == 100
        assert ledger_rows[0]["reason"] == "test_add"
        assert ledger_rows[0]["ref"] == "ref1"
        assert len(ledger_rows[0]["hash"]) == 8

        # Row 2 (Spend credits)
        assert ledger_rows[1]["uid"] == 123
        assert ledger_rows[1]["gid"] == 456
        assert ledger_rows[1]["delta"] == -40
        assert ledger_rows[1]["bal"] == 60
        assert ledger_rows[1]["reason"] == "test_spend"
        assert ledger_rows[1]["ref"] == "ref2"
        assert len(ledger_rows[1]["hash"]) == 8

    await db.close()


@pytest.mark.asyncio
async def test_database_credits_concurrency(tmp_path):
    db_path = tmp_path / "test_credits_concurrent.db"
    db = Database(str(db_path))
    await db.initialize()

    user_id = 999
    guild_id = 888

    # Run 50 concurrent additions of 10 credits each
    tasks = [db.add_credits(user_id, guild_id, 10, reason=f"concurrent_add_{i}") for i in range(50)]
    await asyncio.gather(*tasks)

    creds = await db.get_credits(user_id, guild_id)
    assert creds["balance"] == 500
    assert creds["earned_today"] == 500

    # Ledger should have 50 rows
    async with db._db.execute("SELECT COUNT(*) as cnt FROM credit_ledger WHERE uid=? AND gid=?", (user_id, guild_id)) as cur:
        row = await cur.fetchone()
        assert row["cnt"] == 50

    # Verify that ledger balances match the deltas sequentially
    async with db._db.execute("SELECT delta, bal FROM credit_ledger WHERE uid=? AND gid=? ORDER BY rowid ASC", (user_id, guild_id)) as cur:
        ledger_rows = [dict(r) for r in await cur.fetchall()]
        current_sum = 0
        for r in ledger_rows:
            current_sum += r["delta"]
            assert r["delta"] == 10
            assert r["bal"] == current_sum

    # Run 20 concurrent spend operations of 5 credits each
    spend_tasks = [db.spend_credits(user_id, guild_id, 5, reason=f"concurrent_spend_{i}") for i in range(20)]
    await asyncio.gather(*spend_tasks)

    creds = await db.get_credits(user_id, guild_id)
    assert creds["balance"] == 400

    # Total ledger rows should be 50 + 20 = 70
    async with db._db.execute("SELECT COUNT(*) as cnt FROM credit_ledger WHERE uid=? AND gid=?", (user_id, guild_id)) as cur:
        row = await cur.fetchone()
        assert row["cnt"] == 70

    # Verify final chronological balance checks
    async with db._db.execute("SELECT delta, bal FROM credit_ledger WHERE uid=? AND gid=? ORDER BY rowid ASC", (user_id, guild_id)) as cur:
        ledger_rows = [dict(r) for r in await cur.fetchall()]
        current_sum = 0
        for r in ledger_rows:
            current_sum += r["delta"]
            assert r["bal"] == current_sum

    await db.close()


@pytest.mark.asyncio
async def test_spend_credits_never_goes_negative(tmp_path):
    """F1: el débito condicional (WHERE balance>=?) impide balance negativo y
    doble gasto bajo concurrencia, incluso si can_spend() no se llamó antes."""
    db = Database(str(tmp_path / "test_f1.db"))
    await db.initialize()
    uid, gid = 111, 222
    await db.add_credits(uid, gid, 100, reason="seed")

    # Gasto insuficiente directo: no debe debitar ni dejar negativo.
    bal = await db.spend_credits(uid, gid, 150, reason="too_much")
    assert bal == 100
    assert (await db.get_credits(uid, gid))["balance"] == 100

    # 10 gastos concurrentes de 30 desde balance 100 → solo caben 3 (90),
    # el resto debe fallar sin dejar negativo.
    await asyncio.gather(*[db.spend_credits(uid, gid, 30) for _ in range(10)])
    final = (await db.get_credits(uid, gid))["balance"]
    assert final >= 0          # invariante clave de F1: nunca negativo
    assert final == 10         # exactamente 3 débitos de 30 caben en 100

    await db.close()
