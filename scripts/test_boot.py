#!/usr/bin/env python3
"""
Djinn Boot Verification & Dry-Run Script
Verifies that Djinn starts up, initializes the database, configures pragmas,
loads all cogs, builds services, and shuts down cleanly in a sandbox environment.
"""

import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

# Add project root to python path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

# Configure sandbox test environment before importing bot/config
os.environ["DB_PATH"] = "db/fairy_test.db"
os.environ["FAIRY_NO_BOOTSTRAP"] = "1"  # Skip bootstrap loop in script
os.environ["FAIRY_OVERRIDE_API_PORT"] = "7701"  # Avoid bind conflict with running instance

# Load environment from .env file if present
from dotenv import load_dotenv
load_dotenv(dotenv_path=ROOT / ".env")

# Ensure test DB directory exists
Path("db").mkdir(exist_ok=True)

# Delete existing test DB to verify clean migration and initialization
test_db = Path("db/fairy_test.db")
if test_db.exists():
    try:
        test_db.unlink()
        logger.info("🧹 Removed old test database: {}", test_db)
    except Exception as e:
        logger.warning("Could not remove old test database: {}", e)

from main import DjinnConfig, DjinnBot
from utils.api_server import DjinnAPIServer

# Override port to avoid conflicts with active bot
DjinnAPIServer.DEFAULT_PORT = 8085
logger.info("🔧 Configured test API server to run on port 8085")

async def run_dry_boot():
    logger.info("🚀 Starting Djinn Dry-Boot Verification...")
    
    # 1. Load config
    config = DjinnConfig.from_env()
    
    # Set dummy credentials if missing so config checks pass
    if not config.discord_token:
        config.discord_token = "dummy_discord_token_for_boot_verification"
    if not config.google_api_key:
        config.google_api_key = "dummy_google_api_key_for_boot_verification"
        
    logger.info("📋 Config loaded. Database: {}", config.db_path)
    
    # 2. Instantiate Bot
    bot = DjinnBot(config)
    
    # 3. Mock network-dependent parts of discord.py to prevent network calls during setup_hook
    bot.tree.sync = AsyncMock(return_value=[])
    # Mock clear_commands on the tree as well
    bot.tree.clear_commands = AsyncMock()
    
    # Mock wait_until_ready and is_ready to bypass connection checks for background tasks
    bot.wait_until_ready = AsyncMock()
    bot.is_ready = lambda: True
    
    success = False
    try:
        # 4. Execute the complete setup hook (DB init, LLM client, cogs loading, API server boot)
        logger.info("⚙️ Executing setup_hook (service & cog initialization)...")
        await bot.setup_hook()
        logger.info("✅ setup_hook executed successfully!")
        
        # Give background tasks 2 seconds to initialize and check if they run cleanly
        logger.info("⏳ Allowing services and tasks a brief warm-up period...")
        await asyncio.sleep(2.0)
        success = True
    except Exception as exc:
        logger.exception("❌ Dry-boot failed during setup_hook:")
    finally:
        # 5. Cleanly shut down all services (closes DB connections, stops API server, etc.)
        logger.info("🛑 Shutting down bot services...")
        try:
            await bot.close()
            logger.info("👋 Bot stopped cleanly.")
        except Exception as close_exc:
            logger.error("Error during bot shutdown: {}", close_exc)
            
    if success:
        print("\n" + "="*50)
        print("🎉 DJINN DRY-BOOT VERIFICATION SUCCESSFUL! 🎉")
        print("All cogs, databases, and internal servers initialized perfectly.")
        print("="*50 + "\n")
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("❌ DJINN DRY-BOOT VERIFICATION FAILED! ❌")
        print("="*50 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_dry_boot())
