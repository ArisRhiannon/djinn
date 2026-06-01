"""
Djinn — Discord Agentic Bot
Inspirada en la IA de Zenless Zone Zero.
Corre sobre Google AI Studio (Gemma 4) vía google-genai SDK.

API Interna LV999:
  • Servidor HTTP en localhost:8080
  • REST endpoints para logs, métricas, estado
  • WebSockets para datos en tiempo real
  • Solo accesible desde la misma VM
"""

# ── Bootstrap venv ────────────────────────────────────────────────────────────
# Permite ejecutar simplemente `python3 main.py` con el Python del sistema:
# crea el venv si falta, instala dependencias si faltan, y se re-ejecuta
# dentro del venv. Si ya estamos dentro del venv del proyecto, no hace nada.
# Exportá FAIRY_NO_BOOTSTRAP=1 para saltarlo (p. ej. en contenedores).

def _bootstrap_venv() -> None:
    import os as _os
    import sys as _sys
    from pathlib import Path as _Path

    if _os.environ.get("FAIRY_NO_BOOTSTRAP") == "1":
        return

    project_dir = _Path(__file__).resolve().parent
    venv_dir = project_dir / "venv"
    venv_python = venv_dir / "bin" / "python"

    # Ya estamos dentro del venv del proyecto → nada que hacer.
    try:
        current = _Path(_sys.executable).resolve()
        if venv_python.exists() and current == venv_python.resolve():
            return
    except OSError:
        pass

    # Crear venv si falta.
    if not venv_python.exists():
        print(f"🔧 Creando venv en {venv_dir}…", flush=True)
        import venv as _venv
        try:
            _venv.EnvBuilder(with_pip=True, clear=False, upgrade_deps=False).create(venv_dir)
        except Exception as exc:
            print(f"❌ No se pudo crear el venv: {exc}", file=_sys.stderr)
            _sys.exit(1)

    # Verificar dependencias con un import-probe rápido.
    import subprocess as _sp
    probe = [str(venv_python), "-c", "import discord, loguru, aiosqlite"]
    missing = _sp.run(probe, capture_output=True).returncode != 0

    if missing:
        requirements = project_dir / "requirements.txt"
        if not requirements.exists():
            print("❌ requirements.txt no encontrado; no puedo instalar dependencias",
                  file=_sys.stderr)
            _sys.exit(1)
        print("📦 Instalando dependencias (primer arranque)…", flush=True)
        try:
            _sp.check_call([
                str(venv_python), "-m", "pip", "install",
                "--disable-pip-version-check",
                "-r", str(requirements),
            ])
        except _sp.CalledProcessError as exc:
            print(f"❌ Fallo instalando dependencias (código {exc.returncode})",
                  file=_sys.stderr)
            _sys.exit(1)

    # Re-ejecutar dentro del venv con los mismos argumentos.
    script = str(_Path(__file__).resolve())
    _os.execv(str(venv_python), [str(venv_python), script, *_sys.argv[1:]])


_bootstrap_venv()

# ── Suprimir ruido de librerías ANTES de los imports ─────────────────────
# Estas env vars se leen por las libs (sentence-transformers, hf_hub,
# transformers) al momento del import, por eso van aquí ANTES de importarlas.
import os
for _var, _val in (
    ("TQDM_DISABLE", "1"),
    ("HF_HUB_DISABLE_PROGRESS_BARS", "1"),
    ("HF_HUB_DISABLE_TELEMETRY", "1"),
    ("TRANSFORMERS_VERBOSITY", "error"),
    ("HF_HUB_DISABLE_SYMLINKS_WARNING", "1"),
    ("PYTHONWARNINGS", "ignore::FutureWarning,ignore::UserWarning"),
):
    os.environ.setdefault(_var, _val)

import os
os.environ["TQDM_DISABLE"] = "1"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import asyncio
import json
import logging
import platform
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands, tasks
from loguru import logger

from config import DjinnConfig
from utils.database import Database
from utils.nexus import DjinnNexus
from utils.orchestrator import Orchestrator
from utils.tts_engine import TTSEngine
from utils.embed_engine import EmbedEngine
from utils.llm_client import create_llm_client
from utils.api_server import create_api_server


