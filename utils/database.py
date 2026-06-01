"""
Capa de base de datos — SQLite asíncrono (aiosqlite).

Tablas:
  guild_config, youkai_readers, warnings, mutes, trust_scores,
  youkai_audit, messages, user_cards, automod_immune_roles, user_profiles,
  watched_users, case_notes, user_seals, reaction_roles,
  guild_listeners, listener_trigger_log

Optimizaciones:
  - WAL mode: lecturas concurrentes sin bloquear escrituras.
  - synchronous=NORMAL: fsync solo en checkpoints.
  - cache_size=-32000: 32 MB de caché.
  - Mensajes purgados automáticamente a 30 días (≈20 MB/año para 50 users/día).
"""

from __future__ import annotations
import json
import time
import asyncio
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
import numpy as np
import logging
from utils.chroma_memory import ChromaMemory

logger = logging.getLogger("djinn.database")


def _sanitize_fts5(query: str) -> str:
    """Sanitize a query string for SQLite FTS5 MATCH.

    FTS5 treats commas, parentheses, quotes, and operators (+, -, *, |, AND, OR, NOT, NEAR)
    as special syntax. This function:
    1. Splits the query on commas AND whitespace (each word = a token)
    2. Wraps each non-empty token in double-quotes with * suffix (prefix matching)
    3. Joins with OR for broad matching

    "Linnea genshin impact" → '"Linnea"* OR "genshin"* OR "impact"*'
    "femboys, femboy aesthetic" → '"femboys"* OR "femboy"* OR "aesthetic"*'

    The * suffix enables prefix matching: "Linnea"* matches "Linnea", "Linnean", etc.
    Individual word tokens (not phrases) give much broader recall than full-phrase matching.
    """
    if not query or not query.strip():
        return query
    import re
    # Split on commas first, then split each part on whitespace
    parts = re.split(r'\s*,\s*', query.strip())
    tokens = []
    for part in parts:
        p = part.strip()
        if not p:
            continue
        # Split this part into individual words (space-delimited)
        words = p.split()
        for word in words:
            w = word.strip()
            if not w:
                continue
            # Remove FTS5 special chars from within tokens
            cleaned = re.sub(r'[+\-|*()\"~^!]', ' ', w).strip()
            if cleaned and len(cleaned) >= 2:  # skip single-char tokens
                tokens.append(f'"{cleaned}"*')
    if not tokens:
        return ""
    return " OR ".join(tokens)


def quantize_embedding(embedding_bytes: bytes) -> bytes:
    """Quantize float32 embedding blob to int8 for compact sqlite-vec storage.

    Args:
        embedding_bytes: Raw float32 bytes (384 * 4 = 1536 bytes) or list

    Returns:
        int8 bytes (384 bytes) — 75% smaller
    """
    if isinstance(embedding_bytes, (list, np.ndarray)):
        arr = np.array(embedding_bytes, dtype=np.float32)
    else:
        arr = np.frombuffer(embedding_bytes, dtype=np.float32)
    max_val = np.max(np.abs(arr))
    if max_val == 0:
        max_val = 1.0
    scale = 127.0 / max_val
    quantized = np.clip(np.round(arr * scale), -127, 127).astype(np.int8)
    return quantized.tobytes()


SCHEMA = """
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id          INTEGER PRIMARY KEY,
    audit_ch          INTEGER,
    welcome_ch        INTEGER,
    welcome_msg       TEXT,
    autorole_id       INTEGER,
    automod_on        INTEGER DEFAULT 1,
    tts_role          INTEGER,
    log_actions       INTEGER DEFAULT 1,
    herta_role_id     INTEGER,
    herta_webhook_url TEXT
);

CREATE TABLE IF NOT EXISTS youkai_readers (
    guild_id  INTEGER NOT NULL,
    role_id   INTEGER NOT NULL,
    PRIMARY KEY (guild_id, role_id)
);

CREATE TABLE IF NOT EXISTS warnings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    mod_id     INTEGER NOT NULL,
    reason     TEXT,
    timestamp  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mutes (
    guild_id  INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    mod_id    INTEGER NOT NULL,
    reason    TEXT,
    until     INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS trust_scores (
    guild_id       INTEGER NOT NULL,
    user_id        INTEGER NOT NULL,
    message_count  INTEGER DEFAULT 0,
    join_date      INTEGER NOT NULL,
    last_seen      INTEGER NOT NULL,
    infractions    INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS youkai_audit (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    actor_id   INTEGER,
    action     TEXT    NOT NULL,
    target_id  INTEGER,
    details    TEXT,
    timestamp  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    INTEGER NOT NULL,
    channel_id  INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    username    TEXT    NOT NULL DEFAULT '',
    content     TEXT,
    reply_to_id INTEGER,
    timestamp   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_cards (
    user_id    INTEGER PRIMARY KEY,
    card_json  TEXT    NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS automod_immune_roles (
    guild_id  INTEGER NOT NULL,
    role_id   INTEGER NOT NULL,
    PRIMARY KEY (guild_id, role_id)
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id      INTEGER PRIMARY KEY,
    username     TEXT    NOT NULL,
    display_name TEXT,
    guild_id     INTEGER,
    last_seen    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS watched_users (
    guild_id  INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    reason    TEXT,
    since     INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS case_notes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id  INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    note      TEXT NOT NULL,
    timestamp INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_seals (
    guild_id               INTEGER NOT NULL,
    user_id                INTEGER NOT NULL,
    sealed_role_id         INTEGER NOT NULL,
    seal_channel_id        INTEGER NOT NULL,
    original_role_ids_json TEXT NOT NULL,
    release_at             TEXT NOT NULL,
    reason                 TEXT,
    mod_message_id         INTEGER,
    mod_channel_id         INTEGER,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS reaction_roles (
    guild_id    INTEGER NOT NULL,
    message_id  INTEGER NOT NULL,
    emoji       TEXT NOT NULL,
    role_id     INTEGER NOT NULL,
    PRIMARY KEY (message_id, emoji)
);

CREATE TABLE IF NOT EXISTS guild_listeners (
    id             TEXT    PRIMARY KEY,
    guild_id       INTEGER NOT NULL,
    name           TEXT    NOT NULL,
    description    TEXT,
    rule_json      TEXT    NOT NULL,
    enabled        INTEGER DEFAULT 1,
    created_at     TEXT    NOT NULL,
    created_by     INTEGER,
    trigger_count  INTEGER DEFAULT 0,
    last_triggered TEXT
);

CREATE TABLE IF NOT EXISTS listener_trigger_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER,
    rule_id      TEXT    REFERENCES guild_listeners(id) ON DELETE CASCADE,
    user_id      INTEGER,
    channel_id   INTEGER,
    message_id   INTEGER,
    score        REAL,
    actions_run  TEXT,
    triggered_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_warnings_guild_user   ON warnings(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_trust_guild_user       ON trust_scores(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_audit_guild            ON youkai_audit(guild_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_user_ts       ON messages(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_guild_ts      ON messages(guild_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_guild_chan_ts  ON messages(guild_id, channel_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_profiles_username      ON user_profiles(username);
CREATE INDEX IF NOT EXISTS idx_case_notes_user        ON case_notes(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_listeners_guild        ON guild_listeners(guild_id);
CREATE INDEX IF NOT EXISTS idx_listeners_enabled      ON guild_listeners(guild_id, enabled);
CREATE INDEX IF NOT EXISTS idx_trigger_log_rule       ON listener_trigger_log(rule_id, triggered_at DESC);

-- ── DATA MASTERY: FTS5 + embeddings ──────────────────────────────────────────

-- FTS5 búsqueda full-text (BM25)
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
 content, username,
 content='', contentless_delete=1,
 tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS messages_fts_insert
    AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(rowid, content, username)
        VALUES (new.id, new.content, new.username);
    END;

CREATE TRIGGER IF NOT EXISTS messages_fts_delete
    BEFORE DELETE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content, username)
        VALUES ('delete', old.id, old.content, old.username);
    END;

CREATE TRIGGER IF NOT EXISTS messages_fts_update
    AFTER UPDATE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content, username)
        VALUES ('delete', old.id, old.content, old.username);
        INSERT INTO messages_fts(rowid, content, username)
        VALUES (new.id, new.content, new.username);
    END;

-- Embeddings para búsqueda semántica (sqlite-vec) — stored exclusively in vec_messages

-- Entities y aliases para Youkai Nexus (grafo de identidades)
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT,
    type TEXT,
    canonical_name TEXT,
    guild_id INTEGER,
    PRIMARY KEY (entity_id, guild_id)
);
CREATE TABLE IF NOT EXISTS aliases (
    alias TEXT,
    entity_id TEXT,
    guild_id INTEGER,
    weight INTEGER DEFAULT 1,
    PRIMARY KEY (alias, entity_id, guild_id)
);
CREATE INDEX IF NOT EXISTS idx_aliases_guild ON aliases(guild_id, alias);

-- ── Maldiciones (Curse Tool) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS curses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id            INTEGER NOT NULL,
    user_id             INTEGER NOT NULL,
    started_at          TEXT    NOT NULL,
    release_at          TEXT    NOT NULL,
    reason              TEXT,
    original_display_name TEXT,
    created_by          INTEGER,
    UNIQUE(guild_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_curses_guild  ON curses(guild_id);
CREATE INDEX IF NOT EXISTS idx_curses_user   ON curses(user_id);
CREATE INDEX IF NOT EXISTS idx_curses_release ON curses(release_at);

-- ── Lavado de Boca (Mouth Wash Tool) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS mouth_washes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    started_at   TEXT NOT NULL,
    release_at   TEXT NOT NULL,
    reason       TEXT,
    display_name TEXT,
    created_by   INTEGER,
    UNIQUE(guild_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_mw_guild ON mouth_washes(guild_id);
CREATE INDEX IF NOT EXISTS idx_mw_user ON mouth_washes(user_id);
CREATE INDEX IF NOT EXISTS idx_mw_release ON mouth_washes(release_at);

CREATE TABLE IF NOT EXISTS user_credits (
    user_id       INTEGER NOT NULL,
    guild_id      INTEGER NOT NULL,
    balance       INTEGER NOT NULL DEFAULT 0,
    earned_today  INTEGER NOT NULL DEFAULT 0,
    spent_today   INTEGER NOT NULL DEFAULT 0,
    calls_today   INTEGER NOT NULL DEFAULT 0,
    last_reset    TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, guild_id)
);

CREATE TABLE IF NOT EXISTS loan_scores (
    user_id         INTEGER NOT NULL,
    guild_id        INTEGER NOT NULL,
    score           INTEGER NOT NULL DEFAULT 500,
    total_loans     INTEGER NOT NULL DEFAULT 0,
    paid_on_time    INTEGER NOT NULL DEFAULT 0,
    missed_payments INTEGER NOT NULL DEFAULT 0,
    defaults_count  INTEGER NOT NULL DEFAULT 0,
    blacklisted     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, guild_id)
);

CREATE TABLE IF NOT EXISTS loans (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    guild_id            INTEGER NOT NULL,
    channel_id          INTEGER NOT NULL,
    principal           INTEGER NOT NULL,
    interest_rate       REAL NOT NULL,
    total_owed          INTEGER NOT NULL,
    installment_amt     INTEGER NOT NULL,
    num_installments    INTEGER NOT NULL,
    paid_installments   INTEGER NOT NULL DEFAULT 0,
    missed_installments INTEGER NOT NULL DEFAULT 0,
    consecutive_misses  INTEGER NOT NULL DEFAULT 0,
    remaining_debt      INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active',
    created_at          TEXT NOT NULL,
    next_collection     TEXT NOT NULL,
    completed_at        TEXT,
    accrued_late_fees   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_loans_active ON loans(status, next_collection);
CREATE INDEX IF NOT EXISTS idx_loans_user ON loans(user_id, guild_id, status);

CREATE TABLE IF NOT EXISTS loan_payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id         INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    guild_id        INTEGER NOT NULL,
    amount_due      INTEGER NOT NULL,
    amount_paid     INTEGER NOT NULL,
    success         INTEGER NOT NULL,
    balance_before  INTEGER NOT NULL,
    balance_after   INTEGER NOT NULL,
    collected_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lp_loan ON loan_payments(loan_id);

CREATE TABLE IF NOT EXISTS aware_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        INTEGER NOT NULL,
    channel_id      INTEGER NOT NULL,
    cycles_total    INTEGER NOT NULL DEFAULT 10,
    cycles_used     INTEGER NOT NULL DEFAULT 0,
    active          INTEGER NOT NULL DEFAULT 1,
    tool_results    TEXT NOT NULL DEFAULT '[]',
    youkai_responses TEXT NOT NULL DEFAULT '[]',
    last_message_id INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_aware_active ON aware_sessions(channel_id, active);

CREATE TABLE IF NOT EXISTS guild_treasury (
    guild_id              INTEGER PRIMARY KEY,
    balance               INTEGER NOT NULL DEFAULT 0,
    total_collected       INTEGER NOT NULL DEFAULT 0,
    total_disbursed       INTEGER NOT NULL DEFAULT 0,
    total_lost_defaults   INTEGER NOT NULL DEFAULT 0,
    bootstrap_amount      INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL,
    last_modified         TEXT NOT NULL,
    total_shares          INTEGER NOT NULL DEFAULT 0,
    total_dividends_paid  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS guild_treasury_movements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    amount       INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    reason       TEXT NOT NULL,
    metadata     TEXT,
    user_id      INTEGER,
    by_staff_id  INTEGER,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_treasury_movements_guild ON guild_treasury_movements(guild_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_treasury_movements_reason ON guild_treasury_movements(guild_id, reason);

CREATE TABLE IF NOT EXISTS treasury_shares (
    user_id             INTEGER NOT NULL,
    guild_id            INTEGER NOT NULL,
    shares              INTEGER NOT NULL DEFAULT 0,
    unclaimed_dividends REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (user_id, guild_id)
);

CREATE TABLE IF NOT EXISTS credit_ledger (
    ts       INTEGER NOT NULL,
    uid      INTEGER NOT NULL,
    gid      INTEGER NOT NULL,
    delta    INTEGER NOT NULL,
    bal      INTEGER NOT NULL,
    reason   TEXT NOT NULL,
    ref      TEXT,
    hash     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ledger_user ON credit_ledger(uid, ts DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_guild ON credit_ledger(gid, ts DESC);

"""

