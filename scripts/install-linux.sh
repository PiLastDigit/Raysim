#!/usr/bin/env bash
#
# Install RaySim on Linux/macOS with all dependencies (including pythonocc-core).
#
# This script:
#   1. Downloads micromamba if not present
#   2. Creates a conda environment with pythonocc-core, PySide6, and all UI deps
#   3. Installs raysim into the environment in editable mode
#   4. Creates a launcher script
#
# Run from the raysim project root:
#   bash scripts/install-linux.sh
#
# Requires: curl, tar, internet connection
# Downloads: ~500 MB (pythonocc-core + Qt + OCCT + Python)
# Disk usage: ~2.5 GB after install

set -euo pipefail

ENV_NAME="raysim-ui"
PYTHON_VERSION="3.12"
OCCT_VERSION="7.9.0"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAMBA_ROOT="$PROJECT_ROOT/.micromamba"
MAMBA_EXE="$PROJECT_ROOT/bin/micromamba"

echo ""
echo "========================================"
echo "  RaySim Installer for Linux/macOS"
echo "========================================"
echo ""
echo "Project root: $PROJECT_ROOT"
echo ""

# --- Step 1: Micromamba ---
if [ -x "$MAMBA_EXE" ]; then
    echo "[1/4] micromamba already installed"
else
    echo "[1/4] Downloading micromamba..."
    mkdir -p "$(dirname "$MAMBA_EXE")"

    ARCH="$(uname -m)"
    OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
    if [ "$OS" = "darwin" ]; then
        PLATFORM="osx-arm64"
        [ "$ARCH" = "x86_64" ] && PLATFORM="osx-64"
    else
        PLATFORM="linux-64"
        [ "$ARCH" = "aarch64" ] && PLATFORM="linux-aarch64"
    fi

    curl -Ls "https://micro.mamba.pm/api/micromamba/$PLATFORM/latest" | tar -xvj -C "$PROJECT_ROOT" bin/micromamba
    echo "  Installed to $MAMBA_EXE"
fi

export MAMBA_ROOT_PREFIX="$MAMBA_ROOT"

# --- Step 2: Create conda environment ---
ENV_PATH="$MAMBA_ROOT/envs/$ENV_NAME"
if [ -d "$ENV_PATH" ]; then
    echo "[2/4] Environment '$ENV_NAME' already exists"
    echo "  To recreate: rm -rf $ENV_PATH and re-run"
else
    echo "[2/4] Creating environment '$ENV_NAME' (this downloads ~500 MB)..."
    echo "  Python $PYTHON_VERSION + pythonocc-core $OCCT_VERSION + PySide6 + matplotlib"
    echo ""
    "$MAMBA_EXE" create -n "$ENV_NAME" \
        "python=$PYTHON_VERSION" \
        "pythonocc-core=$OCCT_VERSION" \
        pyside6 matplotlib pyqtgraph \
        -c conda-forge -y
    echo "  Environment created"
fi

# --- Step 3: Install raysim ---
echo "[3/4] Installing raysim into the environment..."
"$MAMBA_EXE" run -n "$ENV_NAME" pip install -e "$PROJECT_ROOT[ray,ui]" --quiet
"$MAMBA_EXE" run -n "$ENV_NAME" raysim --version
echo "  raysim installed"

# --- Step 4: Create launcher script ---
echo "[4/4] Creating launcher script..."

LAUNCHER="$PROJECT_ROOT/raysim.sh"
cat > "$LAUNCHER" << EOF
#!/usr/bin/env bash
export MAMBA_ROOT_PREFIX="$MAMBA_ROOT"
exec "$MAMBA_EXE" run -n "$ENV_NAME" raysim "\$@"
EOF
chmod +x "$LAUNCHER"
echo "  Created $LAUNCHER"

echo ""
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""
echo "  To launch the GUI:"
echo "    ./raysim.sh gui"
echo ""
echo "  To use the CLI:"
echo "    ./raysim.sh run --scene ... --materials ... --detectors ... --dose-curve ... --out run.json"
echo ""
echo "  To run tests:"
echo "    ./raysim.sh --version"
echo ""
