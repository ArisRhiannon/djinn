from __future__ import annotations
import logging
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional
import chromadb

logger = logging.getLogger("djinn.chroma_memory")

class ChromaMemory:
    def __init__(self, db_dir: str = "db/chromadb") -> None:
        self.db_path = Path(db_dir).resolve()
        self.client: Optional[chromadb.PersistentClient] = None
        self.collection = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chroma_exec")

    def initialize(self) -> None:
        """Inicializa el cliente persistente de ChromaDB y obtiene la colección."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(self.db_path))
            # Crear o recuperar colección con espacio de distancia coseno
            self.collection = self.client.get_or_create_collection(
                name="djinn_messages",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("ChromaMemory inicializado exitosamente en %s", self.db_path)
        except Exception as exc:
            logger.exception("Error inicializando ChromaMemory: %s", exc)
            raise

    async def add_messages(self, items: List[Dict[str, Any]]) -> None:
        """
        Almacena embeddings y metadatas de forma asíncrona en ChromaDB.
        
        items: [{
            "message_id": int,
            "content": str,
            "embedding": List[float],
            "guild_id": int,
            "channel_id": int,
            "user_id": int,
            "username": str,
            "timestamp": int
        }, ...]
        """
        if not self.collection or not items:
            return

        def _add():
            ids = []
            embeddings = []
            documents = []
            metadatas = []
            for it in items:
                ids.append(str(it["message_id"]))
                embeddings.append(it["embedding"])
                documents.append(it["content"] or "")
                metadatas.append({
                    "guild_id": int(it["guild_id"]),
                    "channel_id": int(it["channel_id"]),
                    "user_id": int(it["user_id"]),
                    "username": str(it["username"] or ""),
                    "timestamp": int(it["timestamp"])
                })
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(self._executor, _add)
        except Exception as exc:
            logger.error("Error al insertar en ChromaMemory: %s", exc)

    async def search_messages(
        self,
        query_embedding: List[float],
        guild_id: int,
        limit: int = 50,
        since: int = 0,
        channel_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[int, int]:
        """
        Busca mensajes vectorialmente con filtros de metadatos rápidos.
        Retorna mapeo {message_id: rank_1_based} para fusión RRF.
        """
        if not self.collection:
            return {}

        # Construir filtros de metadatos
        where: Dict[str, Any] = {
            "$and": [
                {"guild_id": {"$eq": int(guild_id)}},
                {"timestamp": {"$gt": int(since)}}
            ]
        }
        if channel_id is not None:
            where["$and"].append({"channel_id": {"$eq": int(channel_id)}})
        if user_id is not None:
            where["$and"].append({"user_id": {"$eq": int(user_id)}})

        def _query():
            return self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where
            )

        loop = asyncio.get_running_loop()
        try:
            res = await loop.run_in_executor(self._executor, _query)
            if not res or not res.get("ids") or not res["ids"][0]:
                return {}
            
            # Mapear ids a rankings 1-based
            vec_results = {}
            for rank, str_id in enumerate(res["ids"][0]):
                try:
                    vec_results[int(str_id)] = rank + 1
                except ValueError:
                    pass
            return vec_results
        except Exception as exc:
            logger.error("Error al buscar en ChromaMemory: %s", exc)
            return {}

    def close(self) -> None:
        """Cierra el executor."""
        self._executor.shutdown(wait=False)