_PRAGMAS = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-32000;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=30000;
"""


_GUILD_CONFIG_COLUMNS = frozenset({
    "audit_ch", "welcome_ch", "welcome_msg", "autorole_id", "automod_on",
    "tts_role", "log_actions", "herta_role_id", "herta_webhook_url",
    "moroso_ch", "moroso_role_id",
    "zzz_calendar_ch", "zzz_calendar_msg_id",
    "birthday_ch", "mod_channel"
})


class Database:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._db: Optional[aiosqlite.Connection] = None
        self.write_lock = asyncio.Lock()
        self._vec_available = False
        self.chroma_memory = ChromaMemory()

    @staticmethod
    def _like_escape(value: str) -> str:
        """Escapa caracteres especiales de LIKE (% y _) para uso seguro."""
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    async def _safe_commit(self, max_retries: int = 3) -> None:
        """Commit con retry para 'database is locked' transitorio."""
        for attempt in range(max_retries):
            try:
                await self._db.commit()
                return
            except aiosqlite.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                raise

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self.path, timeout=30)
        self._db.row_factory = aiosqlite.Row
        for pragma in _PRAGMAS.strip().splitlines():
            pragma = pragma.strip()
            if pragma:
                await self._db.execute(pragma)
        # Fallback for older SQLite versions that don't support contentless_delete (introduced in 3.38.0)
        schema_to_run = SCHEMA
        async with self._db.execute("SELECT sqlite_version()") as cur:
            row = await cur.fetchone()
            if row:
                try:
                    sqlite_ver = tuple(map(int, row[0].split(".")))
                    if sqlite_ver < (3, 38, 0):
                        schema_to_run = schema_to_run.replace(", contentless_delete=1", "")
                except Exception:
                    pass
        await self._db.executescript(schema_to_run)

        # ── Sistema de migraciones con PRAGMA user_version ─────────────
        await self._run_migrations()

        # Inicializar ChromaDB para búsqueda semántica
        try:
            self.chroma_memory.initialize()
            self._vec_available = True
        except Exception as exc:
            logger.exception("Error al inicializar ChromaMemory en Database: %s", exc)
            self._vec_available = False

        await self._safe_commit()

    # ── Migraciones incrementales ──────────────────────────────────────────

    _MIGRATIONS = [
        # v1: columnas legacy (ya existentes en la mayoría de instancias)
        [
            "ALTER TABLE guild_config ADD COLUMN herta_role_id INTEGER",
            "ALTER TABLE guild_config ADD COLUMN herta_webhook_url TEXT",
            "ALTER TABLE messages ADD COLUMN username TEXT NOT NULL DEFAULT ''",
        ],
        # v2: token tracking
        [
            """CREATE TABLE IF NOT EXISTS token_usage (
                guild_id   INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                date       TEXT NOT NULL,
                tokens_in  INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                calls      INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, date)
            )""",
        ],
        # v3: moroso shaming system
        [
            "ALTER TABLE guild_config ADD COLUMN moroso_ch INTEGER",
            "ALTER TABLE guild_config ADD COLUMN moroso_role_id INTEGER",
        ],
        # v4: ZZZ event calendar
        [
            "ALTER TABLE guild_config ADD COLUMN zzz_calendar_ch INTEGER",
            "ALTER TABLE guild_config ADD COLUMN zzz_calendar_msg_id INTEGER",
        ],
        # v5: Knowledge base (interactive RAG)
        [
            """CREATE TABLE IF NOT EXISTS knowledge_base (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                key         TEXT NOT NULL,
                content     TEXT NOT NULL,
                tags        TEXT DEFAULT '',
                scope       TEXT DEFAULT 'guild',
                author_id   INTEGER DEFAULT 0,
                embedding   BLOB,
                created_at  INTEGER NOT NULL,
                updated_at  INTEGER NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_kb_guild ON knowledge_base(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_kb_key ON knowledge_base(guild_id, key)",
            "CREATE INDEX IF NOT EXISTS idx_kb_tags ON knowledge_base(tags)",
        ],
        # v6: Birthdays
        [
            """CREATE TABLE IF NOT EXISTS birthdays (
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                day         INTEGER NOT NULL,
                month       INTEGER NOT NULL,
                name        TEXT DEFAULT '',
                PRIMARY KEY (guild_id, user_id)
            )""",
            "ALTER TABLE guild_config ADD COLUMN birthday_ch INTEGER",
        ],
        # v7: Shop / Redeemables
        [
            """CREATE TABLE IF NOT EXISTS shop_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                price       INTEGER NOT NULL,
                type        TEXT NOT NULL DEFAULT 'role',
                category    TEXT DEFAULT '',
                payload     TEXT DEFAULT '{}',
                stock       INTEGER DEFAULT -1,
                duration_hours INTEGER DEFAULT 0,
                redeemed_count INTEGER DEFAULT 0,
                active      INTEGER DEFAULT 1,
                created_by  INTEGER DEFAULT 0,
                created_at  TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_shop_guild ON shop_items(guild_id, active)",
            """CREATE TABLE IF NOT EXISTS redemptions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                item_id     INTEGER NOT NULL,
                redeemed_at TEXT NOT NULL,
                expires_at  TEXT
            )""",
            "CREATE INDEX IF NOT EXISTS idx_redemptions_user ON redemptions(guild_id, user_id)",
            "CREATE INDEX IF NOT EXISTS idx_redemptions_expires ON redemptions(expires_at)",
        ],
        # v8: Conscious mode — mod channel
        [
            "ALTER TABLE guild_config ADD COLUMN mod_channel INTEGER",
        ],
        # v9: Sistema de economía — creación de la tabla credit_ledger omitida anteriormente
        [
            """CREATE TABLE IF NOT EXISTS credit_ledger (
                ts       INTEGER NOT NULL,
                uid      INTEGER NOT NULL,
                gid      INTEGER NOT NULL,
                delta    INTEGER NOT NULL,
                bal      INTEGER NOT NULL,
                reason   TEXT NOT NULL,
                ref      TEXT,
                hash     TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_ledger_user ON credit_ledger(uid, ts DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ledger_guild ON credit_ledger(gid, ts DESC)",
        ],
        # v10: Sistema de economía avanzado - recargos de mora e inversiones/dividendos
        [
            "ALTER TABLE loans ADD COLUMN accrued_late_fees INTEGER NOT NULL DEFAULT 0",
            """CREATE TABLE IF NOT EXISTS treasury_shares (
                user_id             INTEGER NOT NULL,
                guild_id            INTEGER NOT NULL,
                shares              INTEGER NOT NULL DEFAULT 0,
                unclaimed_dividends REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (user_id, guild_id)
            )""",
            "ALTER TABLE guild_treasury ADD COLUMN total_shares INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE guild_treasury ADD COLUMN total_dividends_paid INTEGER NOT NULL DEFAULT 0",
        ],
        # v11: Registro de ejecución de premios de actividad mensual
        [
            """CREATE TABLE IF NOT EXISTS active_award_runs (
                guild_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                run_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, year, month)
            )"""
        ],
        # v12: Persistencia de roles de los miembros
        [
            """CREATE TABLE IF NOT EXISTS member_roles_persistence (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role_ids TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )"""
        ],
        # v13: Contadores de acciones de rol interactivo (hug, kiss, pat, heal)
        [
            """CREATE TABLE IF NOT EXISTS user_action_counters (
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                count       INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, action_type)
            )"""
        ],
    ]

    async def _run_migrations(self) -> None:
        """Ejecuta migraciones incrementales usando PRAGMA user_version."""
        cursor = await self._db.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        current_version = row[0] if row else 0

        for version, statements in enumerate(self._MIGRATIONS, start=1):
            if current_version >= version:
                continue
            for sql in statements:
                try:
                    await self._db.execute(sql)
                except aiosqlite.OperationalError:
                    pass  # columna/tabla ya existe
            await self._db.execute(f"PRAGMA user_version = {version}")
            await self._safe_commit()

    # ── Guild config ───────────────────────────────────────────────────────

    async def init_guild(self, guild_id: int) -> None:
        async with self.write_lock:
            await self._db.execute(
                "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,)
            )
            await self._safe_commit()

    async def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        await self.init_guild(guild_id)
        async with self._db.execute(
            "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else {}

    async def set_guild_config(self, guild_id: int, **kwargs: Any) -> None:
        await self.init_guild(guild_id)
        for k in kwargs:
            if k not in _GUILD_CONFIG_COLUMNS:
                raise ValueError(f"Invalid guild_config column: {k}")
        async with self.write_lock:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [guild_id]
            await self._db.execute(f"UPDATE guild_config SET {sets} WHERE guild_id = ?", vals)
            await self._safe_commit()

    # ── Fairy readers ──────────────────────────────────────────────────────

    async def add_youkai_reader(self, guild_id: int, role_id: int) -> None:
        async with self.write_lock:
            await self._db.execute(
                "INSERT OR IGNORE INTO youkai_readers (guild_id, role_id) VALUES (?, ?)",
                (guild_id, role_id),
            )
            await self._safe_commit()

    async def remove_youkai_reader(self, guild_id: int, role_id: int) -> None:
        async with self.write_lock:
            await self._db.execute(
                "DELETE FROM youkai_readers WHERE guild_id = ? AND role_id = ?",
                (guild_id, role_id),
            )
            await self._safe_commit()

    async def get_youkai_readers(self, guild_id: int) -> List[int]:
        async with self._db.execute(
            "SELECT role_id FROM youkai_readers WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return [r["role_id"] for r in await cur.fetchall()]

    # ── Warnings ───────────────────────────────────────────────────────────

    async def add_warning(self, guild_id: int, user_id: int, mod_id: int, reason: str) -> int:
        async with self.write_lock:
            await self._db.execute(
                "INSERT INTO warnings (guild_id, user_id, mod_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, mod_id, reason, int(time.time())),
            )
            await self._safe_commit()
            return await self.count_warnings(guild_id, user_id)

    async def count_warnings(self, guild_id: int, user_id: int) -> int:
        async with self._db.execute(
            "SELECT COUNT(*) AS c FROM warnings WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            return row["c"] if row else 0

    async def get_warnings(self, guild_id: int, user_id: int) -> List[Dict]:
        async with self._db.execute(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC LIMIT 20",
            (guild_id, user_id),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def clear_warnings(self, guild_id: int, user_id: int) -> None:
        async with self.write_lock:
            await self._db.execute(
                "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
            )
            await self._safe_commit()

    # ── Trust scores & Leaderboard ─────────────────────────────────────────

    async def upsert_trust(self, guild_id: int, user_id: int, join_ts: int) -> None:
        now = int(time.time())
        async with self.write_lock:
            await self._db.execute(
                """INSERT INTO trust_scores (guild_id, user_id, message_count, join_date, last_seen)
                   VALUES (?, ?, 1, ?, ?)
                   ON CONFLICT(guild_id, user_id) DO UPDATE SET
                     message_count = message_count + 1,
                     last_seen     = excluded.last_seen""",
                (guild_id, user_id, join_ts, now),
            )
            await self._safe_commit()

    async def get_trust(self, guild_id: int, user_id: int) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM trust_scores WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def add_infraction(self, guild_id: int, user_id: int) -> None:
        async with self.write_lock:
            await self._db.execute(
                "UPDATE trust_scores SET infractions = infractions + 1 WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await self._safe_commit()

    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Obtiene el top histórico de usuarios basado en trust_scores."""
        async with self._db.execute(
            """SELECT t.user_id, t.message_count,
                      COALESCE(p.display_name, p.username, CAST(t.user_id AS TEXT)) AS display_name
               FROM trust_scores t
               LEFT JOIN user_profiles p ON t.user_id = p.user_id
               WHERE t.guild_id = ?
               ORDER BY t.message_count DESC LIMIT ?""",
            (guild_id, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    # ── Audit log y Moderación Avanzada ────────────────────────────────────

    async def log_action(
        self,
        guild_id: int,
        action: str,
        actor_id: Optional[int] = None,
        target_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> None:
        async with self.write_lock:
            await self._db.execute(
                "INSERT INTO youkai_audit (guild_id, actor_id, action, target_id, details, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (guild_id, actor_id, action, target_id, json.dumps(details or {}), int(time.time())),
            )
            await self._safe_commit()

    async def get_infractions_summary(self, guild_id: int, hours: int) -> Dict:
        """Obtiene un resumen de baneos, kicks y timeouts usando el audit log interno."""
        since = int(time.time()) - (hours * 3600)
        async with self._db.execute(
            "SELECT action, COUNT(*) as count FROM youkai_audit WHERE guild_id = ? AND timestamp > ? GROUP BY action",
            (guild_id, since)
        ) as cur:
            rows = await cur.fetchall()

        breakdown = {r["action"]: r["count"] for r in rows}
        bans  = breakdown.get("ban", 0) + breakdown.get("softban", 0)
        kicks = breakdown.get("kick", 0)
        mutes = breakdown.get("mute", 0) + breakdown.get("mass_timeout", 0)
        total = sum(breakdown.values())

        return {
            "bans": bans,
            "kicks": kicks,
            "mutes": mutes,
            "total_actions": total,
            "breakdown": breakdown,
        }

    # ── Messages ───────────────────────────────────────────────────────────

    async def save_message(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        username: str,
        content: str,
        reply_to_id: Optional[int] = None,
    ) -> None:
        async with self.write_lock:
            await self._db.execute(
                "INSERT INTO messages (guild_id, channel_id, user_id, username, content, reply_to_id, timestamp)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (guild_id, channel_id, user_id, username, content, reply_to_id, int(time.time())),
            )
            await self._safe_commit()

    async def get_user_messages(self, user_id: int, since: int, limit: int = 100) -> List[Dict]:
        """Mensajes de un usuario desde `since` con nombre resuelto."""
        async with self._db.execute(
            """SELECT m.content, m.reply_to_id, m.timestamp,
                      COALESCE(NULLIF(m.username,''), p.username, p.display_name, CAST(m.user_id AS TEXT)) AS username
               FROM messages m
               LEFT JOIN user_profiles p ON p.user_id = m.user_id
               WHERE m.user_id = ? AND m.timestamp > ?
               ORDER BY m.timestamp ASC LIMIT ?""",
            (user_id, since, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def get_all_messages_since(
        self, since: int, limit: int = 500, guild_id: Optional[int] = None
    ) -> List[Dict]:
        """Todos los mensajes desde `since` con nombre resuelto."""
        if guild_id is not None:
            async with self._db.execute(
                """SELECT m.channel_id, m.user_id, m.content, m.reply_to_id, m.timestamp,
                          COALESCE(NULLIF(m.username,''), p.username, p.display_name, CAST(m.user_id AS TEXT)) AS username
                   FROM messages m
                   LEFT JOIN user_profiles p ON p.user_id = m.user_id
                   WHERE m.timestamp > ? AND m.guild_id = ?
                   ORDER BY m.timestamp ASC LIMIT ?""",
                (since, guild_id, limit),
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]
        else:
            async with self._db.execute(
                """SELECT m.channel_id, m.user_id, m.content, m.reply_to_id, m.timestamp,
                          COALESCE(NULLIF(m.username,''), p.username, p.display_name, CAST(m.user_id AS TEXT)) AS username
                   FROM messages m
                   LEFT JOIN user_profiles p ON p.user_id = m.user_id
                   WHERE m.timestamp > ?
                   ORDER BY m.timestamp ASC LIMIT ?""",
                (since, limit),
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def search_messages(
        self,
        guild_id: int,
        keyword: Optional[str] = None,
        user_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        hours: int = 72,
        limit: int = 25,
    ) -> List[Dict]:
        """Búsqueda de mensajes con nombre resuelto. Filtros opcionales."""
        since = int(time.time()) - hours * 3600
        clauses = ["m.guild_id = ?", "m.timestamp > ?"]
        params: List[Any] = [guild_id, since]

        if user_id is not None:
            clauses.append("m.user_id = ?")
            params.append(user_id)
        if channel_id is not None:
            clauses.append("m.channel_id = ?")
            params.append(channel_id)
        if keyword:
            escaped = self._like_escape(keyword)
            clauses.append("m.content LIKE ? ESCAPE '\\'")
            params.append(f"%{escaped}%")

        where = " AND ".join(clauses)
        params.append(limit)

        async with self._db.execute(
            f"""SELECT m.id, m.user_id, m.channel_id, m.content, m.timestamp,
                       COALESCE(NULLIF(m.username,''), p.username, p.display_name, CAST(m.user_id AS TEXT)) AS username
                FROM messages m
                LEFT JOIN user_profiles p ON p.user_id = m.user_id
                WHERE {where}
                ORDER BY m.timestamp DESC LIMIT ?""",
            params,
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def count_search_messages(
        self,
        guild_id: int,
        keyword: str,
        user_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        hours: int = 72,
    ) -> int:
        """Cuenta total de mensajes que matchean (sin límite)."""
        since = int(time.time()) - hours * 3600
        clauses = ["guild_id = ?", "timestamp > ?"]
        params: List[Any] = [guild_id, since]
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if channel_id is not None:
            clauses.append("channel_id = ?")
            params.append(channel_id)
        escaped = self._like_escape(keyword)
        clauses.append("content LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")
        where = " AND ".join(clauses)
        async with self._db.execute(
            f"SELECT COUNT(*) as c FROM messages WHERE {where}", params
        ) as cur:
            row = await cur.fetchone()
            return row["c"] if row else 0

    async def get_server_activity(
        self, guild_id: int, hours: int = 24, limit: int = 15
    ) -> List[Dict]:
        """Usuarios más activos en las últimas N horas con nombre resuelto."""
        since = int(time.time()) - hours * 3600
        async with self._db.execute(
            """SELECT m.user_id,
                      COALESCE(p.display_name, p.username, CAST(m.user_id AS TEXT)) AS display_name,
                      COUNT(*) AS message_count,
                      MAX(m.timestamp) AS last_message
               FROM messages m
               LEFT JOIN user_profiles p ON p.user_id = m.user_id
               WHERE m.guild_id = ? AND m.timestamp > ?
               GROUP BY m.user_id
               ORDER BY message_count DESC LIMIT ?""",
            (guild_id, since, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def get_active_user_ids(self, guild_id: int, hours: int) -> List[int]:
        """Devuelve los IDs de usuarios activos en las últimas N horas."""
        since = int(time.time()) - (hours * 3600)
        async with self._db.execute(
            "SELECT DISTINCT user_id FROM messages WHERE guild_id = ? AND timestamp > ?",
            (guild_id, since)
        ) as cur:
            return [r["user_id"] for r in await cur.fetchall()]

    async def get_user_all_messages(
        self, guild_id: int, user_id: int, limit: int = 600
    ) -> List[Dict]:
        """Todos los mensajes de un usuario en un guild, ordenados por timestamp.
        Usado por el Destilador para perfilar personalidades."""
        async with self._db.execute(
            """SELECT m.content, m.timestamp, m.channel_id,
            COALESCE(NULLIF(m.username,''), p.username, p.display_name, CAST(m.user_id AS TEXT)) AS username
            FROM messages m
            LEFT JOIN user_profiles p ON p.user_id = m.user_id
            WHERE m.guild_id = ? AND m.user_id = ?
            ORDER BY m.timestamp ASC LIMIT ?""",
            (guild_id, user_id, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def get_guild_member_ids(self, guild_id: int, min_messages: int = 10) -> List[int]:
        """IDs de usuarios con al menos N mensajes en el guild (para destilación)."""
        async with self._db.execute(
            """SELECT user_id FROM messages
            WHERE guild_id = ?
            GROUP BY user_id
            HAVING COUNT(*) >= ?
            ORDER BY COUNT(*) DESC""",
            (guild_id, min_messages),
        ) as cur:
            return [r["user_id"] for r in await cur.fetchall()]

    async def prune_old_messages(self, days: int = 30) -> int:
        """Elimina mensajes más viejos de `days` días. Llamar diariamente."""
        cutoff = int(time.time()) - days * 86400
        async with self.write_lock:
            # Embeddings are managed by tiered archival (db_maintenance cog),
            # NOT deleted here. Only orphaned rows are cleaned up.
            if self._vec_available:
                try:
                    await self._db.execute(
                        "DELETE FROM vec_messages WHERE rowid NOT IN (SELECT id FROM messages)"
                    )
                    await self._db.execute(
                        "DELETE FROM vec_messages_archive WHERE rowid NOT IN (SELECT id FROM messages)"
                    )
                except Exception:
                    pass

            async with self._db.execute(
                "DELETE FROM messages WHERE timestamp < ?", (cutoff,)
            ) as cur:
                deleted = cur.rowcount or 0

            # Orphan cleanup already done above for both vec tables

            audit_cutoff = int(time.time()) - 90 * 86400
            await self._db.execute("DELETE FROM youkai_audit WHERE timestamp < ?", (audit_cutoff,))
            # Prune listener trigger log with the same cutoff as messages
            await self._db.execute("DELETE FROM listener_trigger_log WHERE triggered_at < ?", (cutoff,))
            # Prune low-weight aliases (keep top 10 per entity)
            await self._db.execute("""
                DELETE FROM aliases WHERE rowid IN (
                    SELECT a1.rowid FROM aliases a1
                    WHERE (SELECT COUNT(*) FROM aliases a2
                    WHERE a2.entity_id = a1.entity_id AND a2.weight > a1.weight) >= 10
                )
            """)
            await self._safe_commit()

        # Reclaim freed pages to OS
        try:
            await self._db.execute("PRAGMA incremental_vacuum")
        except Exception:
            pass  # Not critical, may fail if auto_vacuum not set

        return deleted

    # ── User profiles ──────────────────────────────────────────────────────

    async def upsert_user_profile(
        self,
        user_id: int,
        username: str,
        display_name: Optional[str] = None,
        guild_id: Optional[int] = None,
    ) -> None:
        """Registra o actualiza perfil. Llamar en cada mensaje entrante."""
        async with self.write_lock:
            await self._db.execute(
                """INSERT INTO user_profiles (user_id, username, display_name, guild_id, last_seen)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       username     = excluded.username,
                       display_name = excluded.display_name,
                       guild_id     = COALESCE(excluded.guild_id, guild_id),
                       last_seen    = excluded.last_seen""",
                (user_id, username, display_name, guild_id, int(time.time())),
            )
            await self._safe_commit()

    async def get_user_profile(self, user_id: int) -> Optional[Dict]:
        """Perfil guardado de un usuario o None si no existe."""
        async with self._db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def search_users_by_name(
        self, name: str, guild_id: Optional[int] = None
    ) -> List[Dict]:
        """Busca usuarios por nombre parcial. Devuelve perfil + card JSON."""
        escaped = self._like_escape(name)
        pattern = f"%{escaped}%"
        if guild_id is not None:
            async with self._db.execute(
                """SELECT p.user_id, p.username, p.display_name, p.last_seen, c.card_json
                FROM user_profiles p
                LEFT JOIN user_cards c ON c.user_id = p.user_id
                WHERE (p.username LIKE ? ESCAPE '\\' OR p.display_name LIKE ? ESCAPE '\\') AND p.guild_id = ?
                ORDER BY p.last_seen DESC LIMIT 10""",
                (pattern, pattern, guild_id),
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]
        else:
            async with self._db.execute(
                """SELECT p.user_id, p.username, p.display_name, p.last_seen, c.card_json
                FROM user_profiles p
                LEFT JOIN user_cards c ON c.user_id = p.user_id
                WHERE p.username LIKE ? ESCAPE '\\' OR p.display_name LIKE ? ESCAPE '\\'
                ORDER BY p.last_seen DESC LIMIT 10""",
                (pattern, pattern),
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ── Character Cards ────────────────────────────────────────────────────

    async def get_card(self, user_id: int) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM user_cards WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                data = dict(row)
                try:
                    data["card_json"] = json.loads(data["card_json"])
                except json.JSONDecodeError:
                    data["card_json"] = {}
                return data
            return None

    async def upsert_card(self, user_id: int, card_data: Dict) -> None:
        async with self.write_lock:
            await self._db.execute(
                "INSERT OR REPLACE INTO user_cards (user_id, card_json, updated_at) VALUES (?, ?, ?)",
                (user_id, json.dumps(card_data), int(time.time())),
            )
            await self._safe_commit()

    # ── Automod immune roles ───────────────────────────────────────────────

    async def add_immune_role(self, guild_id: int, role_id: int) -> None:
        async with self.write_lock:
            await self._db.execute(
                "INSERT OR IGNORE INTO automod_immune_roles (guild_id, role_id) VALUES (?, ?)",
                (guild_id, role_id),
            )
            await self._safe_commit()

    async def remove_immune_role(self, guild_id: int, role_id: int) -> None:
        async with self.write_lock:
            await self._db.execute(
                "DELETE FROM automod_immune_roles WHERE guild_id = ? AND role_id = ?",
                (guild_id, role_id),
            )
            await self._safe_commit()

    async def get_immune_roles(self, guild_id: int) -> List[int]:
        async with self._db.execute(
            "SELECT role_id FROM automod_immune_roles WHERE guild_id = ?", (guild_id,)
        ) as cur:
            return [r["role_id"] for r in await cur.fetchall()]

    async def get_all_immune_roles(self) -> List[Dict]:
        """Todas las entradas de automod_immune_roles (para carga inicial de cogs)."""
        async with self._db.execute(
            "SELECT guild_id, role_id FROM automod_immune_roles"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def get_all_cards(self) -> List[Dict]:
        """Todas las user_cards (para ranking/top)."""
        async with self._db.execute(
            "SELECT user_id, card_json FROM user_cards"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def batch_insert_messages(self, messages: List[Dict]) -> None:
        """Inserta lote de mensajes + upsert perfiles en una transaccion.

        Cada dict: {guild_id, channel_id, user_id, username, display_name,
                    content, reply_to_id, timestamp}
        """
        if not messages:
            return
        async with self.write_lock:
            await self._db.executemany(
                "INSERT INTO messages "
                "(guild_id, channel_id, user_id, username, content, reply_to_id, timestamp, attachments)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(m["guild_id"], m["channel_id"], m["user_id"],
                  m["username"], m["content"], m["reply_to_id"],
                  m["timestamp"], m.get("attachments")) for m in messages],
            )
            seen = {}
            for m in messages:
                seen[m["user_id"]] = m
            for m in seen.values():
                await self._db.execute(
                    """INSERT INTO user_profiles
                    (user_id, username, display_name, guild_id, last_seen)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    display_name = excluded.display_name,
                    guild_id = COALESCE(excluded.guild_id, guild_id),
                    last_seen = excluded.last_seen""",
                    (m["user_id"], m["username"],
                     m.get("display_name"), m["guild_id"], m["timestamp"]),
                )
            await self._safe_commit()

    async def find_message_id(self, user_id: int, channel_id: int, timestamp: int) -> Optional[int]:
        """Busca el ID de un mensaje por usuario, canal y timestamp exacto."""
        async with self._db.execute(
            "SELECT id FROM messages "
            "WHERE user_id = ? AND channel_id = ? AND timestamp = ? "
            "LIMIT 1",
            (user_id, channel_id, timestamp),
        ) as cur:
            row = await cur.fetchone()
            return row["id"] if row else None

    # ── Vigilancia (Watch) y Notas de caso ─────────────────────────────────

    async def set_watch(self, guild_id: int, user_id: int, active: bool, reason: str = "") -> None:
        async with self.write_lock:
            if active:
                await self._db.execute(
                    "INSERT OR REPLACE INTO watched_users (guild_id, user_id, reason, since) VALUES (?, ?, ?, ?)",
                    (guild_id, user_id, reason, int(time.time()))
                )
            else:
                await self._db.execute(
                    "DELETE FROM watched_users WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id)
                )
            await self._safe_commit()

    async def get_watched_users(self, guild_id: int) -> List[Dict]:
        async with self._db.execute(
            """SELECT w.*, COALESCE(p.username, CAST(w.user_id AS TEXT)) as username
               FROM watched_users w
               LEFT JOIN user_profiles p ON w.user_id = p.user_id
               WHERE w.guild_id = ?""",
            (guild_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def add_case_note(self, guild_id: int, user_id: int, note: str) -> None:
        async with self.write_lock:
            await self._db.execute(
                "INSERT INTO case_notes (guild_id, user_id, note, timestamp) VALUES (?, ?, ?, ?)",
                (guild_id, user_id, note, int(time.time()))
            )
            await self._safe_commit()

    async def get_case_notes(self, guild_id: int, user_id: int) -> List[Dict]:
        async with self._db.execute(
            "SELECT note, timestamp FROM case_notes WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
            (guild_id, user_id)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    # ── Roles por Reacción (Reaction Roles) ────────────────────────────────

    async def add_reaction_role(self, guild_id: int, message_id: int, emoji: str, role_id: int) -> None:
        async with self.write_lock:
            await self._db.execute(
                "INSERT OR REPLACE INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)",
                (guild_id, message_id, emoji, role_id)
            )
            await self._safe_commit()

    # ── Sellos (Seals) ─────────────────────────────────────────────────────

    async def store_seal(
        self,
        guild_id: int,
        user_id: int,
        sealed_role_id: int,
        seal_channel_id: int,
        original_role_ids: list,
        release_at: str,
        reason: str,
    ) -> None:
        roles_json = json.dumps(original_role_ids)
        async with self.write_lock:
            await self._db.execute(
                """INSERT OR REPLACE INTO user_seals
                   (guild_id, user_id, sealed_role_id, seal_channel_id, original_role_ids_json, release_at, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (guild_id, user_id, sealed_role_id, seal_channel_id, roles_json, release_at, reason)
            )
            await self._safe_commit()

    async def update_seal_mod_message(
        self, guild_id: int, user_id: int, mod_message_id: int, mod_channel_id: int
    ) -> None:
        async with self.write_lock:
            await self._db.execute(
                "UPDATE user_seals SET mod_message_id = ?, mod_channel_id = ? WHERE guild_id = ? AND user_id = ?",
                (mod_message_id, mod_channel_id, guild_id, user_id)
            )
            await self._safe_commit()

    async def get_seal(self, guild_id: int, user_id: int) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM user_seals WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ) as cur:
            row = await cur.fetchone()
            if row:
                data = dict(row)
                try:
                    data["original_role_ids"] = json.loads(data.get("original_role_ids_json", "[]"))
                except json.JSONDecodeError:
                    data["original_role_ids"] = []
                return data
            return None

    async def get_seal_by_mod_message(self, guild_id: int, message_id: int) -> Optional[Dict]:
        """Recupera el sello usando el ID del mensaje de los mods."""
        async with self._db.execute(
            "SELECT * FROM user_seals WHERE guild_id = ? AND mod_message_id = ?",
            (guild_id, message_id)
        ) as cur:
            row = await cur.fetchone()
            if row:
                data = dict(row)
                try:
                    data["original_role_ids"] = json.loads(data.get("original_role_ids_json", "[]"))
                except json.JSONDecodeError:
                    data["original_role_ids"] = []
                return data
            return None

    async def remove_seal(self, guild_id: int, user_id: int) -> None:
        async with self.write_lock:
            await self._db.execute(
                "DELETE FROM user_seals WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            await self._safe_commit()

    # ── Listeners ──────────────────────────────────────────────────────────

    async def save_listener(self, guild_id: int, rule: dict) -> None:
        """Guarda o reemplaza una regla completa. rule debe tener 'id'."""
        rule_copy = dict(rule)
        rule_copy.setdefault("created_at", datetime.datetime.utcnow().isoformat())
        async with self.write_lock:
            await self._db.execute(
                """INSERT INTO guild_listeners
                       (id, guild_id, name, description, rule_json, enabled, created_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       name        = excluded.name,
                       description = excluded.description,
                       rule_json   = excluded.rule_json,
                       enabled     = excluded.enabled""",
                (
                    rule_copy["id"],
                    guild_id,
                    rule_copy.get("name", ""),
                    rule_copy.get("description", ""),
                    json.dumps(rule_copy),
                    1 if rule_copy.get("enabled", True) else 0,
                    rule_copy["created_at"],
                    rule_copy.get("created_by"),
                ),
            )
            await self._safe_commit()

    async def get_listeners(self, guild_id: int) -> List[Dict]:
        """Devuelve todas las reglas del servidor como dicts (rule_json parseado)."""
        async with self._db.execute(
            """SELECT rule_json, enabled, trigger_count, last_triggered
               FROM guild_listeners WHERE guild_id = ? ORDER BY created_at""",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
        result = []
        for row in rows:
            try:
                rule = json.loads(row["rule_json"])
                rule["enabled"]        = bool(row["enabled"])
                rule["trigger_count"]  = row["trigger_count"] or 0
                rule["last_triggered"] = row["last_triggered"]
                result.append(rule)
            except json.JSONDecodeError:
                pass
        return result

    async def get_listener(self, guild_id: int, rule_id: str) -> Optional[Dict]:
        """Devuelve una regla por su ID o None si no existe."""
        async with self._db.execute(
            """SELECT rule_json, enabled, trigger_count, last_triggered
               FROM guild_listeners WHERE guild_id = ? AND id = ?""",
            (guild_id, rule_id),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        try:
            rule = json.loads(row["rule_json"])
            rule["enabled"]        = bool(row["enabled"])
            rule["trigger_count"]  = row["trigger_count"] or 0
            rule["last_triggered"] = row["last_triggered"]
            return rule
        except json.JSONDecodeError:
            return None

    async def delete_listener(self, guild_id: int, rule_id: str) -> bool:
        """Elimina una regla. Devuelve True si existía."""
        async with self.write_lock:
            async with self._db.execute(
                "DELETE FROM guild_listeners WHERE guild_id = ? AND id = ?",
                (guild_id, rule_id),
            ) as cur:
                deleted = cur.rowcount or 0
            await self._safe_commit()
        return deleted > 0

    async def toggle_listener(self, guild_id: int, rule_id: str, enabled: bool) -> bool:
        """Activa o desactiva una regla. Devuelve True si existía."""
        async with self.write_lock:
            async with self._db.execute(
                "UPDATE guild_listeners SET enabled = ? WHERE guild_id = ? AND id = ?",
                (1 if enabled else 0, guild_id, rule_id),
            ) as cur:
                updated = cur.rowcount or 0
            await self._safe_commit()
        return updated > 0

    async def patch_listener(self, guild_id: int, rule_id: str, patch: dict) -> bool:
        """Aplica un patch parcial a una regla existente."""
        rule = await self.get_listener(guild_id, rule_id)
        if not rule:
            return False
        rule.update(patch)
        await self.save_listener(guild_id, rule)
        return True

    async def log_listener_trigger(
        self,
        guild_id: int,
        rule_id: str,
        user_id: int,
        channel_id: int,
        message_id: int,
        score: float,
        actions: str,
    ) -> None:
        """Registra un disparo en el log y actualiza el contador de la regla."""
        now     = int(time.time())
        now_iso = datetime.datetime.utcnow().isoformat()
        async with self.write_lock:
            await self._db.execute(
                """INSERT INTO listener_trigger_log
                       (guild_id, rule_id, user_id, channel_id, message_id, score, actions_run, triggered_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (guild_id, rule_id, user_id, channel_id, message_id, score, actions, now),
            )
            await self._db.execute(
                """UPDATE guild_listeners
                   SET trigger_count  = trigger_count + 1,
                       last_triggered = ?
                   WHERE id = ? AND guild_id = ?""",
                (now_iso, rule_id, guild_id),
            )
            await self._safe_commit()

    async def get_last_trigger_time(self, rule_id: str, user_id: int) -> int:
        """Retorna el timestamp del último trigger de esta regla para este usuario, o 0."""
        async with self._db.execute(
            "SELECT triggered_at FROM listener_trigger_log "
            "WHERE rule_id = ? AND user_id = ? ORDER BY triggered_at DESC LIMIT 1",
            (rule_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            return row["triggered_at"] if row else 0

    async def count_triggers_in_window(self, rule_id: str, user_id: int, window_seconds: int) -> int:
        """Cuenta triggers de esta regla+usuario en la ventana de tiempo."""
        since = int(time.time()) - window_seconds
        async with self._db.execute(
            "SELECT COUNT(*) as c FROM listener_trigger_log "
            "WHERE rule_id = ? AND user_id = ? AND triggered_at > ?",
            (rule_id, user_id, since),
        ) as cur:
            row = await cur.fetchone()
            return row["c"] if row else 0

    async def get_listener_stats(self, guild_id: int, rule_id: str, hours: int = 24) -> Dict:
        """Estadísticas de una regla: disparos por hora, top usuarios, top canales."""
        since = int(time.time()) - hours * 3600
        rule  = await self.get_listener(guild_id, rule_id)
        if not rule:
            return {"error": f"Regla {rule_id} no encontrada."}

        async with self._db.execute(
            """SELECT user_id, channel_id, score, triggered_at
               FROM listener_trigger_log
               WHERE guild_id = ? AND rule_id = ? AND triggered_at > ?
               ORDER BY triggered_at DESC LIMIT 200""",
            (guild_id, rule_id, since),
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

        from collections import Counter
        user_counts    = Counter(r["user_id"]    for r in rows)
        channel_counts = Counter(r["channel_id"] for r in rows)
        hour_counts    = Counter(
            int((r["triggered_at"] - since) // 3600) for r in rows
            if isinstance(r["triggered_at"], (int, float))
        )

        return {
            "rule_id":           rule_id,
            "rule_name":         rule.get("name", ""),
            "period_hours":      hours,
            "total_triggers":    len(rows),
            "top_users":         [{"user_id": uid, "count": c}    for uid, c in user_counts.most_common(5)],
            "top_channels":      [{"channel_id": cid, "count": c} for cid, c in channel_counts.most_common(5)],
            "triggers_per_hour": dict(hour_counts),
        }

    # ── DATA MASTERY ───────────────────────────────────────────────────────

    async def hybrid_search_messages(
        self,
        guild_id: int,
        query: str,
        hours: int = 72,
        limit: int = 20,
        user_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        semantic_weight: float = 0.5,
        min_score: float = 0.0,
        query_embedding: Optional[list] = None,
    ) -> List[Dict]:
        """
        Búsqueda híbrida: FTS5 (BM25) + KNN vectorial + fusión RRF.
        Si sqlite-vec no está disponible o query_embedding es None, cae en FTS5 puro.
        """
        import struct
        since = int(time.time()) - hours * 3600
        k = 60  # constante RRF estándar

        # ── FTS5 ──────────────────────────────────────────────────────────
        fts_results: Dict[int, int] = {}
        if semantic_weight < 1.0 and query:
            # Sanitize FTS5 query: split on commas/special chars, quote each term
            fts_query = _sanitize_fts5(query)
            if not fts_query:
                fts_query = query  # fallback: use raw if sanitization stripped everything
            clauses = ["m.guild_id = ?", "m.timestamp > ?", "fts.content MATCH ?"]
            params: List[Any] = [guild_id, since, fts_query]
            if user_id is not None: clauses.append("m.user_id = ?"); params.append(user_id)
            if channel_id is not None: clauses.append("m.channel_id = ?"); params.append(channel_id)
            params.append(min(limit * 5, 200))
            async with self._db.execute(
                f"SELECT m.id FROM messages m"
                f" JOIN messages_fts fts ON fts.rowid = m.id"
                f" WHERE {' AND '.join(clauses)} ORDER BY fts.rank LIMIT ?",
                params,
            ) as cur:
                for rank, row in enumerate(await cur.fetchall()):
                    fts_results[row["id"]] = rank + 1

        # ── KNN vectorial (ChromaDB) ──────────────────────────────────────
        vec_results: Dict[int, int] = {}
        if semantic_weight > 0.0 and query_embedding is not None and self._vec_available:
            try:
                knn_limit = min(limit * 5, 200)
                vec_results = await self.chroma_memory.search_messages(
                    query_embedding=query_embedding,
                    guild_id=guild_id,
                    limit=knn_limit,
                    since=since,
                    channel_id=channel_id,
                    user_id=user_id
                )
            except Exception as e:
                logger.error("Error al buscar en ChromaMemory durante búsqueda híbrida: %s", e)

        # ── RRF fusion ────────────────────────────────────────────────────
        all_ids = set(fts_results) | set(vec_results)
        if not all_ids:
            # FTS5 + vector both empty → fallback to LIKE for broader matching
            if query and semantic_weight < 1.0:
                # LIKE fallback: busca cada palabra individualmente con OR lógico
                # El query puede tener 10+ palabras — cada una se busca por separado
                import re as _re
                words = [w for w in _re.split(r'\s+', query.strip()) if len(w) >= 3][:8]
                if not words:
                    return []
                
                like_clauses = " OR ".join(["m.content LIKE ? ESCAPE '\\'"] * len(words))
                like_params = [f"%{self._like_escape(w)}%" for w in words]
                
                async with self._db.execute(
                    f"""SELECT m.id FROM messages m
                       WHERE m.guild_id = ? AND m.timestamp > ?
                       AND ({like_clauses})
                       ORDER BY m.timestamp DESC LIMIT ?""",
                    [guild_id, since] + like_params + [min(limit * 3, 60)],
                ) as cur:
                    like_ids = [row["id"] for row in await cur.fetchall()]
                if like_ids:
                    # Rank by recency (higher rank = more recent)
                    for rank, mid in enumerate(like_ids):
                        fts_results[mid] = rank + 1
                    all_ids = set(like_ids)
            if not all_ids:
                return []

        def rrf(mid: int) -> float:
            s = 0.0
            if mid in fts_results and semantic_weight < 1.0:
                s += (1.0 - semantic_weight) / (k + fts_results[mid])
            if mid in vec_results and semantic_weight > 0.0:
                s += semantic_weight / (k + vec_results[mid])
            return s

        ranked = sorted(all_ids, key=rrf, reverse=True)
        if min_score > 0.0:
            ranked = [m for m in ranked if rrf(m) >= min_score]
        ranked = ranked[:limit]
        if not ranked:
            return []

        ph = ",".join("?" * len(ranked))
        async with self._db.execute(
            f"""SELECT m.id, m.user_id, m.channel_id, m.content, m.timestamp,
                       COALESCE(NULLIF(m.username,''), p.username, p.display_name,
                                CAST(m.user_id AS TEXT)) AS username
                FROM messages m
                LEFT JOIN user_profiles p ON p.user_id = m.user_id
                WHERE m.id IN ({ph})""",
            ranked,
        ) as cur:
            rows_dict = {r["id"]: dict(r) for r in await cur.fetchall()}

        result = []
        for mid in ranked:
            if mid in rows_dict:
                rows_dict[mid]["rrf_score"] = round(rrf(mid), 6)
                result.append(rows_dict[mid])
        return result

    # ── Embedding storage ────────────────────────────────────────────────

    async def store_embeddings(self, items: List[Dict]) -> None:
        """Almacena embeddings en batch en ChromaDB."""
        if not items or not self._vec_available:
            return
        try:
            await self.chroma_memory.add_messages(items)
        except Exception as e:
            logger.error("Error guardando embeddings en ChromaMemory: %s", e)

    async def get_unembedded_message_ids(self, limit: int = 200) -> List[Dict]:
        """Devuelve mensajes sin embedding (para backfill)."""
        async with self._db.execute(
            """SELECT m.id, m.content FROM messages m
            WHERE m.id NOT IN (SELECT rowid FROM vec_messages)
            AND m.content IS NOT NULL
            AND LENGTH(m.content) >= 20
            ORDER BY m.id ASC LIMIT ?""",
            (limit,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def archive_old_embeddings(self, age_days: int = 90, batch_size: int = 500) -> int:
        """Deprecated: SQLite-vec archival logic. Returns 0."""
        return 0
        cutoff = int(time.time()) - age_days * 86400
        archived = 0
        while True:
            # Find batch of old embeddings still in hot table
            async with self._db.execute(
                """SELECT ve.rowid, ve.embedding FROM vec_messages ve
                   INNER JOIN messages m ON m.id = ve.rowid
                   WHERE m.timestamp < ?
                   LIMIT ?""",
                (cutoff, batch_size),
            ) as cur:
                rows = await cur.fetchall()
            if not rows:
                break
            async with self.write_lock:
                for row in rows:
                    rowid = row["rowid"]
                    emb_blob = row["embedding"]
                    # Truncate: take first 128 dims from int8[384]
                    truncated = emb_blob[:128]
                    # Renormalize int8[128] to use full -127..127 range
                    arr = np.frombuffer(truncated, dtype=np.int8).astype(np.float32)
                    max_val = np.max(np.abs(arr))
                    if max_val > 0:
                        arr = arr * (127.0 / max_val)
                    renormed = np.clip(np.round(arr), -127, 127).astype(np.int8).tobytes()
                    try:
                        await self._db.execute(
                            "INSERT OR REPLACE INTO vec_messages_archive (rowid, embedding) VALUES (?, ?)",
                            (rowid, renormed),
                        )
                        await self._db.execute(
                            "DELETE FROM vec_messages WHERE rowid = ?", (rowid,)
                        )
                    except Exception:
                        continue
                await self._safe_commit()
            archived += len(rows)
        return archived

    async def purge_ancient_embeddings(self, age_days: int = 365) -> int:
        """Deprecated: SQLite-vec purge logic. Returns 0."""
        return 0
        cutoff = int(time.time()) - age_days * 86400
        async with self.write_lock:
            try:
                await self._db.execute(
                    """DELETE FROM vec_messages_archive WHERE rowid IN (
                        SELECT id FROM messages WHERE timestamp < ?
                    )""",
                    (cutoff,),
                )
                await self._safe_commit()
                return 0
            except Exception:
                return 0

    async def search_archive_vectors(
        self, query_embedding: list, guild_id: int, limit: int = 50
    ) -> Dict[int, int]:
        """KNN search on vec_messages_archive (warm tier, int8[128]).

        Returns {message_id: rank} dict, same format as hot tier results.
        Query embedding is truncated to 128 dims and quantized to int8.
        """
        if not self._vec_available or query_embedding is None:
            return {}
        try:
            # Truncate query to 128 dims + quantize
            q_arr = np.array(query_embedding[:128], dtype=np.float32)
            max_val = np.max(np.abs(q_arr))
            if max_val == 0:
                max_val = 1.0
            scale = 127.0 / max_val
            q_int8 = np.clip(np.round(q_arr * scale), -127, 127).astype(np.int8)
            blob = q_int8.tobytes()

            knn_limit = min(limit * 3, 150)
            results: Dict[int, int] = {}
            async with self._db.execute(
                """SELECT ve.rowid as message_id, ve.distance
                FROM vec_messages_archive ve
                WHERE ve.embedding MATCH ? AND k = ?
                ORDER BY ve.distance""",
                (blob, knn_limit),
            ) as cur:
                for rank, row in enumerate(await cur.fetchall()):
                    results[row["message_id"]] = rank + 1

            # Filter by guild
            if results:
                ph = ",".join("?" * len(results))
                valid_ids: set = set()
                async with self._db.execute(
                    f"SELECT id FROM messages WHERE id IN ({ph}) AND guild_id = ?",
                    list(results.keys()) + [guild_id],
                ) as cur:
                    for row in await cur.fetchall():
                        valid_ids.add(row["id"])
                results = {k: v for k, v in results.items() if k in valid_ids}
            return results
        except Exception:
            return {}

    async def aggregate_messages(
        self,
        guild_id: int,
        group_by: str = "user",
        hours: int = 168,
        limit: int = 20,
        user_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        start_ts: Optional[str] = None,
        end_ts: Optional[str] = None,
        agg_type: str = "messages",
    ) -> List[Dict]:
        """Aggregación SQL directa. Soporta rangos absolutos con start_ts/end_ts."""
        import datetime as _dt
        if start_ts:
            start = int(_dt.datetime.fromisoformat(start_ts).timestamp())
            end   = int(_dt.datetime.fromisoformat(end_ts).timestamp()) if end_ts else int(time.time())
        else:
            start = int(time.time()) - hours * 3600
            end   = int(time.time())

        if agg_type == "audit":
            async with self._db.execute(
                "SELECT action, COUNT(*) as count FROM youkai_audit"
                " WHERE guild_id = ? AND timestamp BETWEEN ? AND ?"
                " GROUP BY action ORDER BY count DESC LIMIT ?",
                (guild_id, start, end, limit),
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

        base_clauses = ["m.guild_id = ?", "m.timestamp BETWEEN ? AND ?"]
        base_params: List[Any] = [guild_id, start, end]
        if user_id    is not None: base_clauses.append("m.user_id = ?");    base_params.append(user_id)
        if channel_id is not None: base_clauses.append("m.channel_id = ?"); base_params.append(channel_id)
        w = " AND ".join(base_clauses)

        QUERIES = {
            "user":        f"SELECT m.user_id, COALESCE(p.display_name, p.username, CAST(m.user_id AS TEXT)) AS label, COUNT(*) AS count FROM messages m LEFT JOIN user_profiles p ON p.user_id = m.user_id WHERE {w} GROUP BY m.user_id ORDER BY count DESC LIMIT ?",
            "channel":     f"SELECT m.channel_id AS id, m.channel_id AS label, COUNT(*) AS count FROM messages m WHERE {w} GROUP BY m.channel_id ORDER BY count DESC LIMIT ?",
            "day":         f"SELECT DATE(m.timestamp, 'unixepoch') AS label, COUNT(*) AS count FROM messages m WHERE {w} GROUP BY label ORDER BY label ASC LIMIT ?",
            "hour_of_day": f"SELECT CAST(strftime('%H', m.timestamp, 'unixepoch') AS INTEGER) AS label, COUNT(*) AS count FROM messages m WHERE {w} GROUP BY label ORDER BY count DESC LIMIT 24",
        }
        if group_by not in QUERIES:
            return [{"error": f"group_by '{group_by}' inválido. Usa: user, channel, day, hour_of_day"}]

        params = base_params + ([limit] if group_by != "hour_of_day" else [])
        async with self._db.execute(QUERIES[group_by], params) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def paginate_messages(
        self,
        guild_id: int,
        hours: int = 168,
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        start_ts: Optional[str] = None,
        end_ts: Optional[str] = None,
        order: str = "desc",
    ) -> Dict:
        """Paginación real con OFFSET. Devuelve has_more y next_offset."""
        import datetime as _dt
        if start_ts:
            start = int(_dt.datetime.fromisoformat(start_ts).timestamp())
            end   = int(_dt.datetime.fromisoformat(end_ts).timestamp()) if end_ts else int(time.time())
        else:
            start = int(time.time()) - hours * 3600
            end   = int(time.time())

        clauses = ["m.guild_id = ?", "m.timestamp BETWEEN ? AND ?"]
        params: List[Any] = [guild_id, start, end]
        if user_id    is not None: clauses.append("m.user_id = ?");    params.append(user_id)
        if channel_id is not None: clauses.append("m.channel_id = ?"); params.append(channel_id)
        w      = " AND ".join(clauses)
        od     = "ASC" if str(order).lower() == "asc" else "DESC"
        limit  = max(1, min(200, int(limit)))
        offset = max(0, int(offset))

        async with self._db.execute(
            f"SELECT COUNT(*) as total FROM messages m WHERE {w}", params
        ) as cur:
            total = (await cur.fetchone())["total"]

        async with self._db.execute(
            f"""SELECT m.user_id, m.channel_id, m.content, m.timestamp, m.id,
                       COALESCE(NULLIF(m.username,''), p.username, p.display_name,
                                CAST(m.user_id AS TEXT)) AS username
                FROM messages m
                LEFT JOIN user_profiles p ON p.user_id = m.user_id
                WHERE {w} ORDER BY m.timestamp {od} LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ) as cur:
            msgs = [dict(r) for r in await cur.fetchall()]

        return {
            "messages":        msgs,
            "count":           len(msgs),
            "total_in_window": total,
            "has_more":        (offset + len(msgs)) < total,
            "next_offset":     offset + len(msgs) if (offset + len(msgs)) < total else None,
        }

    async def get_user_timeline(
        self,
        guild_id: int,
        user_id: int,
        days: int = 14,
    ) -> Dict:
        """Timeline cronológico: mensajes + warns + acciones de mod entrelazados."""
        since = int(time.time()) - days * 86400

        async with self._db.execute(
            "SELECT 'message' as type, timestamp, content as detail, channel_id, NULL as action"
            " FROM messages WHERE guild_id = ? AND user_id = ? AND timestamp > ?"
            " ORDER BY timestamp ASC LIMIT 300",
            (guild_id, user_id, since),
        ) as cur:
            messages = [dict(r) for r in await cur.fetchall()]

        async with self._db.execute(
            "SELECT 'mod_action' as type, timestamp, details as detail, NULL as channel_id, action"
            " FROM youkai_audit WHERE guild_id = ? AND target_id = ? AND timestamp > ?"
            " ORDER BY timestamp ASC",
            (guild_id, user_id, since),
        ) as cur:
            mod_actions = [dict(r) for r in await cur.fetchall()]

        async with self._db.execute(
            "SELECT 'warning' as type, timestamp, reason as detail, NULL as channel_id, 'warn' as action"
            " FROM warnings WHERE guild_id = ? AND user_id = ? AND timestamp > ?"
            " ORDER BY timestamp ASC",
            (guild_id, user_id, since),
        ) as cur:
            warns = [dict(r) for r in await cur.fetchall()]

        import datetime as _dt
        timeline = sorted(messages + mod_actions + warns, key=lambda x: x["timestamp"])
        day_counts: Dict[str, int] = {}
        for item in messages:
            day = _dt.datetime.utcfromtimestamp(item["timestamp"]).strftime("%Y-%m-{}")
            day_counts[day] = day_counts.get(day, 0) + 1

        return {
            "user_id":          user_id,
            "days_analyzed":    days,
            "total_messages":   len(messages),
            "total_mod_events": len(mod_actions) + len(warns),
            "activity_by_day":  day_counts,
            "timeline":         timeline,
        }

    async def query_pattern_analysis(
        self,
        guild_id: int,
        mode: str,
        hours: int = 168,
        days: int = 7,
        min_overlap: int = 3,
        sensitivity: float = 2.0,
        min_previous_messages: int = 10,
    ) -> Dict:
        """Análisis de patrones: cooccurrence | anomaly | sudden_silence."""
        import math
        from collections import defaultdict
        since = int(time.time()) - hours * 3600

        if mode == "cooccurrence":
            # Python bucket approach — O(n) fetch + O(buckets*users²) compute
            async with self._db.execute(
                "SELECT user_id, channel_id, timestamp / 1800 AS bucket "
                "FROM messages WHERE guild_id = ? AND timestamp > ?",
                (guild_id, since),
            ) as cur:
                rows = await cur.fetchall()
            buckets: dict = defaultdict(set)
            for user_id, channel_id, bucket in rows:
                buckets[(channel_id, bucket)].add(user_id)
            pairs: dict = defaultdict(lambda: [0, set()])
            for (ch, _), users in buckets.items():
                if len(users) < 2 or len(users) > 40:
                    continue
                users_list = sorted(users)
                for i in range(len(users_list)):
                    for j in range(i + 1, len(users_list)):
                        key = (users_list[i], users_list[j])
                        pairs[key][0] += 1
                        pairs[key][1].add(ch)
            results = sorted(
                [{"user_a": k[0], "user_b": k[1],
                  "shared_channels": len(v[1]), "co_messages": v[0]}
                 for k, v in pairs.items() if v[0] >= min_overlap],
                key=lambda x: x["co_messages"], reverse=True,
            )[:30]
            return {"mode": "cooccurrence", "period_hours": hours, "pairs": results}

        elif mode == "anomaly":
            async with self._db.execute(
                "SELECT CAST(strftime('%H', timestamp, 'unixepoch') AS INTEGER) as hour,"
                " COUNT(*) as count FROM messages"
                " WHERE guild_id = ? AND timestamp > ? GROUP BY hour ORDER BY hour",
                (guild_id, since),
            ) as cur:
                rows = [dict(r) for r in await cur.fetchall()]
            if len(rows) < 3:
                return {"mode": "anomaly", "anomalies": [], "note": "Datos insuficientes"}
            counts = [r["count"] for r in rows]
            mean   = sum(counts) / len(counts)
            std    = math.sqrt(sum((x - mean) ** 2 for x in counts) / len(counts))
            anomalies = []
            for row in rows:
                if std > 0:
                    z = (row["count"] - mean) / std
                    if abs(z) >= sensitivity:
                        anomalies.append({
                            "hour_utc": row["hour"], "count": row["count"],
                            "z_score":  round(z, 2),
                            "type":     "spike" if z > 0 else "drop",
                        })
            return {
                "mode": "anomaly", "period_hours": hours,
                "mean_per_hour": round(mean, 1), "std_dev": round(std, 1),
                "sensitivity": sensitivity,
                "anomalies": sorted(anomalies, key=lambda x: abs(x["z_score"]), reverse=True),
            }

        elif mode == "sudden_silence":
            cutoff_recent = int(time.time()) - 2 * 86400
            cutoff_before = int(time.time()) - days * 86400
            async with self._db.execute(
                "SELECT user_id, COUNT(*) as msg_before FROM messages"
                " WHERE guild_id = ? AND timestamp BETWEEN ? AND ?"
                " GROUP BY user_id HAVING COUNT(*) >= ?",
                (guild_id, cutoff_before, cutoff_recent - 2 * 86400, min_previous_messages),
            ) as cur:
                active_before = {r["user_id"]: r["msg_before"] for r in await cur.fetchall()}
            async with self._db.execute(
                "SELECT DISTINCT user_id FROM messages WHERE guild_id = ? AND timestamp > ?",
                (guild_id, cutoff_recent),
            ) as cur:
                active_recent = {r["user_id"] for r in await cur.fetchall()}
            silent = sorted(
                [{"user_id": uid, "messages_before": c}
                 for uid, c in active_before.items() if uid not in active_recent],
                key=lambda x: x["messages_before"], reverse=True,
            )
            return {
                "mode": "sudden_silence", "days": days,
                "silent_users": silent[:30], "count": len(silent),
            }

        return {"error": f"modo '{mode}' inválido. Usa: cooccurrence, anomaly, sudden_silence"}

    # ── Nexus proxy methods ─────────────────────────────────────────────

    async def nexus_update_association(
        self,
        alias: str,
        entity_id: str,
        entity_type: str,
        name: str,
        guild_id: int,
    ) -> None:
        """Refuerza la asociacion entre un alias y una entidad (Nexus)."""
        alias = alias.lower().strip()
        if not alias:
            return
        async with self.write_lock:
            await self._db.execute(
                "INSERT OR REPLACE INTO entities "
                "(entity_id, type, canonical_name, guild_id) VALUES (?, ?, ?, ?)",
                (entity_id, entity_type, name, guild_id),
            )
            await self._db.execute(
                "INSERT INTO aliases (alias, entity_id, guild_id, weight) "
                "VALUES (?, ?, ?, 1) "
                "ON CONFLICT(alias, entity_id, guild_id) "
                "DO UPDATE SET weight = weight + 1",
                (alias, entity_id, guild_id),
            )
            await self._safe_commit()

    async def nexus_resolve_entity(
        self, query: str, guild_id: int
    ) -> Optional[Dict[str, Any]]:
        """Resuelve un alias al entity de mayor peso (Nexus)."""
        query = query.lower().strip()
        async with self._db.execute(
            "SELECT entity_id FROM aliases "
            "WHERE alias = ? AND guild_id = ? "
            "ORDER BY weight DESC LIMIT 1",
            (query, guild_id),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        entity_id = row["entity_id"]
        async with self._db.execute(
            "SELECT type, canonical_name FROM entities "
            "WHERE entity_id = ? AND guild_id = ?",
            (entity_id, guild_id),
        ) as cur:
            entity_row = await cur.fetchone()
        if entity_row:
            return {
                "id": entity_id,
                "type": entity_row["type"],
                "name": entity_row["canonical_name"],
                "guild_id": guild_id,
            }
        return None

    async def nexus_get_context_snapshot(
        self, guild_id: int, limit: int = 20
    ) -> str:
        """Genera un string compacto con entidades relevantes (Nexus)."""
        async with self._db.execute(
            "SELECT e.entity_id, e.type, e.canonical_name, "
            "GROUP_CONCAT(a.alias, ', ') AS aliases "
            "FROM entities e "
            "JOIN aliases a "
            "ON e.entity_id = a.entity_id AND e.guild_id = a.guild_id "
            "WHERE e.guild_id = ? "
            "GROUP BY e.entity_id "
            "ORDER BY SUM(a.weight) DESC "
            "LIMIT ?",
            (guild_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        if not rows:
            return ""
        parts = []
        for row in rows:
            eid, etype, name, aliases = (
                row["entity_id"], row["type"],
                row["canonical_name"], row["aliases"],
            )
            prefix = "U" if etype == "user" else ("R" if etype == "role" else "C")
            parts.append(f"{prefix}:{eid}({name}, {aliases})")
        return " | ".join(parts)

    # ── Curse (Maldición) ──────────────────────────────────────────────────

    async def add_curse(
        self, guild_id: int, user_id: int, release_at: str, reason: str = "",
        created_by: Optional[int] = None, display_name: str = "",
    ) -> None:
        """Registra una maldición activa (INSERT OR REPLACE)."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self.write_lock:
            await self._db.execute(
                "INSERT OR REPLACE INTO curses "
                "(guild_id, user_id, started_at, release_at, reason, "
                "original_display_name, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (guild_id, user_id, now, release_at, reason,
                 display_name, created_by),
            )
            await self._safe_commit()

    async def remove_curse(self, guild_id: int, user_id: int) -> bool:
        """Elimina una maldición. Retorna True si existía."""
        async with self.write_lock:
            cur = await self._db.execute(
                "DELETE FROM curses WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await self._safe_commit()
            return cur.rowcount > 0

    async def get_curse(self, guild_id: int, user_id: int) -> Optional[Dict]:
        """Obtiene una maldición específica."""
        async with self._db.execute(
            "SELECT * FROM curses WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_active_curses(self, guild_id: int) -> List[Dict]:
        """Obtiene todas las maldiciones activas (release_at > now)."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self._db.execute(
            "SELECT * FROM curses WHERE guild_id = ? AND release_at > ?",
            (guild_id, now),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    # ── Mouth Wash (Lavado de Boca) ────────────────────────────────────────
    
    async def add_mouth_wash(
        self, guild_id: int, user_id: int, release_at: str, reason: str = "",
        created_by: Optional[int] = None, display_name: str = "",
    ) -> None:
        """Registra un lavado de boca activo (INSERT OR REPLACE)."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self.write_lock:
            await self._db.execute(
                "INSERT OR REPLACE INTO mouth_washes "
                "(guild_id, user_id, started_at, release_at, reason, "
                "display_name, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (guild_id, user_id, now, release_at, reason,
                 display_name, created_by),
            )
            await self._safe_commit()
    
    async def remove_mouth_wash(self, guild_id: int, user_id: int) -> bool:
        """Elimina un lavado de boca. Retorna True si existia."""
        async with self.write_lock:
            cur = await self._db.execute(
                "DELETE FROM mouth_washes WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            await self._safe_commit()
            return cur.rowcount > 0
    
    async def get_mouth_wash(self, guild_id: int, user_id: int) -> Optional[Dict]:
        """Obtiene un lavado de boca especifico."""
        async with self._db.execute(
            "SELECT * FROM mouth_washes WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
    
    async def get_active_mouth_washes(self, guild_id: int) -> List[Dict]:
        """Obtiene todos los lavados de boca activos (release_at > now)."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self._db.execute(
            "SELECT * FROM mouth_washes WHERE guild_id = ? AND release_at > ?",
            (guild_id, now),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    # ── Raw query for internal consumers (GraphAnalyzer, etc) ───────────────

    async def fetch(self, query: str, params: tuple = ()) -> List[dict]:
        """Execute a read-only query safely. For internal module consumers."""
        if self._db is None:
            raise RuntimeError("Database not initialized")
        async with self._db.execute(query, params) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Execute a read-only query returning a single row or None."""
        if self._db is None:
            raise RuntimeError("Database not initialized")
        async with self._db.execute(query, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    # ── Credits ─────────────────────────────────────────────────────────────

    async def get_credits(self, user_id: int, guild_id: int) -> dict:
        today = __import__("datetime").date.today().isoformat()
        row = await self.fetchone(
            "SELECT * FROM user_credits WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        if not row:
            return {"balance": 0, "earned_today": 0, "spent_today": 0, "calls_today": 0, "last_reset": today}
        d = dict(row)
        if d["last_reset"] != today:
            d["earned_today"] = 0
            d["spent_today"] = 0
            d["calls_today"] = 0
            d["last_reset"] = today
            await self._db.execute(
                "UPDATE user_credits SET earned_today=0, spent_today=0, calls_today=0, last_reset=? WHERE user_id=? AND guild_id=?",
                (today, user_id, guild_id),
            )
            await self._db.commit()
        return d

    async def add_credits(self, user_id: int, guild_id: int, amount: int,
                          reason: str = "earn", ref: str = "") -> int:
        today = __import__("datetime").date.today().isoformat()
        async with self.write_lock:
            try:
                await self._db.execute(
                    "INSERT INTO user_credits (user_id, guild_id, balance, earned_today, last_reset) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(user_id, guild_id) DO UPDATE SET balance=balance+?, earned_today=CASE WHEN last_reset=? THEN earned_today+? ELSE ? END, last_reset=?",
                    (user_id, guild_id, amount, amount, today, amount, today, amount, amount, today),
                )
                row = await self.fetchone("SELECT balance FROM user_credits WHERE user_id=? AND guild_id=?", (user_id, guild_id))
                bal = row["balance"] if row else amount
                await self._ledger_inside_transaction(user_id, guild_id, amount, bal, reason, ref)
                await self._safe_commit()
                return bal
            except Exception:
                await self._db.rollback()
                raise

    async def spend_credits(self, user_id: int, guild_id: int, amount: int,
                            reason: str = "spend", ref: str = "") -> int:
        today = __import__("datetime").date.today().isoformat()
        async with self.write_lock:
            try:
                # F1 (review): débito atómico condicional. El guard `balance>=?`
                # impide doble gasto / balance negativo bajo concurrencia — la
                # verificación previa en can_spend() no es atómica con este UPDATE.
                cur = await self._db.execute(
                    "UPDATE user_credits SET balance=balance-?, spent_today=CASE WHEN last_reset=? THEN spent_today+? ELSE ? END, "
                    "calls_today=CASE WHEN last_reset=? THEN calls_today+1 ELSE 1 END, last_reset=? "
                    "WHERE user_id=? AND guild_id=? AND balance>=?",
                    (amount, today, amount, amount, today, today, user_id, guild_id, amount),
                )
                row = await self.fetchone("SELECT balance FROM user_credits WHERE user_id=? AND guild_id=?", (user_id, guild_id))
                bal = row["balance"] if row else 0
                # Solo registrar en el ledger si el débito realmente ocurrió.
                if cur.rowcount == 1:
                    await self._ledger_inside_transaction(user_id, guild_id, -amount, bal, reason, ref)
                await self._safe_commit()
                return bal
            except Exception:
                await self._db.rollback()
                raise

    async def _ledger_inside_transaction(self, uid: int, gid: int, delta: int, bal: int, reason: str, ref: str) -> None:
        """Append to credit_ledger with crc32 hash inside an active transaction (no commit)."""
        import time, zlib, struct
        ts = int(time.time())
        # Hash: crc32 of (ts + uid + delta + bal) — 8 hex chars, zero-cost
        raw = struct.pack(">qiqi", uid, delta, ts, bal)
        h = format(zlib.crc32(raw) & 0xFFFFFFFF, "08x")
        await self._db.execute(
            "INSERT INTO credit_ledger (ts, uid, gid, delta, bal, reason, ref, hash) VALUES (?,?,?,?,?,?,?,?)",
            (ts, uid, gid, delta, bal, reason[:16], ref[:60], h),
        )

    async def _ledger(self, uid: int, gid: int, delta: int, bal: int, reason: str, ref: str) -> None:
        """Append to credit_ledger with crc32 hash (legacy, with individual commit)."""
        async with self.write_lock:
            await self._ledger_inside_transaction(uid, gid, delta, bal, reason, ref)
            await self._safe_commit()

    # ── Token tracking ─────────────────────────────────────────────────────

    async def track_tokens(self, guild_id: int, user_id: int, tokens_in: int, tokens_out: int) -> None:
        today = __import__("datetime").date.today().isoformat()
        async with self.write_lock:
            await self._db.execute(
                "INSERT INTO token_usage (guild_id, user_id, date, tokens_in, tokens_out, calls) "
                "VALUES (?,?,?,?,?,1) ON CONFLICT(guild_id, user_id, date) DO UPDATE SET "
                "tokens_in=tokens_in+?, tokens_out=tokens_out+?, calls=calls+1",
                (guild_id, user_id, today, tokens_in, tokens_out, tokens_in, tokens_out),
            )
            await self._safe_commit()

    async def get_token_usage(self, guild_id: int, user_id: int = None, days: int = 7) -> list:
        cutoff = (__import__("datetime").date.today() - __import__("datetime").timedelta(days=days)).isoformat()
        if user_id:
            rows = await self.fetchall(
                "SELECT * FROM token_usage WHERE guild_id=? AND user_id=? AND date>=? ORDER BY date DESC",
                (guild_id, user_id, cutoff),
            )
        else:
            rows = await self.fetchall(
                "SELECT date, SUM(tokens_in) as tokens_in, SUM(tokens_out) as tokens_out, SUM(calls) as calls "
                "FROM token_usage WHERE guild_id=? AND date>=? GROUP BY date ORDER BY date DESC",
                (guild_id, cutoff),
            )
        return [dict(r) for r in rows]

    # ── Loans (Youkai Financial Services™) ─────────────────────────────────

    async def get_loan_score(self, user_id: int, guild_id: int) -> dict:
        row = await self.fetchone(
            "SELECT * FROM loan_scores WHERE user_id=? AND guild_id=?", (user_id, guild_id)
        )
        if row:
            return dict(row)
        return {"score": 500, "total_loans": 0, "paid_on_time": 0,
                "missed_payments": 0, "defaults_count": 0, "blacklisted": 0}

    async def update_loan_score(self, user_id: int, guild_id: int, delta: int) -> int:
        await self._db.execute(
            "INSERT INTO loan_scores (user_id, guild_id, score) VALUES (?,?,?) "
            "ON CONFLICT(user_id, guild_id) DO UPDATE SET score=MAX(0, MIN(1000, score+?))",
            (user_id, guild_id, max(0, min(1000, 500 + delta)), delta),
        )
        await self._safe_commit()
        row = await self.fetchone("SELECT score FROM loan_scores WHERE user_id=? AND guild_id=?", (user_id, guild_id))
        return row["score"] if row else 500

    async def get_active_loan(self, user_id: int, guild_id: int) -> Optional[dict]:
        row = await self.fetchone(
            "SELECT * FROM loans WHERE user_id=? AND guild_id=? AND status='active'",
            (user_id, guild_id),
        )
        return dict(row) if row else None

    async def create_loan(self, user_id: int, guild_id: int, channel_id: int,
                          principal: int, rate: float, total: int,
                          installment: int, num_installments: int) -> int:
        """Crea un préstamo activo. NO debita la treasury — usar create_loan_with_treasury."""
        now = datetime.datetime.now(datetime.timezone.utc)
        next_col = (now + datetime.timedelta(hours=24)).isoformat()
        async with self.write_lock:
            cur = await self._db.execute(
                "INSERT INTO loans (user_id, guild_id, channel_id, principal, interest_rate, "
                "total_owed, installment_amt, num_installments, remaining_debt, created_at, next_collection) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (user_id, guild_id, channel_id, principal, rate, total, installment,
                 num_installments, total, now.isoformat(), next_col),
            )
            await self._db.execute(
                "INSERT INTO loan_scores (user_id, guild_id, total_loans) VALUES (?,?,1) "
                "ON CONFLICT(user_id, guild_id) DO UPDATE SET total_loans=total_loans+1",
                (user_id, guild_id),
            )
            await self._safe_commit()
            return cur.lastrowid

    async def create_loan_with_treasury(self, user_id: int, guild_id: int, channel_id: int,
                                        principal: int, rate: float, total: int,
                                        installment: int, num_installments: int) -> Optional[int]:
        """Crea un préstamo Y debita la treasury atómicamente.

        Retorna ``loan_id`` si éxito, ``None`` si la treasury no tiene fondos suficientes.
        El monto desembolsado es ``principal`` (lo que recibe el usuario), NO ``total_owed``.
        """
        # Garantizar que la treasury existe (bootstrap si es la primera vez)
        await self._ensure_treasury(guild_id)

        now = datetime.datetime.now(datetime.timezone.utc)
        next_col = (now + datetime.timedelta(hours=24)).isoformat()
        now_iso = now.isoformat()

        async with self.write_lock:
            # Atomic: verificar y debitar bajo el mismo lock
            row = await (await self._db.execute(
                "SELECT balance FROM guild_treasury WHERE guild_id=?", (guild_id,)
            )).fetchone()
            if not row or row[0] < principal:
                return None

            new_balance = row[0] - principal

            cur = await self._db.execute(
                "INSERT INTO loans (user_id, guild_id, channel_id, principal, interest_rate, "
                "total_owed, installment_amt, num_installments, remaining_debt, created_at, next_collection) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (user_id, guild_id, channel_id, principal, rate, total, installment,
                 num_installments, total, now_iso, next_col),
            )
            loan_id = cur.lastrowid
            await self._db.execute(
                "INSERT INTO loan_scores (user_id, guild_id, total_loans) VALUES (?,?,1) "
                "ON CONFLICT(user_id, guild_id) DO UPDATE SET total_loans=total_loans+1",
                (user_id, guild_id),
            )
            # Debitar treasury
            await self._db.execute(
                "UPDATE guild_treasury SET balance=?, total_disbursed=total_disbursed+?, "
                "last_modified=? WHERE guild_id=?",
                (new_balance, principal, now_iso, guild_id),
            )
            # Movement
            await self._db.execute(
                "INSERT INTO guild_treasury_movements "
                "(guild_id, amount, balance_after, reason, metadata, user_id, by_staff_id, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (guild_id, -principal, new_balance, "loan_disbursed",
                 f'{{"loan_id": {loan_id}, "principal": {principal}}}',
                 user_id, None, now_iso),
            )
            await self._safe_commit()
            return loan_id

    async def get_due_loans(self, now_iso: str) -> list[dict]:
        rows = await self.fetch(
            "SELECT * FROM loans WHERE status='active' AND next_collection<=?", (now_iso,)
        )
        return [dict(r) for r in rows]

    async def record_loan_payment(self, loan_id: int, user_id: int, guild_id: int,
                                  due: int, paid: int, success: bool,
                                  bal_before: int, bal_after: int) -> None:
        """Registra un cobro. Si éxito, deposita el monto en la treasury del guild."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        next_col = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)).isoformat()
        # Asegurar que la treasury existe (bootstrap idempotente)
        if success and paid > 0:
            await self._ensure_treasury(guild_id)
        async with self.write_lock:
            await self._db.execute(
                "INSERT INTO loan_payments (loan_id, user_id, guild_id, amount_due, amount_paid, "
                "success, balance_before, balance_after, collected_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (loan_id, user_id, guild_id, due, paid, int(success), bal_before, bal_after, now),
            )
            if success:
                # Distribute dividends first, based on interest portion of the payment
                row_loan = await (await self._db.execute(
                    "SELECT principal, total_owed FROM loans WHERE id=?", (loan_id,)
                )).fetchone()
                if row_loan and row_loan[1] > 0:
                    l_principal, l_total = row_loan[0], row_loan[1]
                    # Interest portion = paid * (total_owed - principal) / total_owed
                    interest_portion = float(paid) * (float(l_total - l_principal) / float(l_total))
                    if interest_portion > 0.0:
                        row_shares = await (await self._db.execute(
                            "SELECT SUM(shares) FROM treasury_shares WHERE guild_id=?", (guild_id,)
                        )).fetchone()
                        total_shares = row_shares[0] if (row_shares and row_shares[0]) else 0
                        if total_shares > 0:
                            dividend_per_share = interest_portion / float(total_shares)
                            await self._db.execute(
                                "UPDATE treasury_shares SET unclaimed_dividends = unclaimed_dividends + (shares * ?) "
                                "WHERE guild_id = ?",
                                (dividend_per_share, guild_id),
                            )

                await self._db.execute(
                    "UPDATE loans SET paid_installments=paid_installments+1, "
                    "remaining_debt=remaining_debt-?, consecutive_misses=0, "
                    "next_collection=? WHERE id=?",
                    (paid, next_col, loan_id),
                )
                await self._db.execute(
                    "UPDATE loan_scores SET paid_on_time=paid_on_time+1, "
                    "score=MIN(1000, score+15) WHERE user_id=? AND guild_id=?",
                    (user_id, guild_id),
                )
                # Treasury inflow: la cuota completa (principal + interés) vuelve al pool
                if paid > 0:
                    row = await (await self._db.execute(
                        "SELECT balance FROM guild_treasury WHERE guild_id=?", (guild_id,)
                    )).fetchone()
                    if row:
                        new_bal = row[0] + paid
                        await self._db.execute(
                            "UPDATE guild_treasury SET balance=?, total_collected=total_collected+?, "
                            "last_modified=? WHERE guild_id=?",
                            (new_bal, paid, now, guild_id),
                        )
                        await self._db.execute(
                            "INSERT INTO guild_treasury_movements "
                            "(guild_id, amount, balance_after, reason, metadata, user_id, by_staff_id, created_at) "
                            "VALUES (?,?,?,?,?,?,?,?)",
                            (guild_id, paid, new_bal, "loan_repayment",
                             f'{{"loan_id": {loan_id}, "due": {due}}}',
                             user_id, None, now),
                        )
            else:
                # Query details to calculate late fees: 10% of installment + 5% of remaining debt
                row_loan = await (await self._db.execute(
                    "SELECT installment_amt, remaining_debt FROM loans WHERE id=?", (loan_id,)
                )).fetchone()
                if row_loan:
                    l_inst, l_rem = row_loan[0], row_loan[1]
                    import math
                    late_fee = int(math.ceil(l_inst * 0.10 + l_rem * 0.05))
                    await self._db.execute(
                        "UPDATE loans SET missed_installments=missed_installments+1, "
                        "consecutive_misses=consecutive_misses+1, "
                        "accrued_late_fees=accrued_late_fees+?, "
                        "remaining_debt=remaining_debt+?, "
                        "total_owed=total_owed+?, "
                        "next_collection=? WHERE id=?",
                        (late_fee, late_fee, late_fee, next_col, loan_id),
                    )
                else:
                    await self._db.execute(
                        "UPDATE loans SET missed_installments=missed_installments+1, "
                        "consecutive_misses=consecutive_misses+1, "
                        "next_collection=? WHERE id=?",
                        (next_col, loan_id),
                    )
                await self._db.execute(
                    "UPDATE loan_scores SET missed_payments=missed_payments+1, "
                    "score=MAX(0, score-40) WHERE user_id=? AND guild_id=?",
                    (user_id, guild_id),
                )
            await self._safe_commit()

    async def complete_loan(self, loan_id: int, user_id: int, guild_id: int, clean: bool) -> None:
        async with self.write_lock:
            await self._db.execute(
                "UPDATE loans SET status='paid', completed_at=? WHERE id=?",
                (datetime.datetime.now(datetime.timezone.utc).isoformat(), loan_id),
            )
            if clean:
                await self._db.execute(
                    "UPDATE loan_scores SET paid_on_time=paid_on_time+1, score=MIN(1000, score+30) "
                    "WHERE user_id=? AND guild_id=?", (user_id, guild_id),
                )
            await self._safe_commit()

    async def default_loan(self, loan_id: int, user_id: int, guild_id: int) -> None:
        """Marca un préstamo como defaulted. Registra la pérdida en la treasury."""
        # Obtener remaining_debt antes de marcar default
        loan_row = await self.fetchone(
            "SELECT remaining_debt FROM loans WHERE id=?", (loan_id,)
        )
        lost = (loan_row["remaining_debt"] if loan_row else 0) or 0
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if lost > 0:
            await self._ensure_treasury(guild_id)

        async with self.write_lock:
            await self._db.execute(
                "UPDATE loans SET status='defaulted', completed_at=? WHERE id=?",
                (now_iso, loan_id),
            )
            await self._db.execute(
                "UPDATE loan_scores SET defaults_count=defaults_count+1, "
                "score=MAX(0, score-100) WHERE user_id=? AND guild_id=?",
                (user_id, guild_id),
            )
            # Blacklist check
            await self._db.execute(
                "UPDATE loan_scores SET blacklisted=1 WHERE user_id=? AND guild_id=? "
                "AND score=0 AND defaults_count>=2", (user_id, guild_id),
            )
            # Tracking de pérdida (no afecta balance — el dinero ya estaba afuera)
            if lost > 0:
                await self._db.execute(
                    "UPDATE guild_treasury SET total_lost_defaults=total_lost_defaults+?, "
                    "last_modified=? WHERE guild_id=?",
                    (lost, now_iso, guild_id),
                )
                row = await (await self._db.execute(
                    "SELECT balance FROM guild_treasury WHERE guild_id=?", (guild_id,)
                )).fetchone()
                cur_bal = row[0] if row else 0
                await self._db.execute(
                    "INSERT INTO guild_treasury_movements "
                    "(guild_id, amount, balance_after, reason, metadata, user_id, by_staff_id, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (guild_id, 0, cur_bal, "loan_default",
                     f'{{"loan_id": {loan_id}, "lost": {lost}}}',
                     user_id, None, now_iso),
                )
            await self._safe_commit()

    # ── Treasury (Y O U K A I · B A N K) ──────────────────────────────────

    DEFAULT_TREASURY_BOOTSTRAP = 6000

    async def _ensure_treasury(self, guild_id: int) -> None:
        """Crea la fila de treasury si no existe (bootstrap idempotente con 6000 cr)."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self.write_lock:
            row = await (await self._db.execute(
                "SELECT 1 FROM guild_treasury WHERE guild_id=?", (guild_id,)
            )).fetchone()
            if row:
                return
            await self._db.execute(
                "INSERT OR IGNORE INTO guild_treasury "
                "(guild_id, balance, bootstrap_amount, created_at, last_modified) "
                "VALUES (?,?,?,?,?)",
                (guild_id, self.DEFAULT_TREASURY_BOOTSTRAP, self.DEFAULT_TREASURY_BOOTSTRAP,
                 now_iso, now_iso),
            )
            # Solo registrar el movimiento si efectivamente acabamos de crearlo
            inserted = await (await self._db.execute(
                "SELECT changes() AS c"
            )).fetchone()
            if inserted and inserted[0] > 0:
                await self._db.execute(
                    "INSERT INTO guild_treasury_movements "
                    "(guild_id, amount, balance_after, reason, metadata, user_id, by_staff_id, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (guild_id, self.DEFAULT_TREASURY_BOOTSTRAP, self.DEFAULT_TREASURY_BOOTSTRAP,
                     "bootstrap", '{"reason": "initial_pool"}', None, None, now_iso),
                )
            await self._safe_commit()

    async def get_treasury(self, guild_id: int) -> dict:
        """Estado completo de la treasury del guild."""
        await self._ensure_treasury(guild_id)
        row = await self.fetchone(
            "SELECT * FROM guild_treasury WHERE guild_id=?", (guild_id,)
        )
        return dict(row) if row else {
            "guild_id": guild_id, "balance": 0, "total_collected": 0,
            "total_disbursed": 0, "total_lost_defaults": 0,
            "bootstrap_amount": 0, "created_at": "", "last_modified": "",
        }

    async def add_to_treasury(self, guild_id: int, amount: int, reason: str,
                              metadata_json: str | None = None,
                              user_id: int | None = None,
                              by_staff_id: int | None = None) -> int:
        """Deposita ``amount`` cr en la treasury. Retorna el nuevo balance."""
        if amount <= 0:
            cur = await self.get_treasury(guild_id)
            return cur["balance"]
        await self._ensure_treasury(guild_id)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self.write_lock:
            await self._db.execute(
                "UPDATE guild_treasury SET balance=balance+?, total_collected=total_collected+?, "
                "last_modified=? WHERE guild_id=?",
                (amount, amount, now_iso, guild_id),
            )
            row = await (await self._db.execute(
                "SELECT balance FROM guild_treasury WHERE guild_id=?", (guild_id,)
            )).fetchone()
            new_bal = row[0] if row else amount
            await self._db.execute(
                "INSERT INTO guild_treasury_movements "
                "(guild_id, amount, balance_after, reason, metadata, user_id, by_staff_id, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (guild_id, amount, new_bal, reason, metadata_json, user_id, by_staff_id, now_iso),
            )
            await self._safe_commit()
            return new_bal

    async def spend_from_treasury(self, guild_id: int, amount: int, reason: str,
                                  metadata_json: str | None = None,
                                  user_id: int | None = None,
                                  by_staff_id: int | None = None) -> tuple[bool, int]:
        """Retira ``amount`` cr de la treasury si hay fondos. Retorna (success, new_balance)."""
        if amount <= 0:
            cur = await self.get_treasury(guild_id)
            return False, cur["balance"]
        await self._ensure_treasury(guild_id)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self.write_lock:
            row = await (await self._db.execute(
                "SELECT balance FROM guild_treasury WHERE guild_id=?", (guild_id,)
            )).fetchone()
            cur_bal = row[0] if row else 0
            if cur_bal < amount:
                return False, cur_bal
            new_bal = cur_bal - amount
            await self._db.execute(
                "UPDATE guild_treasury SET balance=?, total_disbursed=total_disbursed+?, "
                "last_modified=? WHERE guild_id=?",
                (new_bal, amount, now_iso, guild_id),
            )
            await self._db.execute(
                "INSERT INTO guild_treasury_movements "
                "(guild_id, amount, balance_after, reason, metadata, user_id, by_staff_id, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (guild_id, -amount, new_bal, reason, metadata_json, user_id, by_staff_id, now_iso),
            )
            await self._safe_commit()
            return True, new_bal

    async def get_treasury_history(self, guild_id: int, limit: int = 25,
                                   reason_filter: str | None = None) -> list[dict]:
        """Últimos movimientos de la treasury (más recientes primero)."""
        if reason_filter:
            rows = await self.fetch(
                "SELECT * FROM guild_treasury_movements "
                "WHERE guild_id=? AND reason=? ORDER BY created_at DESC LIMIT ?",
                (guild_id, reason_filter, max(1, min(200, limit))),
            )
        else:
            rows = await self.fetch(
                "SELECT * FROM guild_treasury_movements "
                "WHERE guild_id=? ORDER BY created_at DESC LIMIT ?",
                (guild_id, max(1, min(200, limit))),
            )
        return [dict(r) for r in rows]

    async def get_treasury_stats(self, guild_id: int) -> dict:
        """Stats agregadas de la treasury del guild."""
        treasury = await self.get_treasury(guild_id)
        # Top reasons by absolute amount
        rows = await self.fetch(
            "SELECT reason, COUNT(*) as count, SUM(amount) as total "
            "FROM guild_treasury_movements WHERE guild_id=? "
            "GROUP BY reason ORDER BY ABS(SUM(amount)) DESC",
            (guild_id,),
        )
        breakdown = [{"reason": r["reason"], "count": r["count"], "total": r["total"]}
                     for r in rows]
        # Outstanding loans = total disbursed - what's been repaid
        active_principal_row = await self.fetchone(
            "SELECT COALESCE(SUM(remaining_debt), 0) AS outstanding FROM loans "
            "WHERE guild_id=? AND status='active'", (guild_id,),
        )
        return {
            "balance": treasury["balance"],
            "total_collected": treasury["total_collected"],
            "total_disbursed": treasury["total_disbursed"],
            "total_lost_defaults": treasury["total_lost_defaults"],
            "bootstrap_amount": treasury["bootstrap_amount"],
            "outstanding_debt": (active_principal_row or {}).get("outstanding", 0) or 0,
            "net_profit": treasury["total_collected"] - treasury["total_disbursed"],
            "breakdown": breakdown,
        }

    async def get_treasury_liquidity_info(self, guild_id: int) -> tuple[int, int]:
        """Retorna (balance_disponible, capital_total).
        capital_total = bootstrap_amount + total_shares.
        """
        await self._ensure_treasury(guild_id)
        row = await self.fetchone(
            "SELECT balance, bootstrap_amount, total_shares FROM guild_treasury WHERE guild_id=?",
            (guild_id,)
        )
        if row:
            balance = row["balance"]
            bootstrap = row["bootstrap_amount"]
            total_shares = row["total_shares"]
            capital_total = max(1, bootstrap + total_shares)
            return balance, capital_total
        return 6000, 6000

    async def invest_in_treasury(self, user_id: int, guild_id: int, amount: int) -> int:
        """Invierte amount créditos de la cuenta del usuario en la caja.
        Retorna la cantidad total de acciones que posee el usuario ahora.
        """
        if amount <= 0:
            raise ValueError("El monto a depositar debe ser mayor que cero.")
        await self._ensure_treasury(guild_id)
        today = __import__("datetime").date.today().isoformat()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self.write_lock:
            row_user = await self.fetchone(
                "SELECT balance FROM user_credits WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            )
            user_bal = row_user["balance"] if row_user else 0
            if user_bal < amount:
                raise ValueError("Saldo de créditos insuficiente para realizar la inversión.")

            # Restar créditos al usuario
            new_user_bal = user_bal - amount
            await self._db.execute(
                "UPDATE user_credits SET balance=? WHERE user_id=? AND guild_id=?",
                (new_user_bal, user_id, guild_id)
            )
            await self._ledger_inside_transaction(user_id, guild_id, -amount, new_user_bal, "invest_deposit", "")

            # Sumar balance y total_shares al banco
            await self._db.execute(
                "UPDATE guild_treasury SET balance=balance+?, total_shares=total_shares+?, last_modified=? WHERE guild_id=?",
                (amount, amount, now_iso, guild_id)
            )

            # Actualizar acciones del usuario
            await self._db.execute(
                "INSERT INTO treasury_shares (user_id, guild_id, shares, unclaimed_dividends) "
                "VALUES (?, ?, ?, 0.0) ON CONFLICT(user_id, guild_id) DO UPDATE SET shares=shares+?",
                (user_id, guild_id, amount, amount)
            )

            # Registrar movimiento del banco
            row_treasury = await (await self._db.execute(
                "SELECT balance FROM guild_treasury WHERE guild_id=?", (guild_id,)
            )).fetchone()
            t_bal = row_treasury[0] if row_treasury else amount
            await self._db.execute(
                "INSERT INTO guild_treasury_movements "
                "(guild_id, amount, balance_after, reason, metadata, user_id, by_staff_id, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (guild_id, amount, t_bal, "invest_deposit", f'{{"shares_purchased": {amount}}}', user_id, None, now_iso)
            )

            row_shares = await self.fetchone(
                "SELECT shares FROM treasury_shares WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            )
            new_shares = row_shares["shares"] if row_shares else 0
            await self._safe_commit()
            return new_shares

    async def withdraw_from_treasury(self, user_id: int, guild_id: int, amount: int) -> int:
        """Retira amount acciones de la caja y las convierte a créditos.
        Retorna las acciones restantes del usuario.
        Falla si el usuario no tiene suficientes acciones o la caja no tiene liquidez.
        """
        if amount <= 0:
            raise ValueError("El monto a retirar debe ser mayor que cero.")
        await self._ensure_treasury(guild_id)
        today = __import__("datetime").date.today().isoformat()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self.write_lock:
            row_shares = await self.fetchone(
                "SELECT shares FROM treasury_shares WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            )
            user_shares = row_shares["shares"] if row_shares else 0
            if user_shares < amount:
                raise ValueError("No tienes suficientes acciones para retirar esa cantidad.")

            row_treasury = await (await self._db.execute(
                "SELECT balance FROM guild_treasury WHERE guild_id=?", (guild_id,)
            )).fetchone()
            t_bal = row_treasury[0] if row_treasury else 0
            if t_bal < amount:
                raise ValueError("La caja de la guild no cuenta con suficiente liquidez disponible en este momento.")

            # Restar acciones
            new_user_shares = user_shares - amount
            await self._db.execute(
                "UPDATE treasury_shares SET shares=? WHERE user_id=? AND guild_id=?",
                (new_user_shares, user_id, guild_id)
            )

            # Restar balance y total_shares del banco
            new_t_bal = t_bal - amount
            await self._db.execute(
                "UPDATE guild_treasury SET balance=?, total_shares=MAX(0, total_shares-?), last_modified=? WHERE guild_id=?",
                (new_t_bal, amount, now_iso, guild_id)
            )

            # Acreditar al usuario
            await self._db.execute(
                "INSERT OR IGNORE INTO user_credits (user_id, guild_id, balance, earned_today, last_reset) VALUES (?,?,0,0,?)",
                (user_id, guild_id, today)
            )
            await self._db.execute(
                "UPDATE user_credits SET balance=balance+? WHERE user_id=? AND guild_id=?",
                (amount, user_id, guild_id)
            )
            row_user = await self.fetchone(
                "SELECT balance FROM user_credits WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            )
            new_user_bal = row_user["balance"] if row_user else amount
            await self._ledger_inside_transaction(user_id, guild_id, amount, new_user_bal, "invest_withdraw", "")

            # Registrar movimiento
            await self._db.execute(
                "INSERT INTO guild_treasury_movements "
                "(guild_id, amount, balance_after, reason, metadata, user_id, by_staff_id, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (guild_id, -amount, new_t_bal, "invest_withdrawal", f'{{"shares_withdrawn": {amount}}}', user_id, None, now_iso)
            )

            await self._safe_commit()
            return new_user_shares

    async def claim_dividends(self, user_id: int, guild_id: int) -> int:
        """Reclama la porción entera de los dividendos acumulados por el usuario.
        Abona a créditos del usuario, resta del balance de la caja y registra la transacción.
        Retorna la cantidad reclamada de créditos.
        """
        await self._ensure_treasury(guild_id)
        today = __import__("datetime").date.today().isoformat()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self.write_lock:
            row_shares = await self.fetchone(
                "SELECT unclaimed_dividends FROM treasury_shares WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            )
            unclaimed = row_shares["unclaimed_dividends"] if row_shares else 0.0
            if unclaimed < 1.0:
                return 0

            claim_amount = int(unclaimed)

            row_treasury = await (await self._db.execute(
                "SELECT balance FROM guild_treasury WHERE guild_id=?", (guild_id,)
            )).fetchone()
            t_bal = row_treasury[0] if row_treasury else 0
            if t_bal < claim_amount:
                claim_amount = t_bal
                if claim_amount <= 0:
                    return 0

            remaining_unclaimed = unclaimed - claim_amount
            await self._db.execute(
                "UPDATE treasury_shares SET unclaimed_dividends=? WHERE user_id=? AND guild_id=?",
                (remaining_unclaimed, user_id, guild_id)
            )

            new_t_bal = t_bal - claim_amount
            await self._db.execute(
                "UPDATE guild_treasury SET balance=?, total_dividends_paid=total_dividends_paid+?, last_modified=? WHERE guild_id=?",
                (new_t_bal, claim_amount, now_iso, guild_id)
            )

            await self._db.execute(
                "INSERT OR IGNORE INTO user_credits (user_id, guild_id, balance, earned_today, last_reset) VALUES (?,?,0,0,?)",
                (user_id, guild_id, today)
            )
            await self._db.execute(
                "UPDATE user_credits SET balance=balance+? WHERE user_id=? AND guild_id=?",
                (claim_amount, user_id, guild_id)
            )
            row_user = await self.fetchone(
                "SELECT balance FROM user_credits WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            )
            new_user_bal = row_user["balance"] if row_user else claim_amount
            await self._ledger_inside_transaction(user_id, guild_id, claim_amount, new_user_bal, "claim_dividends", "")

            await self._db.execute(
                "INSERT INTO guild_treasury_movements "
                "(guild_id, amount, balance_after, reason, metadata, user_id, by_staff_id, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (guild_id, -claim_amount, new_t_bal, "dividend_payout", f'{{"claimed_amount": {claim_amount}}}', user_id, None, now_iso)
            )

            await self._safe_commit()
            return claim_amount

    # ── Knowledge Base (Interactive RAG) ─────────────────────────────────────

    async def kb_store(self, guild_id: int, key: str, content: str,
                       tags: str = "", scope: str = "guild",
                       author_id: int = 0, embedding: bytes = None) -> int:
        """Store a knowledge entry. Returns the new row ID."""
        now = int(time.time())
        async with self.write_lock:
            cur = await self._db.execute(
                "INSERT INTO knowledge_base (guild_id, key, content, tags, scope, author_id, embedding, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (guild_id, key, content, tags, scope, author_id, embedding, now, now),
            )
            await self._safe_commit()
            return cur.lastrowid

    async def kb_update(self, guild_id: int, key: str, content: str,
                        tags: str = None, embedding: bytes = None) -> bool:
        """Update an existing entry by key. Returns True if found."""
        now = int(time.time())
        sets = ["content = ?", "updated_at = ?"]
        params = [content, now]
        if tags is not None:
            sets.append("tags = ?")
            params.append(tags)
        if embedding is not None:
            sets.append("embedding = ?")
            params.append(embedding)
        params += [guild_id, key]
        async with self.write_lock:
            cur = await self._db.execute(
                f"UPDATE knowledge_base SET {', '.join(sets)} WHERE guild_id = ? AND key = ?",
                params,
            )
            await self._safe_commit()
            return cur.rowcount > 0

    async def kb_delete(self, guild_id: int, key: str) -> bool:
        """Delete entry by key."""
        async with self.write_lock:
            cur = await self._db.execute(
                "DELETE FROM knowledge_base WHERE guild_id = ? AND key = ?",
                (guild_id, key),
            )
            await self._safe_commit()
            return cur.rowcount > 0

    async def kb_search(self, guild_id: int, query: str, limit: int = 5) -> List[Dict]:
        """FTS-like search over knowledge_base using LIKE + tag matching."""
        query_lower = query.lower()
        terms = [t.strip() for t in query_lower.split() if len(t.strip()) > 2]
        if not terms:
            return []

        # Build WHERE with OR conditions on content, key, tags
        conditions = []
        params = [guild_id]
        for term in terms[:5]:
            conditions.append("(LOWER(content) LIKE ? OR LOWER(key) LIKE ? OR LOWER(tags) LIKE ?)")
            params += [f"%{term}%", f"%{term}%", f"%{term}%"]

        where = " OR ".join(conditions)
        params.append(limit * 3)  # fetch more, then rank

        rows = await self.fetch(
            f"SELECT id, key, content, tags, scope, created_at, updated_at "
            f"FROM knowledge_base WHERE guild_id = ? AND ({where}) "
            f"ORDER BY updated_at DESC LIMIT ?",
            tuple(params),
        )

        # Simple relevance scoring: count term hits
        scored = []
        for row in rows:
            text = f"{row['key']} {row['content']} {row['tags']}".lower()
            score = sum(1 for t in terms if t in text)
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]

    async def kb_search_semantic(self, guild_id: int, query_embedding: bytes,
                                 limit: int = 5) -> List[Dict]:
        """Vector KNN search over knowledge_base embeddings."""
        if not self._vec_available:
            return []
        try:
            async with self._db.execute(
                "SELECT id, distance FROM vec_knowledge "
                "WHERE guild_id = ? AND embedding MATCH ? "
                "ORDER BY distance LIMIT ?",
                (guild_id, query_embedding, limit),
            ) as cur:
                vec_results = {row["id"]: row["distance"] for row in await cur.fetchall()}
            if not vec_results:
                return []
            ids = list(vec_results.keys())
            placeholders = ",".join("?" * len(ids))
            return await self.fetch(
                f"SELECT id, key, content, tags, scope, created_at, updated_at "
                f"FROM knowledge_base WHERE id IN ({placeholders})",
                tuple(ids),
            )
        except Exception:
            return []

    async def kb_get(self, guild_id: int, key: str) -> Optional[Dict]:
        """Get single entry by exact key."""
        return await self.fetchone(
            "SELECT id, key, content, tags, scope, created_at, updated_at "
            "FROM knowledge_base WHERE guild_id = ? AND key = ?",
            (guild_id, key),
        )

    async def kb_count(self, guild_id: int) -> int:
        row = await self.fetchone(
            "SELECT COUNT(*) as c FROM knowledge_base WHERE guild_id = ?",
            (guild_id,),
        )
        return row["c"] if row else 0

    async def kb_bulk_insert(self, rows: List[tuple]) -> int:
        """Bulk insert: rows = [(guild_id, key, content, tags, scope, author_id, embedding, created_at, updated_at), ...]"""
        async with self.write_lock:
            await self._db.executemany(
                "INSERT OR IGNORE INTO knowledge_base "
                "(guild_id, key, content, tags, scope, author_id, embedding, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            await self._safe_commit()
        return len(rows)

    # ── Shop / Redeemables ─────────────────────────────────────────────────

    async def shop_create(self, guild_id: int, name: str, price: int, type_: str,
                          description: str = "", payload: str = "{}",
                          stock: int = -1, duration_hours: int = 0,
                          category: str = "", created_by: int = 0) -> int:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        async with self.write_lock:
            cur = await self._db.execute(
                "INSERT INTO shop_items (guild_id, name, description, price, type, category, payload, stock, duration_hours, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (guild_id, name, description, price, type_, category, payload, stock, duration_hours, created_by, now),
            )
            await self._safe_commit()
            return cur.lastrowid

    async def shop_list(self, guild_id: int, active_only: bool = True) -> list:
        q = "SELECT * FROM shop_items WHERE guild_id = ?"
        if active_only:
            q += " AND active = 1"
        q += " ORDER BY price"
        return await self.fetch(q, (guild_id,))

    async def shop_get(self, item_id: int) -> Optional[dict]:
        return await self.fetchone("SELECT * FROM shop_items WHERE id = ?", (item_id,))

    async def shop_toggle(self, item_id: int, active: bool) -> bool:
        async with self.write_lock:
            cur = await self._db.execute(
                "UPDATE shop_items SET active = ? WHERE id = ?", (int(active), item_id)
            )
            await self._safe_commit()
            return cur.rowcount > 0

    async def shop_delete(self, item_id: int) -> bool:
        async with self.write_lock:
            cur = await self._db.execute("DELETE FROM shop_items WHERE id = ?", (item_id,))
            await self._safe_commit()
            return cur.rowcount > 0

    async def shop_update(self, item_id: int, **fields) -> bool:
        allowed = {"name", "description", "price", "payload", "stock", "active", "type", "duration_hours", "category"}
        sets = [(k, v) for k, v in fields.items() if k in allowed]
        if not sets:
            return False
        sql = "UPDATE shop_items SET " + ", ".join(f"{k}=?" for k, _ in sets) + " WHERE id=?"
        async with self.write_lock:
            cur = await self._db.execute(sql, [v for _, v in sets] + [item_id])
            await self._safe_commit()
            return cur.rowcount > 0

    async def shop_redeem(self, guild_id: int, user_id: int, item_id: int) -> tuple[bool, str]:
        """Attempt redemption. Returns (success, message). Duration stacks if re-purchased."""
        from datetime import datetime, timezone, timedelta
        item = await self.shop_get(item_id)
        if not item:
            return False, "Item no encontrado."
        if not item["active"]:
            return False, "Item no disponible."
        if item["guild_id"] != guild_id:
            return False, "Item de otro servidor."
        if item["stock"] != -1 and item["redeemed_count"] >= item["stock"]:
            return False, "Agotado."
        # Check balance
        info = await self.get_credits(user_id, guild_id)
        if info["balance"] < item["price"]:
            return False, f"Créditos insuficientes ({info['balance']}/{item['price']})."
        # Calculate expires_at (stacking: extend from current expiry if active)
        now = datetime.now(timezone.utc)
        expires_at = None
        duration_h = item.get("duration_hours", 0) or 0
        if duration_h > 0:
            # Check if user has an active (non-expired) redemption for this item
            existing = await self.fetchone(
                "SELECT expires_at FROM redemptions "
                "WHERE guild_id=? AND user_id=? AND item_id=? AND expires_at>? "
                "ORDER BY expires_at DESC LIMIT 1",
                (guild_id, user_id, item_id, now.isoformat()),
            )
            if existing and existing["expires_at"]:
                # Stack: extend from current expiry
                base = datetime.fromisoformat(existing["expires_at"])
            else:
                base = now
            expires_at = (base + timedelta(hours=duration_h)).isoformat()
        # Deduct + log
        async with self.write_lock:
            await self._db.execute(
                "UPDATE user_credits SET balance=balance-? WHERE user_id=? AND guild_id=?",
                (item["price"], user_id, guild_id),
            )
            await self._db.execute(
                "INSERT INTO redemptions (guild_id, user_id, item_id, redeemed_at, expires_at) VALUES (?,?,?,?,?)",
                (guild_id, user_id, item_id, now.isoformat(), expires_at),
            )
            await self._db.execute(
                "UPDATE shop_items SET redeemed_count=redeemed_count+1 WHERE id=?", (item_id,)
            )
            await self._safe_commit()
        msg = "Canjeado exitosamente."
        if expires_at:
            msg += f" Expira: {expires_at[:16].replace('T',' ')}"
        return True, msg

    async def shop_redemptions(self, guild_id: int, user_id: int = None, limit: int = 20) -> list:
        if user_id:
            return await self.fetch(
                "SELECT r.*, s.name as item_name, s.type as item_type FROM redemptions r "
                "JOIN shop_items s ON r.item_id=s.id WHERE r.guild_id=? AND r.user_id=? "
                "ORDER BY r.redeemed_at DESC LIMIT ?", (guild_id, user_id, limit)
            )
        return await self.fetch(
            "SELECT r.*, s.name as item_name, s.type as item_type FROM redemptions r "
            "JOIN shop_items s ON r.item_id=s.id WHERE r.guild_id=? "
            "ORDER BY r.redeemed_at DESC LIMIT ?", (guild_id, limit)
        )

    async def shop_get_expired(self) -> list:
        """Get redemptions that have expired and need role removal."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        return await self.fetch(
            "SELECT r.id, r.guild_id, r.user_id, r.item_id, r.expires_at, "
            "s.payload, s.type FROM redemptions r "
            "JOIN shop_items s ON r.item_id=s.id "
            "WHERE r.expires_at IS NOT NULL AND r.expires_at <= ? AND s.type='role'",
            (now,),
        )

    async def shop_delete_redemption(self, redemption_id: int) -> None:
        async with self.write_lock:
            await self._db.execute("DELETE FROM redemptions WHERE id=?", (redemption_id,))
            await self._safe_commit()

    # ── Economy Stats ──────────────────────────────────────────────────────

    async def economy_stats(self, guild_id: int) -> dict:
        """Get economy overview stats."""
        today = __import__("datetime").date.today().isoformat()
        # Total credits in circulation
        row = await self.fetchone(
            "SELECT SUM(balance) as total, COUNT(*) as users FROM user_credits WHERE guild_id=?",
            (guild_id,),
        )
        total_credits = row["total"] or 0 if row else 0
        total_users = row["users"] or 0 if row else 0
        # Today's earning
        row = await self.fetchone(
            "SELECT SUM(earned_today) as earned, SUM(spent_today) as spent "
            "FROM user_credits WHERE guild_id=? AND last_reset=?",
            (guild_id, today),
        )
        earned_today = row["earned"] or 0 if row else 0
        spent_today = row["spent"] or 0 if row else 0
        # Top earners today
        top = await self.fetch(
            "SELECT user_id, earned_today FROM user_credits "
            "WHERE guild_id=? AND last_reset=? AND earned_today>0 ORDER BY earned_today DESC LIMIT 5",
            (guild_id, today),
        )
        return {
            "total_in_circulation": total_credits,
            "total_users": total_users,
            "earned_today": earned_today,
            "spent_today": spent_today,
            "top_earners_today": [{"user_id": r["user_id"], "earned": r["earned_today"]} for r in top],
        }

    # ── Active Award ──────────────────────────────────────────────────────────

    async def has_active_award_run(self, guild_id: int, year: int, month: int) -> bool:
        """Check if a monthly active award has already been run."""
        row = await self.fetchone(
            "SELECT 1 FROM active_award_runs WHERE guild_id = ? AND year = ? AND month = ?",
            (guild_id, year, month)
        )
        return row is not None

    async def record_active_award_run(self, guild_id: int, year: int, month: int, user_id: int) -> None:
        """Record that a monthly active award run occurred."""
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with self.write_lock:
            await self._db.execute(
                "INSERT INTO active_award_runs (guild_id, year, month, user_id, run_at) VALUES (?, ?, ?, ?, ?)",
                (guild_id, year, month, user_id, now_iso)
            )
            await self._safe_commit()

    async def get_most_active_user(self, guild_id: int, start_ts: int, end_ts: int) -> Optional[Dict]:
        """Get the most active user in a given time range."""
        return await self.fetchone(
            "SELECT user_id, username, COUNT(*) as msg_count "
            "FROM messages "
            "WHERE guild_id = ? AND timestamp >= ? AND timestamp <= ? "
            "GROUP BY user_id "
            "ORDER BY msg_count DESC "
            "LIMIT 1",
            (guild_id, start_ts, end_ts)
        )

    async def get_most_active_users(self, guild_id: int, start_ts: int, end_ts: int, limit: int = 50) -> List[Dict]:
        """Get the most active users list in a given time range."""
        rows = await self.fetch(
            "SELECT user_id, username, COUNT(*) as msg_count "
            "FROM messages "
            "WHERE guild_id = ? AND timestamp >= ? AND timestamp <= ? "
            "GROUP BY user_id "
            "ORDER BY msg_count DESC "
            "LIMIT ?",
            (guild_id, start_ts, end_ts, limit)
        )
        return [dict(r) for r in rows]

    # ── Role Persistence ──────────────────────────────────────────────────────

    async def get_persisted_roles(self, guild_id: int, user_id: int) -> List[int]:
        """Get the persisted role IDs for a member in a guild."""
        row = await self.fetchone(
            "SELECT role_ids FROM member_roles_persistence WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        if not row or not row["role_ids"]:
            return []
        try:
            return [int(r) for r in row["role_ids"].split(",") if r.strip()]
        except ValueError:
            return []

    async def save_persisted_roles(self, guild_id: int, user_id: int, role_ids: List[int]) -> None:
        """Save/overwrite persisted role IDs for a member in a guild."""
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        role_ids_str = ",".join(map(str, role_ids))
        async with self.write_lock:
            await self._db.execute(
                "INSERT OR REPLACE INTO member_roles_persistence (guild_id, user_id, role_ids, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (guild_id, user_id, role_ids_str, now_iso)
            )
            await self._safe_commit()

    async def bulk_save_persisted_roles(self, guild_id: int, data: List[Tuple[int, List[int]]]) -> None:
        """Save persisted roles for multiple members in a single transaction."""
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        params = [
            (guild_id, user_id, ",".join(map(str, role_ids)), now_iso)
            for user_id, role_ids in data
        ]
        async with self.write_lock:
            await self._db.executemany(
                "INSERT OR REPLACE INTO member_roles_persistence (guild_id, user_id, role_ids, updated_at) "
                "VALUES (?, ?, ?, ?)",
                params
            )
            await self._safe_commit()

    async def clear_persisted_roles(self, guild_id: int, user_id: int) -> None:
        """Clear persisted roles for a member in a guild."""
        async with self.write_lock:
            await self._db.execute(
                "DELETE FROM member_roles_persistence WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            await self._safe_commit()

    # ── Contadores de Acciones de Rol ────────────────────────────────────────

    async def increment_action_count(self, guild_id: int, user_id: int, action_type: str) -> int:
        """Increments the received action count for a user in a guild, returning the new count."""
        async with self.write_lock:
            await self._db.execute(
                "INSERT INTO user_action_counters (guild_id, user_id, action_type, count) "
                "VALUES (?, ?, ?, 1) "
                "ON CONFLICT(guild_id, user_id, action_type) DO UPDATE SET count = count + 1",
                (guild_id, user_id, action_type)
            )
            await self._safe_commit()
            
            cursor = await self._db.execute(
                "SELECT count FROM user_action_counters WHERE guild_id = ? AND user_id = ? AND action_type = ?",
                (guild_id, user_id, action_type)
            )
            row = await cursor.fetchone()
            return row[0] if row else 1

    async def get_action_count(self, guild_id: int, user_id: int, action_type: str) -> int:
        """Returns the received action count for a user in a guild."""
        cursor = await self._db.execute(
            "SELECT count FROM user_action_counters WHERE guild_id = ? AND user_id = ? AND action_type = ?",
            (guild_id, user_id, action_type)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


    # ── Lifecycle ──────────────────────────────────────────────────────────
    
    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None