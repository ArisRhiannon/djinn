"""Backtest del motor automod v3 sobre el histórico REAL de mensajes.

Reproduce todos los mensajes de db/fairy.db (solo-lectura) a través del motor,
en orden cronológico, reconstruyendo la reputación de cada usuario AL MOMENTO
de cada mensaje (msg_count acumulado + antigüedad desde su 1er mensaje visto).

Objetivo: validar 0-FP empíricamente. En tráfico real, casi todo debe ser
ALLOW/OBSERVE; cualquier PUNITIVE/QUARANTINE es un candidato a falso positivo
para auditar.

Uso: python scripts/automod3_replay.py [db_path] [--limit N] [--show K]
"""

from __future__ import annotations

import collections
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3

from utils.automod3 import AccountContext, Action, Engine, MessageContext

_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_INVITE = re.compile(
    r"(?:discord\.(?:gg|com/invite)|discordapp\.com/invite|dsc\.gg|discord\.me)/\S+",
    re.IGNORECASE,
)
_DISCORD_EPOCH_MS = 1420070400000

try:
    from utils.safe_domains import is_safe_domain
except Exception:
    def is_safe_domain(_h):  # fallback: trata todo link como no-safe
        return False


def account_age_days(uid: int, now: float) -> float:
    created_ms = (uid >> 22) + _DISCORD_EPOCH_MS
    return max(0.0, (now - created_ms / 1000) / 86400)


def main() -> None:
    args = sys.argv[1:]
    db_path = next((a for a in args if not a.startswith("--")), "db/fairy.db")
    limit = next((int(a.split("=")[1]) for a in args if a.startswith("--limit=")), None)
    show = next((int(a.split("=")[1]) for a in args if a.startswith("--show=")), 25)

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    eng = Engine()
    first_ts: dict[int, float] = {}
    msg_count: dict[int, int] = collections.defaultdict(int)
    dist: collections.Counter = collections.Counter()
    reason_counts: collections.Counter = collections.Counter()
    samples: dict[str, list] = collections.defaultdict(list)

    q = "SELECT guild_id,channel_id,user_id,username,content,reply_to_id,timestamp FROM messages ORDER BY timestamp ASC"
    if limit:
        q += f" LIMIT {limit}"

    n = 0
    t0 = time.perf_counter()
    for r in cur.execute(q):
        uid = r["user_id"]
        ts = float(r["timestamp"] or 0)
        content = r["content"] or ""
        if uid not in first_ts:
            first_ts[uid] = ts
        server_age = max(0.0, (ts - first_ts[uid]) / 86400)

        invites = _INVITE.findall(content)
        unsafe = [u for u in _URL.findall(content)
                  if not _INVITE.search(u)
                  and (lambda h: h and not is_safe_domain(h))(_host(u))]

        acc = AccountContext(
            user_id=uid,
            account_age_days=account_age_days(uid, ts),
            server_age_days=server_age,
            msg_count=msg_count[uid],
            is_staff=False,  # histórico: desconocido → evaluar a todos (conservador)
        )
        ctx = MessageContext(
            guild_id=r["guild_id"], channel_id=r["channel_id"], message_id=r["id"] if "id" in r.keys() else n,
            author=acc, content=content, created_at=ts,
            mentions_everyone=("@everyone" in content or "@here" in content),
            invite_urls=tuple(invites), external_invite=bool(invites),
            unsafe_links=tuple(unsafe), is_reply=r["reply_to_id"] is not None,
        )

        d = eng.evaluate(ctx)
        dist[d.action.name] += 1
        msg_count[uid] += 1
        n += 1

        if d.action >= Action.SOFT:  # SOFT/QUARANTINE/HOLD/PUNITIVE → auditar
            for k in d.keys:
                reason_counts[k.name] += 1
            bucket = samples[d.action.name]
            if len(bucket) < show:
                bucket.append((r["username"], content[:80].replace("\n", " "),
                               [k.name for k in d.keys], round(acc.account_age_days, 1),
                               round(server_age, 1), acc.msg_count))

    con.close()
    elapsed = time.perf_counter() - t0

    print(f"\n=== Backtest automod v3 sobre {n:,} mensajes reales ({elapsed:.1f}s) ===\n")
    print("Distribución de acciones (qué HARÍA el motor):")
    for action in ("ALLOW", "OBSERVE", "SOFT", "QUARANTINE", "HOLD", "PUNITIVE"):
        c = dist.get(action, 0)
        pct = 100 * c / n if n else 0
        print(f"  {action:<11} {c:>8,}  ({pct:6.3f}%)")
    actionable = sum(dist.get(a, 0) for a in ("SOFT", "QUARANTINE", "HOLD", "PUNITIVE"))
    print(f"\n  Mensajes con ALGUNA acción: {actionable:,} ({100*actionable/n if n else 0:.3f}%)")
    print(f"  Punitivos (timeout): {dist.get('PUNITIVE',0):,} "
          f"({100*dist.get('PUNITIVE',0)/n if n else 0:.4f}%)")

    if reason_counts:
        print("\nSeñales (llaves) que dispararon acción:")
        for name, c in reason_counts.most_common():
            print(f"  {name:<22} {c:,}")

    for action in ("PUNITIVE", "QUARANTINE", "HOLD", "SOFT"):
        if samples.get(action):
            print(f"\n── Ejemplos {action} (auditar para falsos positivos) ──")
            for user, c, keys, acc_age, srv_age, mc in samples[action]:
                print(f"  [{user}] acc={acc_age}d srv={srv_age}d msgs={mc} keys={keys}")
                print(f"      {c!r}")


def _host(url: str) -> str:
    from urllib.parse import urlparse
    try:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


if __name__ == "__main__":
    main()
