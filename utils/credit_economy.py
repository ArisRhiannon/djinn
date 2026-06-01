"""Credit economy for public Youkai pipeline."""
from __future__ import annotations
import re, time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord
    from .database import Database

# ── Constants ──────────────────────────────────────────────────────────────
COST_WITH_TOOLS = 300
COST_SIMPLE = 100
DAILY_EARN_CAP = 750
DAILY_CALL_CAP = 10

# ── Message quality evaluator (no LLM, pure heuristics) ───────────────────
_LOW_EFFORT = re.compile(
    r"^(x+d+|lol|lmao|jaj[aj]*|kek|f|gg|si|no|ok|ya|va|xd+|bruh|ñ+|a+h*|e+h*|o+h*)\s*[.!?]*$",
    re.IGNORECASE,
)
_EMOJI_ONLY = re.compile(r"^[\s\U0001f000-\U0001ffff\u2600-\u27bf<:>\d_a]+$")
_last_msg: dict[int, float] = {}  # user_id -> timestamp


def evaluate_message(message: "discord.Message") -> int:
    """Return credit reward: 0 (spam), 1 (low), 2 (mid), 3 (high)."""
    text = (message.content or "").strip()
    uid = message.author.id
    now = time.time()

    # Spam: too fast or empty
    if not text or len(text) < 3:
        return 0
    if now - _last_msg.get(uid, 0) < 5:
        _last_msg[uid] = now
        return 0
    _last_msg[uid] = now

    # Low effort
    if _LOW_EFFORT.match(text) or _EMOJI_ONLY.match(text) or len(text) < 20:
        return 1

    # High: >50 chars, multiple words, has substance
    words = set(text.lower().split())
    if len(text) > 50 and len(words) > 5:
        return 3

    return 2


async def can_spend(db: "Database", user_id: int, guild_id: int, cost: int) -> tuple[bool, str, dict]:
    """Check if user can afford a call. Returns (ok, reason, credit_info)."""
    info = await db.get_credits(user_id, guild_id)
    if info["calls_today"] >= DAILY_CALL_CAP:
        return False, "Límite diario de llamadas alcanzado (10/10).", info
    if info["balance"] < cost:
        return False, f"Créditos insuficientes ({info['balance']}/{cost}).", info
    return True, "", info


async def earn_passive(db: "Database", message: "discord.Message") -> int:
    """Award credits for a message. Returns amount earned (0 if capped).
    Server boosters get 2x credits from all sources.
    """
    info = await db.get_credits(message.author.id, message.guild.id)
    if info["earned_today"] >= DAILY_EARN_CAP:
        return 0
    reward = evaluate_message(message)
    if reward <= 0:
        return 0
    # 2x for server boosters
    if getattr(message.author, "premium_since", None) is not None:
        reward *= 2
    # Cap to not exceed daily limit
    reward = min(reward, DAILY_EARN_CAP - info["earned_today"])
    await db.add_credits(message.author.id, message.guild.id, reward, reason="msg", ref="")
    return reward
