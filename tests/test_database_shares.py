"""Tests for Youkai Financial Services™ advanced economy, dynamic interest, late fees, and shares/dividends.

Wave 10 Verification:
- Database schema migrations for loans and guild_treasury
- Dynamic loan interest rate calculations based on liquidity
- Late fee / penalty accumulations on failed payments
- Investment deposits, shares, withdrawals, liquidity checks
- O(1) dividend payouts and claims
"""

from __future__ import annotations

import asyncio
import math
import pytest
import aiosqlite
from pathlib import Path

from utils.database import Database
from utils.loan_engine import calculate_interest, compute_loan


@pytest.mark.asyncio
async def test_database_shares_migration_and_tables(tmp_path):
    db_path = tmp_path / "test_shares.db"
    db = Database(str(db_path))
    await db.initialize()

    # Verify migration v10 executed
    async with db._db.execute("PRAGMA user_version") as cur:
        row = await cur.fetchone()
        assert row[0] >= 10

    # Check tables exist
    async with db._db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
        tables = {r["name"] for r in await cur.fetchall()}
        assert "treasury_shares" in tables
        assert "guild_treasury" in tables
        assert "loans" in tables

    # Verify column additions in loans and guild_treasury
    async with db._db.execute("PRAGMA table_info(loans)") as cur:
        cols = {r["name"] for r in await cur.fetchall()}
        assert "accrued_late_fees" in cols

    async with db._db.execute("PRAGMA table_info(guild_treasury)") as cur:
        cols = {r["name"] for r in await cur.fetchall()}
        assert "total_shares" in cols
        assert "total_dividends_paid" in cols

    await db.close()


@pytest.mark.asyncio
async def test_database_shares_interest_rate_fluctuation(tmp_path):
    db_path = tmp_path / "test_interest.db"
    db = Database(str(db_path))
    await db.initialize()

    guild_id = 12345

    # Initially treasury is bootstrapped to 6000 credits
    bal, cap = await db.get_treasury_liquidity_info(guild_id)
    assert bal == 6000
    assert cap == 6000

    # Rate at default score 500 (Base rate is 1.10)
    # Liquidity ratio = 6000 / 6000 = 1.0 (100% liquidity)
    # Final rate = 1.10 + (1 - 1) * 0.5 = 1.10
    rate = calculate_interest(500, bal, cap)
    assert rate == 1.10

    # Test rate calculation with low liquidity
    # Say balance drops to 1500, capital total is 6000
    # Liquidity ratio = 1500 / 6000 = 0.25 (25% liquidity)
    # Premium = (1.0 - 0.25) * 0.5 = 0.375
    # Final rate = 1.10 + 0.375 = 1.475 -> rounded to 2 decimals -> 1.48
    rate_low = calculate_interest(500, 1500, 6000)
    assert rate_low == 1.48

    # Test rate calculation with zero liquidity
    # Premium = (1.0 - 0.0) * 0.5 = 0.5
    # Final rate = 1.10 + 0.5 = 1.60
    rate_zero = calculate_interest(500, 0, 6000)
    assert rate_zero == 1.60

    await db.close()


@pytest.mark.asyncio
async def test_database_shares_invest_withdraw(tmp_path):
    db_path = tmp_path / "test_invest_withdraw.db"
    db = Database(str(db_path))
    await db.initialize()

    user_id = 999
    guild_id = 888

    # Give user credits first
    await db.add_credits(user_id, guild_id, 2000, reason="init")

    # 1. Invest 1000 credits
    new_shares = await db.invest_in_treasury(user_id, guild_id, 1000)
    assert new_shares == 1000

    # Verify user's credit balance decreased
    creds = await db.get_credits(user_id, guild_id)
    assert creds["balance"] == 1000

    # Verify treasury balance and total shares increased
    bal, cap = await db.get_treasury_liquidity_info(guild_id)
    # Initial balance is 6000 + 1000 = 7000. Capital is 6000 (bootstrap) + 1000 = 7000.
    assert bal == 7000
    assert cap == 7000

    # Check database rows
    row_user_shares = await db.fetchone(
        "SELECT shares, unclaimed_dividends FROM treasury_shares WHERE user_id=? AND guild_id=?",
        (user_id, guild_id)
    )
    assert row_user_shares["shares"] == 1000
    assert row_user_shares["unclaimed_dividends"] == 0.0

    # 2. Try to invest more than balance
    with pytest.raises(ValueError, match="Saldo de créditos insuficiente"):
        await db.invest_in_treasury(user_id, guild_id, 5000)

    # 3. Withdraw 400 shares
    remaining_shares = await db.withdraw_from_treasury(user_id, guild_id, 400)
    assert remaining_shares == 600

    # Verify user's credit balance increased
    creds = await db.get_credits(user_id, guild_id)
    assert creds["balance"] == 1400

    # Verify treasury balance decreased
    bal, cap = await db.get_treasury_liquidity_info(guild_id)
    assert bal == 6600
    assert cap == 6600

    # 4. Try to withdraw more shares than owned
    with pytest.raises(ValueError, match="No tienes suficientes acciones"):
        await db.withdraw_from_treasury(user_id, guild_id, 800)

    # 5. Try to withdraw more than treasury's liquidity (bank run scenario)
    # First, let's drain the treasury balance by making a large loan
    # For testing, we can manually update guild_treasury balance to a low value
    async with db.write_lock:
        await db._db.execute("UPDATE guild_treasury SET balance = 100 WHERE guild_id = ?", (guild_id,))
        await db._safe_commit()

    # Try to withdraw 500 actions (wants 500 credits, but treasury only has 100)
    with pytest.raises(ValueError, match="no cuenta con suficiente liquidez"):
        await db.withdraw_from_treasury(user_id, guild_id, 500)

    await db.close()


