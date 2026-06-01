# Youkai API Interna

Servidor HTTP local para monitoreo y control del bot.

## Conexión

- **Host**: `127.0.0.1:8080` (solo localhost)
- **Auth**: Header `X-API-Key: <valor de INTERNAL_API_KEY en .env>`
- `/health` no requiere autenticación

## Endpoints

### GET /health
Estado rápido del bot y servicios.
```json
{"status": "ok|degraded", "service": "fairy-api", "version": "lv999", "services": {"DB": "ok", "LLM": "ok", "TTS": "fail"}, "circuit_breaker": "closed|open"}
```

### GET /api/v1/status
Info general: uptime, versión de Python/discord.py, user tag.

### GET /api/v1/logs
Logs recientes del ring buffer.
- Query params: `?limit=50&level=INFO`

### GET /api/v1/metrics
Métricas de sistema: CPU, RAM, tamaño de DB, uptime.

### GET /api/v1/llm
Estado del LLM activo: provider, modelo, temperatura, tokens, thinking level.

### GET /api/v1/discord
Estado de Discord: guilds, usuarios, canales, latencia, presencia.

### GET /api/v1/services
Estado de todos los servicios internos (DB, LLM, TTS, Embed, etc).

### GET /api/v1/cogs
Lista de cogs cargados y su estado.

### GET /api/v1/orchestrator
Estado del orchestrator: historiales activos, circuit breaker, turnos totales.

## WebSockets

### WS /api/v1/ws/logs
Stream de logs en tiempo real. Formato: `{"type": "log", "data": {"timestamp": "HH:MM:SS", "level": "INFO", "message": "...", "source": "..."}}`

### WS /api/v1/ws/metrics
Métricas cada 2s. Formato: `{"type": "metrics", "data": {...}}`

## Seguridad
- Solo escucha en 127.0.0.1
- CORS solo para localhost origins
- Rate limiting básico por IP
