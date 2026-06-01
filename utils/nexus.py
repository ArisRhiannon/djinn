"""
Djinn Nexus — Grafo de resolucion de identidades por guild.
Mapea aliases y nombres a IDs de Discord usando asociaciones ponderadas.

Las operaciones de DB se delegan a Database.nexus_*() para asegurar
serializacion correcta via write_lock y evitar 'database is locked'.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .database import Database

from loguru import logger


@dataclass
class Entity:
    id: str
    type: str  # 'user' | 'role' | 'channel'
    name: str
    guild_id: int


class DjinnNexus:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def initialize(self) -> None:
        """Verifica que la DB este inicializada."""
        if self.db._db is None:
            raise RuntimeError("La base de datos debe estar inicializada antes que el Nexus.")
        logger.info("Djinn Nexus inicializado.")

    async def update_association(
        self,
        alias: str,
        entity_id: str,
        entity_type: str,
        name: str,
        guild_id: int,
    ) -> None:
        """Refuerza la asociacion entre un alias y una entidad."""
        await self.db.nexus_update_association(
            alias, entity_id, entity_type, name, guild_id
        )

    async def resolve_entity(
        self, query: str, guild_id: int
    ) -> Optional[Entity]:
        """Resuelve un alias al entity de mayor peso para este guild."""
        result = await self.db.nexus_resolve_entity(query, guild_id)
        if result:
            return Entity(
                id=result["id"],
                type=result["type"],
                name=result["name"],
                guild_id=result["guild_id"],
            )
        return None

    async def get_context_snapshot(
        self, guild_id: int, limit: int = 20
    ) -> str:
        """Genera un string compacto con las entidades mas relevantes del guild."""
        return await self.db.nexus_get_context_snapshot(guild_id, limit)

    async def close(self) -> None:
        """Limpia la referencia. La conexion la gestiona Database.close()."""
        logger.info("Djinn Nexus: referencia liberada.")
