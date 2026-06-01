#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║           Fairy Agent — Instalador Ubuntu 22.04 ARM64           ║
# ╚══════════════════════════════════════════════════════════════════╝
set -euo pipefail

# ── Colores ────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()    { echo -e "\n${BOLD}━━━ $* ━━━${NC}"; }

# ── Verificaciones previas ─────────────────────────────────────────
step "Verificando entorno"

if [[ $EUID -eq 0 ]]; then
    warn "Ejecutando como root. Se recomienda un usuario con sudo."
fi

ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
    warn "Arquitectura detectada: $ARCH. Este instalador está optimizado para ARM64/aarch64."
fi

# Verificar Ubuntu 22.04
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    if [[ "$ID" != "ubuntu" ]]; then
        warn "SO detectado: $ID. Optimizado para Ubuntu."
    fi
else
    warn "No se pudo detectar la versión del SO."
fi

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
info "Directorio de instalación: $INSTALL_DIR"

# ── Python ─────────────────────────────────────────────────────────
step "Verificando Python 3.11+"

if command -v python3.11 &>/dev/null; then
    PYTHON_BIN="python3.11"
    success "Python 3.11 encontrado: $(python3.11 --version)"
elif command -v python3.10 &>/dev/null; then
    PYTHON_BIN="python3.10"
    warn "Python 3.10 encontrado (3.11+ recomendado): $(python3.10 --version)"
elif command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"; then
        PYTHON_BIN="python3"
        warn "Usando python3 ($PY_VERSION). Se recomienda 3.11."
    else
        info "Instalando Python 3.11..."
        sudo apt-get update -qq
        sudo apt-get install -y software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa
        sudo apt-get update -qq
        sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
        PYTHON_BIN="python3.11"
    fi
else
    info "Python no encontrado. Instalando 3.11..."
    sudo apt-get update -qq
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -qq
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
    PYTHON_BIN="python3.11"
fi

# ── Dependencias del sistema ───────────────────────────────────────
step "Instalando dependencias del sistema"

sudo apt-get update -qq
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    ffmpeg \
    libopus0 \
    libopus-dev \
    libcairo2 \
    libcairo2-dev \
    libglib2.0-dev \
    pkg-config \
    git \
    curl \
    wget \
    unzip \
    sqlite3 \
    libsodium-dev \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    2>/dev/null || warn "Algunos paquetes no pudieron instalarse, continuando..."

success "Dependencias del sistema instaladas."

# ── Entorno virtual ────────────────────────────────────────────────
step "Creando entorno virtual"

VENV_DIR="$INSTALL_DIR/venv"
if [[ -d "$VENV_DIR" ]]; then
    warn "Entorno virtual existente encontrado en $VENV_DIR. Reutilizando."
else
    $PYTHON_BIN -m venv "$VENV_DIR"
    success "Entorno virtual creado en $VENV_DIR"
fi

# Activar venv
source "$VENV_DIR/bin/activate"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

$PIP install --upgrade pip setuptools wheel -q
success "pip actualizado."

# ── Paquetes Python ────────────────────────────────────────────────
step "Instalando paquetes Python"

# opencv-python-headless puede tener problemas en ARM; intentar la versión headless primero
info "Instalando dependencias principales..."
$PIP install --upgrade \
    "discord.py>=2.4.0" \
    "PyNaCl>=1.5.0" \
    "google-genai>=1.0.0" \
    "aiosqlite>=0.20.0" \
    "loguru>=0.7.2" \
    "python-dotenv>=1.0.0" \
    -q && success "Core packages OK" || error "Error instalando paquetes core."

info "Instalando sentence-transformers (puede tardar en ARM64)..."
$PIP install "sentence-transformers>=3.3.0" -q \
    && success "sentence-transformers OK" \
    || warn "sentence-transformers falló. EmbedEngine no estará disponible."

info "Instalando opencv-python-headless..."
$PIP install "opencv-python-headless>=4.8.0" -q \
    && success "opencv OK" \
    || {
        warn "opencv-python-headless falló. Intentando compilar desde fuente..."
        $PIP install opencv-python-headless -q --no-binary opencv-python-headless \
            && success "opencv compilado OK" \
            || warn "opencv no disponible. El procesamiento de vídeo estará desactivado."
    }