@pytest.mark.asyncio
async def test_database_shares_dividends_distribution_and_claim(tmp_path):
    db_path = tmp_path / "test_dividends.db"
    db = Database(str(db_path))
    await db.initialize()

    guild_id = 555
    user_a = 111
    user_b = 222
    user_c = 333  # Borrower

    # Give credits to investors
    await db.add_credits(user_a, guild_id, 1000, reason="init")
    await db.add_credits(user_b, guild_id, 1000, reason="init")

    # Invest to buy shares
    # A buys 600 shares, B buys 400 shares. Total shares = 1000
    await db.invest_in_treasury(user_a, guild_id, 600)
    await db.invest_in_treasury(user_b, guild_id, 400)

    # Create a loan for user C
    # Principal: 1000, rate: 0.5, total: 1500, installment: 300, installments: 5
    loan_id = await db.create_loan_with_treasury(user_c, guild_id, 1, 1000, 0.5, 1500, 300, 5)
    assert loan_id is not None

    # Simulate User C paying an installment of 300 credits
    # Interest portion of the payment = paid * (total_owed - principal) / total_owed
    # Interest portion = 300 * (1500 - 1000) / 1500 = 100.0 credits
    # Dividend per share = 100.0 / 1000 shares = 0.1 credits/share
    # User A (600 shares) gets: 600 * 0.1 = 60.0 unclaimed dividends
    # User B (400 shares) gets: 400 * 0.1 = 40.0 unclaimed dividends
    await db.record_loan_payment(loan_id, user_c, guild_id, 300, 300, True, 300, 0)

    # Check dividends
    row_a = await db.fetchone("SELECT unclaimed_dividends FROM treasury_shares WHERE user_id=? AND guild_id=?", (user_a, guild_id))
    row_b = await db.fetchone("SELECT unclaimed_dividends FROM treasury_shares WHERE user_id=? AND guild_id=?", (user_b, guild_id))
    assert row_a["unclaimed_dividends"] == 60.0
    assert row_b["unclaimed_dividends"] == 40.0

    # Claim dividends for user A
    claimed_a = await db.claim_dividends(user_a, guild_id)
    assert claimed_a == 60

    # Verify user A's balance increased
    creds_a = await db.get_credits(user_a, guild_id)
    # User A had: 1000 - 600 (invested) = 400 + 60 (claimed) = 460
    assert creds_a["balance"] == 460

    # Verify user A's unclaimed_dividends reset
    row_a_after = await db.fetchone("SELECT unclaimed_dividends FROM treasury_shares WHERE user_id=? AND guild_id=?", (user_a, guild_id))
    assert row_a_after["unclaimed_dividends"] == 0.0

    await db.close()


@pytest.mark.asyncio
async def test_database_shares_late_fees_compound(tmp_path):
    db_path = tmp_path / "test_late_fees.db"
    db = Database(str(db_path))
    await db.initialize()

    guild_id = 777
    user_id = 666

    # Create loan
    # Principal: 1000, rate: 0.5, total: 1500, installment: 375, installments: 4
    loan_id = await db.create_loan_with_treasury(user_id, guild_id, 1, 1000, 0.5, 1500, 375, 4)
    assert loan_id is not None

    # Simulate failed payment (success = False)
    # Late fee: 10% of installment (375 * 0.1 = 37.5) + 5% of remaining debt (1500 * 0.05 = 75.0)
    # Total late fee = ceil(37.5 + 75.0) = ceil(112.5) = 113
    await db.record_loan_payment(loan_id, user_id, guild_id, 375, 0, False, 100, 100)

    # Check loan status in DB
    row_loan = await db.fetchone("SELECT accrued_late_fees, remaining_debt, total_owed FROM loans WHERE id=?", (loan_id,))
    assert row_loan["accrued_late_fees"] == 113
    assert row_loan["remaining_debt"] == 1613
    assert row_loan["total_owed"] == 1613

    await db.close()
