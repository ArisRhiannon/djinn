#!/usr/bin/env python3
"""Backfill: genera embeddings para mensajes históricos sin embedding.

Uso:
    python scripts/backfill_embeddings.py [--batch 200] [--dry-run]

Requiere que el venv esté activo y que sentence-transformers + sqlite-vec
estén instalados.  Funciona sobre la DB directamente (sin arrancar el bot).
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import sqlite3
import time

# ── Añadir raíz del proyecto al path ─────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DB_PATH = os.path.join(ROOT, "db", "youkai.db")
MIN_EMBED_LENGTH = 5


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill de embeddings")
    parser.add_argument("--batch", type=int, default=200, help="Tamaño de lote")
    parser.add_argument("--dry-run", action="store_true", help="Solo contar, no escribir")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"❌ DB no encontrada: {DB_PATH}")
        sys.exit(1)

    # ── Conectar DB ──────────────────────────────────────────────────────
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    # Cargar sqlite-vec
    vec_available = False
    try:
        import sqlite_vec
        db.enable_load_extension(True)
        db.load_extension(sqlite_vec.loadable_path())
        db.enable_load_extension(False)
        # Asegurar que vec_messages existe
        db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS vec_messages USING vec0(
            embedding float[384]
        )""")
        db.commit()
        vec_available = True
    except Exception as e:
        print(f"⚠️  sqlite-vec no disponible ({e}) — solo BLOB store")

    # ── Contar mensajes sin embedding ────────────────────────────────────
    cur = db.execute(
        """SELECT COUNT(*) FROM messages m
           LEFT JOIN message_embeddings me ON me.message_id = m.id
           WHERE me.message_id IS NULL
             AND m.content IS NOT NULL
             AND LENGTH(m.content) >= ?""",
        (MIN_EMBED_LENGTH,),
    )
    total = cur.fetchone()[0]
    print(f"📊 Mensajes sin embedding (≥{MIN_EMBED_LENGTH} chars): {total:,}")

    if total == 0:
        print("✅ Todos los mensajes ya tienen embedding. Nada que hacer.")
        db.close()
        return

    if args.dry_run:
        db.close()
        return

    # ── Cargar modelo ────────────────────────────────────────────────────
    print("⏳ Cargando modelo all-MiniLM-L6-v2...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("✅ Modelo cargado.")

    # ── Procesar en lotes ─────────────────────────────────────────────────
    processed = 0
    t_start = time.time()

    while True:
        rows = db.execute(
            """SELECT m.id, m.content FROM messages m
               LEFT JOIN message_embeddings me ON me.message_id = m.id
               WHERE me.message_id IS NULL
                 AND m.content IS NOT NULL
                 AND LENGTH(m.content) >= ?
               ORDER BY m.id ASC LIMIT ?""",
            (MIN_EMBED_LENGTH, args.batch),
        ).fetchall()

        if not rows:
            break

        ids = [r["id"] for r in rows]
        texts = [r["content"] for r in rows]

        # Encode batch
        embeddings = model.encode(texts, normalize_embeddings=True)

        # Empaquetar e insertar
        blob_items = []
        vec_items = []
        for i, mid in enumerate(ids):
            emb = embeddings[i]
            dim = len(emb)
            blob = struct.pack(f"{dim}f", *emb.tolist())
            blob_items.append((mid, blob, dim))
            vec_items.append((mid, blob))

        db.executemany(
            "INSERT OR IGNORE INTO message_embeddings "
            "(message_id, embedding, model_dim) VALUES (?, ?, ?)",
            blob_items,
        )
        if vec_available:
            try:
                db.executemany(
                    "INSERT INTO vec_messages (rowid, embedding) VALUES (?, ?)",
                    vec_items,
                )
            except Exception:
                vec_available = False  # deshabilitar para el resto

        db.commit()
        processed += len(rows)

        if processed % 1000 < args.batch:
            elapsed = time.time() - t_start
            rate = processed / elapsed if elapsed > 0 else 0
            eta = (total - processed) / rate if rate > 0 else 0
            print(f"  {processed:,}/{total:,} ({processed*100//total}%) "
                  f"— {rate:.0f} msg/s — ETA {eta:.0f}s")

    elapsed = time.time() - t_start
    print(f"\n✅ Backfill completo: {processed:,} embeddings en {elapsed:.1f}s "
          f"({processed/elapsed:.0f} msg/s)")

    # ── Verificar ────────────────────────────────────────────────────────
    cur = db.execute("SELECT COUNT(*) FROM message_embeddings")
    embed_count = cur.fetchone()[0]
    if vec_available:
        cur = db.execute("SELECT COUNT(*) FROM vec_messages")
        vec_count = cur.fetchone()[0]
        print(f"📊 message_embeddings: {embed_count:,} | vec_messages: {vec_count:,}")
    else:
        print(f"📊 message_embeddings: {embed_count:,} (vec_messages: N/A)")

    db.close()


if __name__ == "__main__":
    main()