info "Instalando cairosvg y Pillow..."
$PIP install "cairosvg>=2.7.0" "Pillow>=10.0.0" -q \
    && success "cairosvg + Pillow OK" \
    || warn "cairosvg falló. SVGEngine no estará disponible."

# ── Directorios necesarios ─────────────────────────────────────────
step "Creando estructura de directorios"

mkdir -p "$INSTALL_DIR/db"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/models/piper"
mkdir -p "$INSTALL_DIR/models/embed"
mkdir -p "$INSTALL_DIR/data"

# Crear archivos de datos si no existen
if [[ ! -f "$INSTALL_DIR/data/fairy_responses.json" ]]; then
    echo '{}' > "$INSTALL_DIR/data/fairy_responses.json"
fi
if [[ ! -f "$INSTALL_DIR/data/bad_domains.txt" ]]; then
    touch "$INSTALL_DIR/data/bad_domains.txt"
fi

success "Estructura de directorios lista."

# ── Configuración .env ─────────────────────────────────────────────
step "Configuración de variables de entorno"

ENV_FILE="$INSTALL_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
    warn ".env ya existe. Se omite la configuración interactiva."
    warn "Edita $ENV_FILE manualmente si necesitas cambiar algo."
else
    echo ""
    echo -e "${BOLD}Necesitas los siguientes tokens para ejecutar Fairy:${NC}"
    echo "  1. Discord Bot Token  → https://discord.com/developers/applications"
    echo "  2. Google API Key     → https://aistudio.google.com/apikey"
    echo ""

    read -rp "$(echo -e "${CYAN}Discord Bot Token:${NC} ")" DISCORD_TOKEN
    read -rp "$(echo -e "${CYAN}Google API Key:${NC} ")" GOOGLE_API_KEY
    read -rp "$(echo -e "${CYAN}Modelo de Google (Enter = gemma-4-26b-a4b-it):${NC} ")" GOOGLE_MODEL
    GOOGLE_MODEL="${GOOGLE_MODEL:-gemma-4-26b-a4b-it}"

    cat > "$ENV_FILE" << ENV_CONTENT
# ── Fairy Agent — Variables de entorno ──────────────────────────────────
# Generado automáticamente por install.sh

# ── Discord ──────────────────────────────────────────────────────────────
DISCORD_TOKEN=${DISCORD_TOKEN}

# ── Google AI Studio ─────────────────────────────────────────────────────
GOOGLE_API_KEY=${GOOGLE_API_KEY}
GOOGLE_MODEL_NAME=${GOOGLE_MODEL}

# ── Base de datos ─────────────────────────────────────────────────────────
DB_PATH=db/fairy.db

# ── Piper TTS (opcional) ──────────────────────────────────────────────────
TTS_ENABLED=false
PIPER_BIN=piper
PIPER_MODEL=models/piper/es_ES-low.onnx
PIPER_CONFIG=models/piper/es_ES-low.onnx.json

# ── Embeddings ────────────────────────────────────────────────────────────
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBED_CACHE_DIR=models/embed

# ── Rutas de datos ────────────────────────────────────────────────────────
RESPONSES_PATH=data/fairy_responses.json
BAD_DOMAINS_PATH=data/bad_domains.txt

# ── SVG ───────────────────────────────────────────────────────────────────
SVG_ENABLED=true
ENV_CONTENT

    chmod 600 "$ENV_FILE"
    success ".env creado correctamente."
fi

# ── Modelos OPUS-MT para la Maldición (es→is/mt/xh/pap/eo) ─────────
step "Descargando modelos OPUS-MT (traductor de la Maldición)"

info "Se descargarán 5 modelos MarianMT (~1.2 GB total, cache en ~/.cache/huggingface/)."
if "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/scripts/download_opusmt.py"; then
    success "Modelos OPUS-MT listos."
else
    warn "Algún modelo falló. CurseTranslator degradará a los idiomas disponibles."
    warn "Podés reintentar con: python scripts/download_opusmt.py"
fi

# ── Piper TTS (opcional) ───────────────────────────────────────────
step "Piper TTS (opcional)"

echo ""
read -rp "$(echo -e "${CYAN}¿Deseas instalar Piper TTS para voz? [s/N]:${NC} ")" INSTALL_PIPER
INSTALL_PIPER="${INSTALL_PIPER:-N}"

