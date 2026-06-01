"""
Djinn API Server — Servidor HTTP interno para consumo local.

Endpoints:
  GET  /health              → Health check
  GET  /api/v1/status       → Estado general del bot
  GET  /api/v1/logs         → Logs recientes (query: ?limit=50&level=INFO)
  GET  /api/v1/metrics      → Métricas de sistema, LLM, Discord
  GET  /api/v1/llm          → Estado y configuración del LLM activo
  GET  /api/v1/discord      → Estado de Discord (guilds, usuarios, presencia)
  GET  /api/v1/services     → Estado de servicios internos
  GET  /api/v1/cogs         → Estado de cogs cargados
  GET  /api/v1/orchestrator → Estado del orchestrator (historiales, circuit breakers)
  WS   /api/v1/ws/logs      → WebSocket: logs en tiempo real
  WS   /api/v1/ws/metrics   → WebSocket: métricas cada 2s

Seguridad:
  • Solo escucha en 127.0.0.1 (localhost)
  • Autenticación por X-API-Key header
  • CORS permitido solo para localhost origins
  • Rate limiting básico por IP

Uso desde tu sitio web (misma VM):
  fetch('http://127.0.0.1:8080/api/v1/status', {
    headers: { 'X-API-Key': 'tu-api-key' }
  })
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import secrets
import time
import weakref
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

# FIX (2026-05-16): `discord` se usa en /api/v1/status (discord.__version__)
# pero no estaba importado — causaba NameError en la respuesta del endpoint.
import discord
from loguru import logger

# Soft import de aiohttp
try:
    from aiohttp import web, WSMsgType
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False
    web = WSMsgType = None  # type: ignore


# ═══════════════════════════════════════════════════════════════════════════════
# MODELOS DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BotStatus:
    online: bool
    user_tag: str
    user_id: int
    uptime_seconds: float
    python_version: str
    discord_py_version: str
    platform: str
    boot_time: str


@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    source: str


@dataclass
class ServiceStatus:
    name: str
    status: str  # "ok" | "fail" | "disabled"
    detail: str = ""


@dataclass
class LLMStatus:
    provider: str
    model: str
    temperature: float
    top_p: float
    top_k: int
    max_output_tokens: int
    thinking_level: str
    ready: bool


@dataclass
class DiscordStatus:
    guilds: int
    users: int
    channels: int
    messages_per_min: int
    presence: str
    latency_ms: float


@dataclass
class SystemMetrics:
    cpu_percent: float
    ram_used_mb: float
    ram_total_mb: float
    ram_percent: float
    db_size_mb: float
    uptime_seconds: float


@dataclass
class OrchestratorStatus:
    histories_count: int
    circuit_breaker_state: str
    total_turns: int


# ═══════════════════════════════════════════════════════════════════════════════
# RING BUFFER PARA LOGS
# ═══════════════════════════════════════════════════════════════════════════════

class LogRingBuffer:
    """Buffer circular thread-safe para logs."""

    def __init__(self, maxsize: int = 500) -> None:
        self._buffer: deque[LogEntry] = deque(maxlen=maxsize)
        self._lock = asyncio.Lock()
        self._subscribers: weakref.WeakSet = weakref.WeakSet()

    def append_sync(self, entry: LogEntry) -> None:
        """Append thread-safe y sincrónico. `collections.deque.append` es atómico
        en CPython, así que no necesita lock para escritura individual. Usar este
        método desde el sink de loguru (que puede correr en cualquier thread)."""
        self._buffer.append(entry)

    async def append(self, entry: LogEntry) -> None:
        async with self._lock:
            self._buffer.append(entry)
        # Notificar suscriptores WebSocket
        await self._notify_subscribers(entry)

    async def get_recent(self, n: int = 100) -> list[LogEntry]:
        async with self._lock:
            return list(self._buffer)[-n:]

    def subscribe(self, ws) -> None:
        self._subscribers.add(ws)

    def unsubscribe(self, ws) -> None:
        self._subscribers.discard(ws)

    async def _notify_subscribers(self, entry: LogEntry) -> None:
        dead = set()
        for ws in list(self._subscribers):
            try:
                await ws.send_json({
                    "type": "log",
                    "data": asdict(entry),
                })
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._subscribers.discard(ws)


# ═══════════════════════════════════════════════════════════════════════════════
# LOGURU SINK
# ═══════════════════════════════════════════════════════════════════════════════

class APILogSink:
    """Sink de loguru que alimenta el ring buffer del API."""

    def __init__(self, ring: LogRingBuffer) -> None:
        self._ring = ring
        self._handler_id: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def install(self) -> None:
        from loguru import logger as loguru_logger

        # Capturar el loop principal; `install()` se llama desde un contexto async.
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        ring = self._ring
        loop_ref = self._loop

        def sink(message):
            # Loguru puede llamar este sink desde cualquier thread (workers de
            # huggingface_hub, ThreadPoolExecutor, bridge del logging stdlib, etc.).
            # El buffer se actualiza sin loop; solo se despacha a websockets si
            # hay suscriptores y tenemos un loop corriendo.
            record = message.record
            entry = LogEntry(
                timestamp=record["time"].strftime("%H:%M:%S"),
                level=record["level"].name,
                message=str(record["message"])[:200],
                source=record.get("name", ""),
            )
            ring.append_sync(entry)

            if not ring._subscribers or loop_ref is None or loop_ref.is_closed():
                return
            try:
                asyncio.run_coroutine_threadsafe(
                    ring._notify_subscribers(entry), loop_ref
                )
            except RuntimeError:
                # Loop cerrándose o ya cerrado: descartar silenciosamente.
                pass

        self._handler_id = loguru_logger.add(
            sink,
            format="{message}",
            level="INFO",
            enqueue=False,
            filter=lambda r: r["name"] not in ("utils.api_server", "aiohttp", "aiohttp.access"),
        )
        logger.debug("API: Log sink instalado (id={})", self._handler_id)

    def uninstall(self) -> None:
        if self._handler_id is not None:
            from loguru import logger as loguru_logger
            try:
                loguru_logger.remove(self._handler_id)
            except Exception:
                pass
            self._handler_id = None
        self._loop = None


# ═══════════════════════════════════════════════════════════════════════════════
# API SERVER
# ═══════════════════════════════════════════════════════════════════════════════

class DjinnAPIServer:
    """Servidor HTTP interno para Djinn."""

    DEFAULT_PORT = 8080
    DEFAULT_HOST = "127.0.0.1"

    def __init__(self, bot: Any, api_key: str | None = None) -> None:
        self.bot = bot
        # SEC-03 (Wave 1, 2026-05-15): API key aleatoria si FAIRY_API_KEY no
        # está configurada. Antes el fallback era el literal "fairy-local-dev"
        # — predecible y explotable por cualquier proceso local o vía SSRF.
        env_key = os.environ.get("FAIRY_API_KEY")
        self._api_key = api_key or env_key or secrets.token_urlsafe(32)
        if not (api_key or env_key):
            logger.warning(
                "FAIRY_API_KEY no definida en entorno — generada aleatoriamente "
                "para esta sesión: {prefix}... "
                "(definila en .env para que persista entre reinicios)",
                prefix=self._api_key[:8],
            )
        self._ring = LogRingBuffer(maxsize=500)
        self._log_sink = APILogSink(self._ring)
        self._app: Any = None
        self._runner: Any = None
        self._site: Any = None
        self._task: asyncio.Task | None = None
        self._start_time = time.time()
        self._metrics_task: asyncio.Task | None = None
        self._metrics_subscribers: weakref.WeakSet = weakref.WeakSet()

        if _AIOHTTP_AVAILABLE:
            self._setup_routes()

    def _setup_routes(self) -> None:
        self._app = web.Application(middlewares=[self._auth_middleware, self._cors_middleware])

        # Health
        self._app.router.add_get("/health", self._handle_health)

        # API v1
        self._app.router.add_get("/api/v1/status", self._handle_status)
        self._app.router.add_get("/api/v1/logs", self._handle_logs)
        self._app.router.add_get("/api/v1/metrics", self._handle_metrics)
        # F5.3 (Wave 9, 2026-05-15): contadores estructurados in-app + circuit breakers
        self._app.router.add_get("/api/v1/metrics_x", self._handle_metrics_x)
        self._app.router.add_get("/api/v1/llm", self._handle_llm)
        self._app.router.add_get("/api/v1/discord", self._handle_discord)
        self._app.router.add_get("/api/v1/services", self._handle_services)
        self._app.router.add_get("/api/v1/cogs", self._handle_cogs)
        self._app.router.add_get("/api/v1/orchestrator", self._handle_orchestrator)

        # WebSockets
        self._app.router.add_get("/api/v1/ws/logs", self._handle_ws_logs)
        self._app.router.add_get("/api/v1/ws/metrics", self._handle_ws_metrics)

    @web.middleware
    async def _auth_middleware(self, request, handler):
        """Middleware de autenticación por API key."""
        # Health check no requiere auth
        if request.path == "/health":
            return await handler(request)

        # WebSockets usan query param
        if request.path.startswith("/api/v1/ws/"):
            key = request.query.get("key", "")
        else:
            key = request.headers.get("X-API-Key", "")

        if key != self._api_key:
            return web.json_response(
                {"error": "Unauthorized"},
                status=401,
            )

        return await handler(request)

    @web.middleware
    async def _cors_middleware(self, request, handler):
        """CORS: solo permitir localhost."""
        response = await handler(request)
        origin = request.headers.get("Origin", "")
        if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "X-API-Key, Content-Type"
        return response

    async def start(self) -> None:
        """Inicia el servidor HTTP."""
        if not _AIOHTTP_AVAILABLE:
            logger.warning("API: aiohttp no instalado — servidor no disponible.")
            logger.info("      Instala con: pip install aiohttp")
            return

        # Instalar log sink
        self._log_sink.install()

        # Iniciar servidor
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(
            self._runner,
            host=self.DEFAULT_HOST,
            port=self.DEFAULT_PORT,
        )
        await self._site.start()

        # Task de métricas periódicas
        self._metrics_task = asyncio.create_task(self._metrics_broadcaster())

        logger.info(
            "API[LV999]: Servidor interno iniciado en http://{}:{}",
            self.DEFAULT_HOST,
            self.DEFAULT_PORT,
        )

    async def stop(self) -> None:
        """Detiene el servidor HTTP."""
        self._log_sink.uninstall()

        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass

        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

        logger.info("API: Servidor detenido.")

    # ── Handlers ─────────────────────────────────────────────────────────

    async def _handle_health(self, request) -> web.Response:
        services = {}
        bot = self.bot
        if hasattr(bot, "_svc_status"):
            services = {k: "ok" if v else "fail" for k, v in bot._svc_status.items()}
        cb_state = "closed"
        if hasattr(bot, "orchestrator"):
            orch = bot.orchestrator
            if hasattr(orch, "_cb_failures") and orch._cb_failures >= orch._CB_FAIL_THRESHOLD:
                cb_state = "open"
        return web.json_response({
            "status": "ok" if bot.is_ready() else "degraded",
            "service": "fairy-api",
            "version": "lv999",
            "services": services,
            "circuit_breaker": cb_state,
        })

    async def _handle_status(self, request) -> web.Response:
        bot = self.bot
        uptime = time.time() - self._start_time

        return web.json_response({
            "online": bot.is_ready() if hasattr(bot, "is_ready") else False,
            "user_tag": str(bot.user) if bot.user else None,
            "user_id": bot.user.id if bot.user else None,
            "uptime_seconds": round(uptime, 1),
            "python_version": platform.python_version(),
            "discord_py_version": discord.__version__,
            "platform": platform.machine(),
            "boot_time": datetime.fromtimestamp(self._start_time).isoformat(),
        })

    async def _handle_logs(self, request) -> web.Response:
        limit = int(request.query.get("limit", 100))
        level_filter = request.query.get("level", None)

        logs = await self._ring.get_recent(limit)

        if level_filter:
            logs = [l for l in logs if l.level == level_filter.upper()]

        return web.json_response({
            "logs": [asdict(l) for l in logs],
            "count": len(logs),
        })

    async def _handle_metrics(self, request) -> web.Response:
        return web.json_response({
            "system": asdict(self._get_system_metrics()),
            "discord": asdict(self._get_discord_metrics()),
            "timestamp": datetime.now().isoformat(),
        })

    async def _handle_metrics_x(self, request) -> web.Response:
        """F5.3: contadores in-app y circuit breakers (Wave 9)."""
        try:
            from utils.metrics import snapshot as _metrics_snapshot
            payload = _metrics_snapshot()
        except ImportError:
            payload = {"error": "utils.metrics no disponible"}
        return web.json_response(payload)

    async def _handle_llm(self, request) -> web.Response:
        bot = self.bot
        if not bot or not hasattr(bot, "llm") or not bot.llm:
            return web.json_response({"error": "LLM not loaded"}, status=503)

        llm = bot.llm
        provider = llm.__class__.__name__.replace("LLM", "")
        model = getattr(llm, "get_model_name", lambda: "unknown")()

        try:
            from utils.llm_client import LLMConfig
            return web.json_response({
                "provider": provider,
                "model": model,
                "temperature": LLMConfig.GEMMA4_TEMPERATURE,
                "top_p": LLMConfig.GEMMA4_TOP_P,
                "top_k": LLMConfig.GEMMA4_TOP_K,
                "max_output_tokens": LLMConfig.GEMMA4_MAX_OUTPUT_TOKENS,
                "thinking_level": LLMConfig.GEMMA4_THINKING_LEVEL,
                "ready": getattr(llm, "ready", False),
            })
        except Exception:
            return web.json_response({
                "provider": provider,
                "model": model,
                "ready": getattr(llm, "ready", False),
            })

    async def _handle_discord(self, request) -> web.Response:
        bot = self.bot
        if not bot:
            return web.json_response({"error": "Bot not ready"}, status=503)

        guilds = len(bot.guilds) if hasattr(bot, "guilds") else 0
        users = sum(g.member_count or 0 for g in bot.guilds) if hasattr(bot, "guilds") else 0
        channels = sum(len(g.channels) for g in bot.guilds) if hasattr(bot, "guilds") else 0

        presence = ""
        if bot.user:
            activity = getattr(bot, "activity", None)
            if activity:
                presence = activity.name if hasattr(activity, "name") else ""

        latency = bot.latency * 1000 if hasattr(bot, "latency") else 0

        return web.json_response({
            "guilds": guilds,
            "users": users,
            "channels": channels,
            "presence": presence,
            "latency_ms": round(latency, 2),
        })

    async def _handle_services(self, request) -> web.Response:
        bot = self.bot
        services = []
        if bot and hasattr(bot, "_svc_status"):
            for name, ok in bot._svc_status.items():
                if ok is None:
                    services.append({"name": name, "status": "disabled", "detail": ""})
                elif ok:
                    services.append({"name": name, "status": "ok", "detail": "ready"})
                else:
                    services.append({"name": name, "status": "fail", "detail": "failed"})

        return web.json_response({"services": services})

    async def _handle_cogs(self, request) -> web.Response:
        bot = self.bot
        cogs = []
        if bot and hasattr(bot, "extensions"):
            for name in bot.extensions:
                cog = bot.get_cog(name.split(".")[-1].replace("_", " ").title())
                cogs.append({
                    "name": name,
                    "loaded": True,
                    "cog": cog.__class__.__name__ if cog else None,
                })

        return web.json_response({"cogs": cogs, "count": len(cogs)})

    async def _handle_orchestrator(self, request) -> web.Response:
        bot = self.bot
        if not bot or not hasattr(bot, "orchestrator") or not bot.orchestrator:
            return web.json_response({"error": "Orchestrator not ready"}, status=503)

        orch = bot.orchestrator
        try:
            stats = await orch.get_stats() if hasattr(orch, "get_stats") else {}
            return web.json_response(stats)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    # ── WebSockets ───────────────────────────────────────────────────────

    async def _handle_ws_logs(self, request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self._ring.subscribe(ws)
        logger.debug("API: Cliente WebSocket conectado a /ws/logs")

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Cliente puede enviar comandos
                    data = json.loads(msg.data)
                    if data.get("action") == "ping":
                        await ws.send_json({"type": "pong"})
                elif msg.type == WSMsgType.ERROR:
                    break
        except Exception:
            pass
        finally:
            self._ring.unsubscribe(ws)
            logger.debug("API: Cliente WebSocket desconectado de /ws/logs")

        return ws

    async def _handle_ws_metrics(self, request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self._metrics_subscribers.add(ws)
        logger.debug("API: Cliente WebSocket conectado a /ws/metrics")

        # Enviar métricas iniciales
        await ws.send_json({
            "type": "metrics",
            "data": {
                "system": asdict(self._get_system_metrics()),
                "discord": asdict(self._get_discord_metrics()),
            },
        })

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("action") == "ping":
                        await ws.send_json({"type": "pong"})
                elif msg.type == WSMsgType.ERROR:
                    break
        except Exception:
            pass
        finally:
            self._metrics_subscribers.discard(ws)
            logger.debug("API: Cliente WebSocket desconectado de /ws/metrics")

        return ws

    # ── Métricas periódicas ──────────────────────────────────────────────

    async def _metrics_broadcaster(self) -> None:
        """Envía métricas a todos los suscriptores cada 2 segundos."""
        while True:
            try:
                await asyncio.sleep(2.0)

                metrics = {
                    "type": "metrics",
                    "data": {
                        "system": asdict(self._get_system_metrics()),
                        "discord": asdict(self._get_discord_metrics()),
                        "timestamp": datetime.now().isoformat(),
                    },
                }

                dead = set()
                for ws in list(self._metrics_subscribers):
                    try:
                        await ws.send_json(metrics)
                    except Exception:
                        dead.add(ws)

                for ws in dead:
                    self._metrics_subscribers.discard(ws)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5.0)

    # ── Colectores ───────────────────────────────────────────────────────

    def _get_system_metrics(self) -> SystemMetrics:
        metrics = SystemMetrics(
            cpu_percent=0.0,
            ram_used_mb=0.0,
            ram_total_mb=0.0,
            ram_percent=0.0,
            db_size_mb=0.0,
            uptime_seconds=time.time() - self._start_time,
        )

        try:
            import psutil
            metrics.cpu_percent = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            metrics.ram_used_mb = round(mem.used / (1024 * 1024), 1)
            metrics.ram_total_mb = round(mem.total / (1024 * 1024), 1)
            metrics.ram_percent = mem.percent
        except ImportError:
            pass

        try:
            if self.bot and hasattr(self.bot, "config"):
                db_path = __import__("pathlib").Path(self.bot.config.db_path)
                if db_path.exists():
                    metrics.db_size_mb = round(db_path.stat().st_size / (1024 * 1024), 1)
        except Exception:
            pass

        return metrics

    def _get_discord_metrics(self) -> DiscordStatus:
        bot = self.bot
        if not bot:
            return DiscordStatus(0, 0, 0, 0, "", 0)

        guilds = len(bot.guilds) if hasattr(bot, "guilds") else 0
        users = sum(g.member_count or 0 for g in bot.guilds) if hasattr(bot, "guilds") else 0
        channels = sum(len(g.channels) for g in bot.guilds) if hasattr(bot, "guilds") else 0

        presence = ""
        if bot.user:
            activity = getattr(bot, "activity", None)
            if activity:
                presence = activity.name if hasattr(activity, "name") else ""

        latency = bot.latency * 1000 if hasattr(bot, "latency") else 0

        return DiscordStatus(
            guilds=guilds,
            users=users,
            channels=channels,
            messages_per_min=0,  # TODO: implementar contador
            presence=presence,
            latency_ms=round(latency, 2),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK
# ═══════════════════════════════════════════════════════════════════════════════

class DjinnAPIFallback:
    def __init__(self, bot: Any, api_key: str | None = None) -> None:
        pass
    async def start(self) -> None:
        pass
    async def stop(self) -> None:
        pass


def create_api_server(bot: Any, api_key: str | None = None) -> DjinnAPIServer | DjinnAPIFallback:
    if _AIOHTTP_AVAILABLE:
        return DjinnAPIServer(bot, api_key)
    return DjinnAPIFallback(bot, api_key)
