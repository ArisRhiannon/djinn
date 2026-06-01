"""Tests for active award monthly role assignment and database logic.
"""
from __future__ import annotations

import datetime
import calendar
import pytest
import aiosqlite
from pathlib import Path

from utils.database import Database


@pytest.mark.asyncio
async def test_database_active_award_runs(tmp_path):
    db_path = tmp_path / "test_active_award.db"
    db = Database(str(db_path))
    await db.initialize()

    # Verify migration v11 executed
    async with db._db.execute("PRAGMA user_version") as cur:
        row = await cur.fetchone()
        assert row[0] >= 11

    # Check tables exist
    async with db._db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
        tables = {r["name"] for r in await cur.fetchall()}
        assert "active_award_runs" in tables

    # Test runs tracking functions
    guild_id = 1269877200488763472
    year = 2026
    month = 5
    user_id = 239550977638793217

    # Initially has not been run
    has_run = await db.has_active_award_run(guild_id, year, month)
    assert has_run is False

    # Record run
    await db.record_active_award_run(guild_id, year, month, user_id)

    # Now it has been run
    has_run = await db.has_active_award_run(guild_id, year, month)
    assert has_run is True

    # Check query most active user in timeframe
    # Insert some dummy messages
    start_ts = int(datetime.datetime(2026, 5, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
    mid_ts = int(datetime.datetime(2026, 5, 15, 12, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
    end_ts = int(datetime.datetime(2026, 5, 31, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp())

    # Insert messages for user A and user B
    async with db.write_lock:
        # User A: 3 messages
        await db._db.execute(
            "INSERT INTO messages (guild_id, channel_id, user_id, username, content, timestamp) "
            "VALUES (?, 1, 100, 'UserA', 'Message 1', ?)", (guild_id, mid_ts)
        )
        await db._db.execute(
            "INSERT INTO messages (guild_id, channel_id, user_id, username, content, timestamp) "
            "VALUES (?, 1, 100, 'UserA', 'Message 2', ?)", (guild_id, mid_ts)
        )
        await db._db.execute(
            "INSERT INTO messages (guild_id, channel_id, user_id, username, content, timestamp) "
            "VALUES (?, 1, 100, 'UserA', 'Message 3', ?)", (guild_id, mid_ts)
        )
        # User B: 2 messages
        await db._db.execute(
            "INSERT INTO messages (guild_id, channel_id, user_id, username, content, timestamp) "
            "VALUES (?, 1, 101, 'UserB', 'Message 1', ?)", (guild_id, mid_ts)
        )
        await db._db.execute(
            "INSERT INTO messages (guild_id, channel_id, user_id, username, content, timestamp) "
            "VALUES (?, 1, 101, 'UserB', 'Message 2', ?)", (guild_id, mid_ts)
        )
        await db._safe_commit()

    # Get most active
    winner = await db.get_most_active_user(guild_id, start_ts, end_ts)
    assert winner is not None
    assert winner["user_id"] == 100
    assert winner["msg_count"] == 3
    assert winner["username"] == "UserA"

    # Get most active list
    winners = await db.get_most_active_users(guild_id, start_ts, end_ts, limit=5)
    assert len(winners) == 2
    assert winners[0]["user_id"] == 100
    assert winners[1]["user_id"] == 101

    await db.close()


def test_active_award_current_month_calculation():
    # Test datetime range logic for active award (day 1 to day 25 of current month)
    # If today is June 25, 2026:
    now = datetime.datetime(2026, 6, 25, 15, 30, 0, tzinfo=datetime.timezone.utc)
    
    start_date = datetime.date(now.year, now.month, 1)
    end_date = datetime.date(now.year, now.month, 25)

    assert start_date == datetime.date(2026, 6, 1)
    assert end_date == datetime.date(2026, 6, 25)


def test_active_award_trigger_logic():
    # Helper lambda to simulate timing logic
    should_run = lambda dt: not (dt.day < 25 or (dt.day == 25 and dt.hour < 23))

    # Before the 25th (should not trigger)
    assert should_run(datetime.datetime(2026, 6, 24, 23, 59, 59, tzinfo=datetime.timezone.utc)) is False
    assert should_run(datetime.datetime(2026, 6, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)) is False

    # On the 25th before 23:00 UTC (should not trigger)
    assert should_run(datetime.datetime(2026, 6, 25, 0, 0, 0, tzinfo=datetime.timezone.utc)) is False
    assert should_run(datetime.datetime(2026, 6, 25, 22, 59, 59, tzinfo=datetime.timezone.utc)) is False

    # On the 25th at or after 23:00 UTC (should trigger)
    assert should_run(datetime.datetime(2026, 6, 25, 23, 0, 0, tzinfo=datetime.timezone.utc)) is True
    assert should_run(datetime.datetime(2026, 6, 25, 23, 59, 0, tzinfo=datetime.timezone.utc)) is True

    # After the 25th (should trigger at any hour for catch-up)
    assert should_run(datetime.datetime(2026, 6, 26, 0, 0, 0, tzinfo=datetime.timezone.utc)) is True
    assert should_run(datetime.datetime(2026, 6, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)) is True

