from __future__ import annotations
import asyncio
import sys
import time
import argparse
from pathlib import Path

# Agregar el directorio raíz del proyecto al sys.path para poder hacer imports
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from config import YoukaiConfig
from utils.database import Database
from utils.embed_engine import EmbedEngine
from loguru import logger

async def run_backfill(limit: int, batch_size: int):
    logger.info("Iniciando backfill semántico de recuerdos para ChromaDB...")
    logger.info(f"Parámetros: límite={limit}, lote={batch_size}")

    # 1. Cargar configuración y conectar a DB
    config = YoukaiConfig.from_env()
    db = Database(config.db_path)
    await db.initialize()

    # 2. Inicializar el motor de embeddings
    logger.info("Cargando EmbedEngine (MiniLM)...")
    embedder = EmbedEngine(config)
    
    # Cargar en executor para no bloquear
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, embedder.load)
    
    if not embedder.available:
        logger.critical("No se pudo cargar el motor de embeddings MiniLM.")
        return

    if not db._vec_available:
        logger.critical("El backend vectorial de ChromaDB no está inicializado en la base de datos.")
        return

    # 3. Leer la cantidad total de mensajes candidatos
    async with db._db.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE content IS NOT NULL AND LENGTH(content) >= 20"
    ) as cur:
        row = await cur.fetchone()
        total_candidates = row["cnt"] if row else 0

    logger.info(f"Mensajes totales candidatos en SQLite: {total_candidates}")
    to_process = min(limit, total_candidates)
    logger.info(f"Mensajes planeados a indexar: {to_process}")

    if to_process <= 0:
        logger.info("No hay mensajes válidos para indexar.")
        return

    # 4. Procesar en reversa (más nuevos primero)
    offset = 0
    processed = 0
    t_start = time.time()

    while offset < to_process:
        chunk_limit = min(batch_size, to_process - offset)
        
        # Leer lote de la DB
        async with db._db.execute(
            """SELECT m.id, m.guild_id, m.channel_id, m.user_id, m.username, m.content, m.timestamp
               FROM messages m
               WHERE m.content IS NOT NULL AND LENGTH(m.content) >= 20
               ORDER BY m.id DESC LIMIT ? OFFSET ?""",
            (chunk_limit, offset),
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

        if not rows:
            break

        # Extraer textos y metadatos
        texts = [r["content"] for r in rows]

        # Codificar usando EmbedEngine
        embeddings = await loop.run_in_executor(
            None, embedder.encode, texts
        )

        # Preparar estructura de items para ChromaDB
        items = []
        for idx, row in enumerate(rows):
            emb = embeddings[idx]
            items.append({
                "message_id": row["id"],
                "content": row["content"],
                "embedding": emb.tolist(),
                "guild_id": row["guild_id"],
                "channel_id": row["channel_id"],
                "user_id": row["user_id"],
                "username": row["username"] or "",
                "timestamp": row["timestamp"]
            })

        # Almacenar en ChromaDB
        await db.store_embeddings(items)

        processed += len(rows)
        offset += len(rows)
        
        elapsed = time.time() - t_start
        speed = processed / elapsed if elapsed > 0 else 0.0
        remaining_time = (to_process - processed) / speed if speed > 0 else 0.0
        
        logger.info(
            "Indexados {}/{} mensajes ({:.1f}%) · velocidad: {:.1f} msgs/s · restan: {:.1f}s",
            processed, to_process, (processed / to_process) * 1000.0 // 10 / 10.0, speed, remaining_time
        )

    db.chroma_memory.close()
    await db._db.close()
    
    total_time = time.time() - t_start
    logger.success(
        "¡Backfill semántico completado con éxito! Indexados {} mensajes en {:.1f}s (velocidad media: {:.1f} msgs/s).",
        processed, total_time, processed / total_time if total_time > 0 else 0.0
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poblar ChromaDB con el historial de mensajes de SQLite.")
    parser.add_argument("--limit", type=int, default=25000, help="Límite máximo de mensajes a indexar (por defecto 25,000).")
    parser.add_argument("--batch-size", type=int, default=500, help="Tamaño de lote para codificación (por defecto 500).")
    args = parser.parse_args()

    asyncio.run(run_backfill(args.limit, args.batch_size))