# ── Logging bridge ────────────────────────────────────────────────────────────

class _LoguruInterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        try:
            msg = record.getMessage()
        except (TypeError, ValueError):
            msg = record.msg
            if record.args:
                try:
                    msg = msg.format(*record.args)
                except Exception:
                    msg = msg
                record.args = None
        logger.opt(depth=depth, exception=record.exc_info).log(level, msg)


def _setup_logging() -> None:
    Path("logs").mkdir(exist_ok=True)

    # ── Suprimir ruido de librerías ANTES de cualquier configuración ──────
    # tqdm/HuggingFace/sentence-transformers spamean barras de progreso por
    # cada batch de embeddings. Estas env vars deben estar ANTES de los imports
    # (que ya ocurrieron arriba), pero las defineamos por idempotencia.
    for var, val in (
        ("TQDM_DISABLE", "1"),
        ("HF_HUB_DISABLE_PROGRESS_BARS", "1"),
        ("HF_HUB_DISABLE_TELEMETRY", "1"),
        ("TRANSFORMERS_VERBOSITY", "error"),
        ("HF_HUB_DISABLE_SYMLINKS_WARNING", "1"),
    ):
        os.environ.setdefault(var, val)

    logging.basicConfig(handlers=[_LoguruInterceptHandler()], level=logging.INFO)

    # Silenciar loggers muy verbosos de librerías de terceros.
    for noisy in (
        "httpx", "httpcore", "urllib3",
        "huggingface_hub", "huggingface_hub.file_download",
        "transformers", "transformers.safetensors_conversion",
        "sentence_transformers", "sentence_transformers.SentenceTransformer",
        "filelock", "PIL", "matplotlib",
        "asyncio",  # silencia "Executing <Task...> took 0.5s"
        "discord.gateway",  # connect/disconnect spam
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger.remove()

    # ── Niveles con icono y color comfy (paleta no-saturada) ──────────────
    # Sage / amber / coral en lugar de bright primaries.
    try:
        logger.level("DEBUG",    no=10, icon="·", color="<fg #6c7980>")
        logger.level("INFO",     no=20, icon="▸", color="<fg #a3b18a>")
        logger.level("SUCCESS",  no=25, icon="✓", color="<fg #95d5b2>")
        logger.level("WARNING",  no=30, icon="⚠", color="<fg #e9c46a>")
        logger.level("ERROR",    no=40, icon="✗", color="<fg #e76f51>")
        logger.level("CRITICAL", no=50, icon="⛔", color="<fg #bc4749><bold>")
    except (TypeError, ValueError):
        # Loguru ya tiene los niveles definidos — solo actualizamos icon/color
        for name, icon, color in (
            ("DEBUG",    "·",  "<fg #6c7980>"),
            ("INFO",     "▸",  "<fg #a3b18a>"),
            ("WARNING",  "⚠",  "<fg #e9c46a>"),
            ("ERROR",    "✗",  "<fg #e76f51>"),
            ("CRITICAL", "⛔", "<fg #bc4749><bold>"),
        ):
            try:
                logger.level(name, icon=icon, color=color)
            except Exception:
                pass

    # ── Filtro: convierte name del módulo en tag "D J I N N · X" ────────
    def _djinn_tag(record: dict) -> bool:
        name = record["name"] or ""
        if name == "__main__":
            tag = "D J I N N"
        elif name.startswith("cogs."):
            tag = f"D J I N N · {name[5:]}"
        elif name.startswith("utils."):
            tag = f"D J I N N · {name[6:]}"
        elif name == "logging":
            # Mensajes redirigidos desde stdlib logging — usan logger root.
            # Mostramos solo el módulo emisor real si está disponible.
            tag = "discord" if "discord" in str(record.get("file") or "") else "·"
        else:
            tag = name.split(".")[0]  # solo top-level (discord, asyncio, etc.)
        # Truncar/padding para alineación
        record["extra"]["tag"] = tag[:30].ljust(30)
        return True

    # ── stderr: formato compacto y comfy ──────────────────────────────────
    # FIX (2026-05-16, SECURITY): diagnose=False + backtrace=False evitan que
    # loguru imprima los VALORES de las variables locales en los tracebacks.
    fmt_stderr = (
        "<dim>{time:HH:mm:ss}</> "
        "<level>{level.icon} {level: <8}</> "
        "<fg #8b95a1>{extra[tag]}</> "
        "<level>{message}</>"
    )
    logger.add(
        sys.stderr,
        format=fmt_stderr,
        level=os.environ.get("DJINN_LOG_LEVEL", os.environ.get("YOUKAI_LOG_LEVEL", "INFO")),
        colorize=True,
        backtrace=False,
        diagnose=False,
        filter=_djinn_tag,
    )

    # ── Archivo: formato detallado para forensia ──────────────────────────
    logger.add(
        "logs/fairy_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        backtrace=False,
        diagnose=False,
    )


# ── Cogs ──────────────────────────────────────────────────────────────────────

CRITICAL_COGS: list[str] = [
    "cogs.nlp_handler",
    "cogs.nexus_observer",
    "cogs.message_logger",
]

OPTIONAL_COGS: list[str] = [
    "cogs.admin",
    "cogs.moderation",
    "cogs.automod_v3",  # Automod PRIMARIO (motor 0-FP). Reemplaza a automod_v2 (deprecated).
    "cogs.info",
    "cogs.listeners",
    "cogs.torneo",
    "cogs.model_switcher",
    "cogs.dream_quest",
    "cogs.media_guard",
    "cogs.curse",
    "cogs.mouthwash",
    "cogs.dashboard_v2",
    # "cogs.zzz_rag",
    "cogs.server_memory",
    "cogs.zzz_builds",
    "cogs.synthtext",
    "cogs.credits_cmd",
    "cogs.loan_shark",
    "cogs.djinn_shares",
    "cogs.morosos",
    "cogs.birthdays",
    "cogs.recompensas",
    "cogs.music",
    "cogs.zzz_calendar",
    "cogs.treasury",  # D J I N N · B A N K: pool del servidor + /banco commands.
    "cogs.override_api",
    "cogs.aware",
    "cogs.db_maintenance",  # Wave 3 (F1.2 backup + F2.2 VACUUM): mantenimiento periódico de la DB.
    "cogs.idle_pinger",     # Posts hollow-knight gif after 1h of no activity in #channel.
    "cogs.conscious_mode",  # Autonomous moderation when Readers are inactive 60min+.
    "cogs.active_award",
    "cogs.role_persistence",
    "cogs.link_fixer",
    "cogs.actions",
]

# ── DjinnBot ──────────────────────────────────────────────────────────────────

class DjinnBot(commands.Bot):
    def __init__(self, config: DjinnConfig) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        intents.moderation = True

        super().__init__(
            command_prefix="§",
            intents=intents,
            help_command=None,
            max_messages=500,
        )

        self.config = config
        self.db: Optional[Database] = None
        self.nexus: Optional[DjinnNexus] = None
        self.llm = None
        self.orchestrator: Optional[Orchestrator] = None
        self.tts: Optional[TTSEngine] = None
        self.embedder: Optional[EmbedEngine] = None
        self.api_server = None

        self._svc_status: dict[str, bool] = {}
        self._start_time: float = time.time()

    async def setup_hook(self) -> None:
        await self._init_database()
        await self._init_nexus()
        await self._init_embedder()
        await self._init_llm()
        await self._init_orchestrator()
        await self._init_tts()

        cogs_ok, cogs_total, failed = await self._load_cogs()
        slash_ok = await self._sync_slash_commands()

        # Iniciar API server
        self.api_server = create_api_server(self, api_key=getattr(self.config, "api_key", None))
        await self.api_server.start()

        # Log resumen
        db_size_mb = 0.0
        try:
            db_path = Path(self.config.db_path)
            if db_path.exists():
                db_size_mb = db_path.stat().st_size / (1024 * 1024)
        except Exception:
            pass

        svc_line = " ".join(f"{n}:{'✓' if v else '✗'}" for n, v in self._svc_status.items() if v is not None)
        logger.info("Services: {} | Cogs: {}/{} | Slash: {} | DB: {:.1f}MB",
                    svc_line, cogs_ok, cogs_total, slash_ok, db_size_mb)

    async def close(self) -> None:
        logger.info("🛑 Shutting down…")
        if self.api_server:
            await self.api_server.stop()
        for svc_name in ("db", "nexus"):
            svc = getattr(self, svc_name, None)
            if svc:
                try:
                    await svc.close()
                except Exception as exc:
                    logger.warning("Error closing {}: {}", svc_name, exc)
        await super().close()
        logger.info("👋 Djinn stopped.")

    async def on_ready(self) -> None:
        guilds = len(self.guilds)
        total_members = sum(g.member_count or 0 for g in self.guilds)
        elapsed = time.time() - self._start_time

        logger.info(
            "🌸 Djinn online — {} | {} servers | ~{} members | {:.1f}s boot",
            self.user, guilds, total_members, elapsed,
        )

        if not self.daily_db_prune.is_running():
            self.daily_db_prune.start()

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="el servidor | Agent Mode",
            ),
            status=discord.Status.online,
        )

    async def _init_database(self) -> None:
        logger.debug("Database…")
        try:
            self.db = Database(self.config.db_path)
            await self.db.initialize()
            self._svc_status["DB"] = True
        except Exception as exc:
            self._svc_status["DB"] = False
            logger.critical("Database failed: {}", exc)
            raise

    async def _init_nexus(self) -> None:
        logger.debug("Nexus…")
        try:
            self.nexus = DjinnNexus(self.db)
            await self.nexus.initialize()
            self._svc_status["Nexus"] = True
        except Exception as exc:
            self._svc_status["Nexus"] = False
            logger.critical("Nexus failed: {}", exc)
            raise

    async def _init_embedder(self) -> None:
        logger.debug("EmbedEngine…")
        try:
            self.embedder = EmbedEngine(self.config)
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="embed") as pool:
                await loop.run_in_executor(pool, self.embedder.load)
            self._svc_status["Embed"] = self.embedder.available
            if not self.embedder.available:
                logger.warning("EmbedEngine: model not available")
        except Exception as exc:
            self._svc_status["Embed"] = False
            logger.warning("EmbedEngine failed (non-critical): {}", exc)
            self.embedder = EmbedEngine(self.config)

    async def _init_llm(self) -> None:
        provider = self.config.llm_provider.upper()
        logger.debug("LLM ({})…", provider)
        try:
            self.llm = create_llm_client(self.config)
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm_init") as pool:
                ok = await loop.run_in_executor(pool, self.llm.load)
            if ok:
                self._svc_status["LLM"] = True
            else:
                self._svc_status["LLM"] = False
                raise RuntimeError("LLMClient failed to load")
        except Exception as exc:
            self._svc_status["LLM"] = False
            logger.critical("LLM failed: {}", exc)
            raise

    async def _init_orchestrator(self) -> None:
        logger.debug("Orchestrator…")
        try:
            self.orchestrator = Orchestrator(self, self.llm)
            self._svc_status["Orch"] = True
        except Exception as exc:
            self._svc_status["Orch"] = False
            logger.critical("Orchestrator failed: {}", exc)
            raise

    async def _init_tts(self) -> None:
        if not self.config.tts_enabled:
            self._svc_status["TTS"] = None
            return
        logger.debug("TTS…")
        try:
            self.tts = TTSEngine(self.config)
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts") as pool:
                ok = await loop.run_in_executor(pool, self.tts.load)
            self._svc_status["TTS"] = ok
            if not ok:
                logger.warning("TTS not available")
                self.tts = None
        except Exception as exc:
            self._svc_status["TTS"] = False
            logger.warning("TTS failed (non-critical): {}", exc)
            self.tts = None

    @tasks.loop(hours=24)
    async def daily_db_prune(self) -> None:
        if not self.db:
            return
        try:
            deleted = await self.db.prune_old_messages(days=30)
            if deleted:
                logger.info("DB prune: {} messages removed (>30d)", deleted)
        except Exception as exc:
            logger.error("DB prune error: {}", exc)

    async def _load_cogs(self) -> tuple[int, int, list[str]]:
        failed_critical: list[str] = []
        failed_optional: list[str] = []

        for cog in CRITICAL_COGS:
            if not await self._load_single_cog(cog):
                failed_critical.append(cog)
        for cog in OPTIONAL_COGS:
            if not await self._load_single_cog(cog):
                failed_optional.append(cog)

        total = len(CRITICAL_COGS) + len(OPTIONAL_COGS)
        loaded = total - len(failed_critical) - len(failed_optional)
        failed = failed_critical + failed_optional

        if failed_optional:
            logger.warning("Optional cogs failed: {}", ", ".join(failed_optional))
        if failed_critical:
            names = ", ".join(failed_critical)
            logger.critical("CRITICAL cogs failed: {}", names)
            raise RuntimeError(f"Critical cogs not loaded: {names}")

        return loaded, total, failed

    async def _load_single_cog(self, cog: str) -> bool:
        try:
            await self.load_extension(cog)
            logger.debug("Cog OK: {}", cog)
            return True
        except Exception as exc:
            tag = "CRITICAL" if cog in CRITICAL_COGS else "optional"
            logger.error("Cog FAIL [{}]: {} — {}", tag, cog, exc)
            return False

    async def _sync_slash_commands(self) -> int:
        try:
            # Clear stale guild-scoped commands that cause duplicates.
            # (Legacy copy_global_to + guild sync left ghost registrations.)
            try:
                guild = discord.Object(id=1269877200488763472)
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
                logger.debug("Cleared guild-scoped commands (anti-duplicate)")
            except Exception:
                pass
            synced = await self.tree.sync()
            logger.debug("Slash commands synced: {}", len(synced))
            return len(synced)
        except Exception as exc:
            logger.warning("Slash sync failed: {}", exc)
            return 0

    async def notify_listener_change(self, action: str, guild_id: int, rule_id: str = '', rule: dict | None = None, enabled: bool = True) -> None:
        cog = self.get_cog('Listeners')
        if not cog:
            return
        try:
            if action == 'load' and rule:
                await cog.load_rule(guild_id, rule)
            elif action == 'toggle':
                await cog.toggle_rule(guild_id, rule_id, enabled)
            elif action == 'unload':
                await cog.unload_rule(guild_id, rule_id)
        except Exception as exc:
            logger.debug("Listener hot-reload skipped: {}", exc)


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    _setup_logging()
    config = DjinnConfig.from_env()

    _model_config = Path("data/model_config.json")
    if _model_config.exists():
        try:
            overrides = json.loads(_model_config.read_text())
            if "llm_provider" in overrides:
                config.llm_provider = overrides["llm_provider"]
            for key in ("google_model_name", "openrouter_model_name",
                         "custom_model_name", "custom_disable_thinking",
                         "nim_model_name", "kiro_model_name"):
                if key in overrides:
                    setattr(config, key, overrides[key])
        except (json.JSONDecodeError, KeyError, OSError):
            logger.warning("Failed to load model_config.json")

    if not config.discord_token:
        print("❌ DISCORD_TOKEN not found")
        sys.exit(1)
    if config.llm_provider == "google" and not config.google_api_key:
        print("❌ GOOGLE_API_KEY not found")
        sys.exit(1)
    if config.llm_provider == "openrouter" and not config.openrouter_api_key:
        print("❌ OPENROUTER_API_KEY not found")
        sys.exit(1)
    if config.llm_provider == "custom" and not config.custom_api_key:
        print("❌ CUSTOM_API_KEY not found")
        sys.exit(1)
    if config.llm_provider == "kiro" and not config.kiro_api_key:
        print("❌ KIRO_API_KEY not found")
        sys.exit(1)

    bot = DjinnBot(config)

    logger.info("🌸 Djinn LV999 booting…")
    logger.info("Python {} · discord.py {} · {}", 
                platform.python_version(), discord.__version__, platform.machine())
    logger.info("API interna: http://127.0.0.1:8080")

    try:
        bot.run(config.discord_token, log_handler=None, reconnect=True)
    except KeyboardInterrupt:
        pass
    except discord.LoginFailure:
        logger.critical("Invalid Discord token")
        sys.exit(1)
    except RuntimeError as exc:
        logger.critical("Fatal: {}", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