if [[ "$INSTALL_PIPER" =~ ^[sS]$ ]]; then
    PIPER_URL="https://github.com/rhasspy/piper/releases/latest/download/piper_linux_aarch64.tar.gz"
    info "Descargando Piper para ARM64..."
    cd /tmp
    wget -q "$PIPER_URL" -O piper_aarch64.tar.gz \
        && tar -xzf piper_aarch64.tar.gz \
        && sudo mv piper/piper /usr/local/bin/ \
        && sudo chmod +x /usr/local/bin/piper \
        && success "Piper instalado en /usr/local/bin/piper" \
        || warn "No se pudo descargar Piper. Actívalo manualmente más tarde."
    cd "$INSTALL_DIR"

    # Descargar modelo de voz español
    info "Descargando modelo de voz (es_ES-low)..."
    VOICE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/low/es_ES-low.onnx"
    VOICE_JSON_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/low/es_ES-low.onnx.json"
    wget -q "$VOICE_URL" -O "$INSTALL_DIR/models/piper/es_ES-low.onnx" \
        && wget -q "$VOICE_JSON_URL" -O "$INSTALL_DIR/models/piper/es_ES-low.onnx.json" \
        && success "Modelo de voz descargado." \
        || warn "No se pudo descargar el modelo de voz. Descárgalo manualmente."

    # Activar TTS en .env
    sed -i 's/TTS_ENABLED=false/TTS_ENABLED=true/' "$ENV_FILE"
else
    info "Piper TTS omitido. Puedes activarlo más tarde editando .env (TTS_ENABLED=true)."
fi

# ── Script de inicio ───────────────────────────────────────────────
step "Creando script de inicio"

cat > "$INSTALL_DIR/start.sh" << 'STARTSCRIPT'
#!/usr/bin/env bash
cd "$(dirname "${BASH_SOURCE[0]}")"
source venv/bin/activate
exec python main.py
STARTSCRIPT
chmod +x "$INSTALL_DIR/start.sh"
success "start.sh creado."

# ── Servicio systemd ───────────────────────────────────────────────
step "Configuración de servicio systemd (opcional)"

echo ""
read -rp "$(echo -e "${CYAN}¿Crear servicio systemd para arranque automático? [s/N]:${NC} ")" SETUP_SYSTEMD
SETUP_SYSTEMD="${SETUP_SYSTEMD:-N}"

if [[ "$SETUP_SYSTEMD" =~ ^[sS]$ ]]; then
    CURRENT_USER="${SUDO_USER:-$USER}"
    SERVICE_FILE="/etc/systemd/system/fairy-bot.service"

    sudo tee "$SERVICE_FILE" > /dev/null << SVCEOF
[Unit]
Description=Fairy Discord Bot Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/main.py
Restart=always
RestartSec=10
StandardOutput=append:${INSTALL_DIR}/logs/fairy.log
StandardError=append:${INSTALL_DIR}/logs/fairy.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF

    sudo systemctl daemon-reload
    sudo systemctl enable fairy-bot.service
    success "Servicio fairy-bot.service instalado y habilitado."
    echo ""
    echo -e "  ${BOLD}Comandos útiles:${NC}"
    echo -e "  ${CYAN}sudo systemctl start fairy-bot${NC}   — Iniciar"
    echo -e "  ${CYAN}sudo systemctl stop fairy-bot${NC}    — Parar"
    echo -e "  ${CYAN}sudo systemctl status fairy-bot${NC}  — Estado"
    echo -e "  ${CYAN}sudo journalctl -u fairy-bot -f${NC}  — Logs en tiempo real"
fi

# ── Verificación final ─────────────────────────────────────────────
step "Verificación final"

source "$VENV_DIR/bin/activate"
if $PYTHON -c "import discord, aiosqlite, loguru, google.genai" 2>/dev/null; then
    success "Importaciones críticas OK."
else
    warn "Algunas importaciones fallaron. Revisa los logs anteriores."
fi

# ── Resumen ────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✅  Fairy Agent instalado correctamente          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Para iniciar manualmente:${NC}"
echo -e "  ${CYAN}cd $INSTALL_DIR && ./start.sh${NC}"
echo ""
if [[ -f "$ENV_FILE" ]]; then
    echo -e "  ${BOLD}Configuración en:${NC} $ENV_FILE"
fi
echo -e "  ${BOLD}Logs en:${NC} $INSTALL_DIR/logs/"
echo ""
