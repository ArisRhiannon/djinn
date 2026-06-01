"""
ZZZ Calendar — datos del calendario de eventos y banners.

Fuente principal: archivo `config.json` curado (porque la API de hoyoverse no
expone calendar para ZZZ y la wiki tiene fases con fechas placeholder).
Fuente secundaria: hoyoverse-api `/news/events` para eventos dinámicos extra.

Modelo:
    CalendarData
      ├── version: str         "2.8"
      ├── title: str           "New: Eridan Sunset"
      ├── start: datetime
      ├── end: datetime
      ├── exclusive_channels: list[Banner]
      ├── wengine_channels: list[Banner]
      ├── login_events: list[Event]
      ├── permanent_events: list[Event]
      ├── battle_pass: Event | None
      └── other_events: list[Event]
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("djinn.zzz_calendar.data")


@dataclass
class Banner:
    """Banner de Exclusive Channel o W-Engine Channel."""
    name: str                       # "Mellow Waveride"
    main: str                       # "Ellen Joe"  (S-rank principal o W-engine)
    side: list[str] = field(default_factory=list)  # ["Soukaku", "Anton"]
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    is_wengine: bool = False        # True si es banner de W-Engine
    rarity: str = "S"               # "S" o "A"


@dataclass
class Event:
    """Evento genérico (login, permanent, other, battle pass)."""
    name: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    rewards: list[str] = field(default_factory=list)  # iconos opcionales
    permanent: bool = False
    new: bool = False               # marcar con badge "NEW!"
    description: Optional[str] = None


@dataclass
class CalendarData:
    """Snapshot completo del calendario para una versión."""
    version: str
    title: str
    start: datetime
    end: datetime
    exclusive_channels: list[Banner] = field(default_factory=list)
    wengine_channels: list[Banner] = field(default_factory=list)
    login_events: list[Event] = field(default_factory=list)
    permanent_events: list[Event] = field(default_factory=list)
    battle_pass: Optional[Event] = None
    other_events: list[Event] = field(default_factory=list)

    @property
    def num_weeks(self) -> int:
        """Cuántas semanas dura la versión (para grid del calendario)."""
        delta = self.end - self.start
        return max(1, (delta.days + 6) // 7)

    def week_ranges(self) -> list[tuple[datetime, datetime]]:
        """Lista de (inicio_semana, fin_semana) cubriendo toda la versión."""
        ranges = []
        cur = self.start
        for i in range(self.num_weeks):
            week_end = min(cur.replace(hour=23, minute=59, second=59) +
                           __import__('datetime').timedelta(days=6), self.end)
            ranges.append((cur, week_end))
            cur = cur + __import__('datetime').timedelta(days=7)
            cur = cur.replace(hour=0, minute=0, second=0)
        return ranges


def _parse_dt(s: str) -> datetime:
    """Parsea string ISO (YYYY-MM-DD o con hora) a datetime UTC."""
    if "T" in s:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def load_calendar(config_path: Path | str) -> CalendarData:
    """Carga el calendario desde el JSON de config."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Calendar config not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    def _banner(b: dict, is_we: bool = False) -> Banner:
        return Banner(
            name=b["name"],
            main=b["main"],
            side=b.get("side", []),
            start=_parse_dt(b["start"]) if b.get("start") else None,
            end=_parse_dt(b["end"]) if b.get("end") else None,
            is_wengine=is_we,
            rarity=b.get("rarity", "S"),
        )

    def _event(e: dict) -> Event:
        return Event(
            name=e["name"],
            start=_parse_dt(e["start"]) if e.get("start") else None,
            end=_parse_dt(e["end"]) if e.get("end") else None,
            rewards=e.get("rewards", []),
            permanent=e.get("permanent", False),
            new=e.get("new", False),
            description=e.get("description"),
        )

    bp = data.get("battle_pass")
    return CalendarData(
        version=data["version"],
        title=data["title"],
        start=_parse_dt(data["start"]),
        end=_parse_dt(data["end"]),
        exclusive_channels=[_banner(b, is_we=False) for b in data.get("exclusive_channels", [])],
        wengine_channels=[_banner(b, is_we=True) for b in data.get("wengine_channels", [])],
        login_events=[_event(e) for e in data.get("login_events", [])],
        permanent_events=[_event(e) for e in data.get("permanent_events", [])],
        battle_pass=_event(bp) if bp else None,
        other_events=[_event(e) for e in data.get("other_events", [])],
    )


__all__ = ["Banner", "Event", "CalendarData", "load_calendar"]
