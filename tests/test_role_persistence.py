"""Tests for role persistence database logic and safety checks.
"""
from __future__ import annotations

import pytest
import aiosqlite
import discord
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from utils.database import Database
from cogs.role_persistence import RolePersistenceCog


@pytest.mark.asyncio
async def test_database_role_persistence_migration(tmp_path):
    db_path = tmp_path / "test_role_persistence.db"
    db = Database(str(db_path))
    await db.initialize()

    # Verify migration v12 executed
    async with db._db.execute("PRAGMA user_version") as cur:
        row = await cur.fetchone()
        assert row[0] >= 12

    # Check table exists
    async with db._db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
        tables = {r["name"] for r in await cur.fetchall()}
        assert "member_roles_persistence" in tables

    # Test single user save and fetch
    guild_id = 999
    user_id = 111
    role_ids = [10, 20, 30]

    roles = await db.get_persisted_roles(guild_id, user_id)
    assert roles == []

    await db.save_persisted_roles(guild_id, user_id, role_ids)
    roles = await db.get_persisted_roles(guild_id, user_id)
    assert roles == role_ids

    # Clear persisted roles
    await db.clear_persisted_roles(guild_id, user_id)
    roles = await db.get_persisted_roles(guild_id, user_id)
    assert roles == []

    # Test bulk save
    bulk_data = [
        (111, [10, 20]),
        (222, [30, 40]),
        (333, []),
    ]
    await db.bulk_save_persisted_roles(guild_id, bulk_data)
    
    assert await db.get_persisted_roles(guild_id, 111) == [10, 20]
    assert await db.get_persisted_roles(guild_id, 222) == [30, 40]
    assert await db.get_persisted_roles(guild_id, 333) == []

    await db.close()


def test_is_safe_role_filtering():
    # Mock bot object to instantiate cog
    bot = MagicMock()
    cog = RolePersistenceCog(bot)

    # Helper function to create mock roles
    def create_mock_role(is_default=False, managed=False, **perms):
        role = MagicMock(spec=discord.Role)
        role.is_default.return_value = is_default
        role.managed = managed
        
        # Setup permissions
        permissions = MagicMock(spec=discord.Permissions)
        # Default all permissions to False
        for attr in dir(permissions):
            if not attr.startswith("_"):
                setattr(permissions, attr, False)
        
        # Override specified perms
        for perm, val in perms.items():
            setattr(permissions, perm, val)
            
        role.permissions = permissions
        return role

    # 1. Default role @everyone (should be unsafe)
    role_everyone = create_mock_role(is_default=True)
    assert cog.is_safe_role(role_everyone) is False

    # 2. Managed role (should be unsafe)
    role_managed = create_mock_role(managed=True)
    assert cog.is_safe_role(role_managed) is False

    # 3. Admin permission role (should be unsafe)
    role_admin = create_mock_role(administrator=True)
    assert cog.is_safe_role(role_admin) is False

    # 4. Mod permission roles (should be unsafe)
    assert cog.is_safe_role(create_mock_role(kick_members=True)) is False
    assert cog.is_safe_role(create_mock_role(ban_members=True)) is False
    assert cog.is_safe_role(create_mock_role(moderate_members=True)) is False
    assert cog.is_safe_role(create_mock_role(manage_messages=True)) is False
    assert cog.is_safe_role(create_mock_role(manage_roles=True)) is False
    assert cog.is_safe_role(create_mock_role(manage_guild=True)) is False
    assert cog.is_safe_role(create_mock_role(manage_channels=True)) is False

    # 5. Normal safe role (should be safe)
    role_normal = create_mock_role()
    assert cog.is_safe_role(role_normal) is True
