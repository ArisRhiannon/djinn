# `data/` — Datos persistentes y assets del bot

Este directorio contiene datos de runtime + assets descargables. Algunos
archivos están intencionalmente vacíos pero su presencia es necesaria.

## Archivos vacíos intencionales

| Archivo | Estado | Por qué |
|---------|--------|---------|
| `bad_domains.txt` | 0 bytes (vacío) | `utils/link_checker.py:LinkChecker._load_bad_domains` abre este archivo al inicio. Si se elimina, lanza FileNotFoundError. Una lista de dominios maliciosos puede añadirse manualmente (un dominio por línea). |
| `fairy_responses.json` | 3 bytes `{}` | Plantillas de respuestas precanned (legacy). El instalador (`install.sh`) lo crea vacío si falta. Referenciado en `config.py:RESPONSES_PATH` y `.env:RESPONSES_PATH`. |

## Archivos cacheados / regenerables

- `mobilenetv3_small.onnx` + `.onnx.data` — modelo de visión para `media_guard`. Re-descargable con `scripts/download_mobilenet_onnx.py`.
- `banned_media.bin` + `banned_media_meta.json` — índice de medios baneados (FAISS-like). Generado en runtime por `cogs/media_guard`.
- `dashboard.json` — estado del dashboard cog. Regenerado al arranque.

## Datos generados por usuarios (NO regenerables)

- `kadath_world.json` (~916 KB) — mundo del juego Kadath.
- `kadath_world_v2.json` (~124 KB) — versión 2 del mundo (en migración).
- `kadath_saves/<user_id>.json` — partidas guardadas por usuario.
- `personas/<user_id - nombre>/` — perfiles persistentes destilados.
- `simulacion/estado_global.json` — estado global de simulación.
- `mapas/zona_principal.json` — mapas del juego.
- `xoft_persona.md` — persona del cog `xoft`.

## Datos extraídos por refactor (Wave 6, 2026-05-15)

- `safe_domains.json` (~159 KB, 10 019 dominios) — extraído de
  `cogs/safe_domains.py` (legacy ahora en `deprecated/cogs_old/`).
  Cargado por `utils/safe_domains.py:safe_domains()` con caché lru.

## Backups automáticos

- `backups/` — destino de los backups diarios de SQLite creados por
  `cogs/db_maintenance.py` (Wave 3, F1.2). Retención: 7 días por defecto.
  Se crea al primer backup. Variable: `FAIRY_DB_BACKUP_DIR`.
