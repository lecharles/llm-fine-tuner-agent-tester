#!/bin/bash
# S23 (#26): macOS local-runtime installer — the "one command" path.
#
#   curl -fsSL https://raw.githubusercontent.com/lecharles/llm-fine-tuner-agent-tester/main/install/macos.sh | bash
#
# Also runs from install/macos-installer.command (the "one file", double-click
# path). Everything lands under ~/.llmtuner; the training engine is MLX, so
# this script only runs on Apple Silicon / macOS and refuses elsewhere.
#
# What it does (idempotent — re-running = update):
#   1. Guards: macOS only, Xcode Command Line Tools, git
#   2. Ensures Python 3.12+ (installs python@3.12 via Homebrew when missing)
#   3. Clones or pulls the repo into ~/.llmtuner
#   4. Creates/reuses .venv, installs backend deps + mlx-lm (Mac training engine)
#   5. Builds the frontend if npm is available (skips with a notice otherwise)
#   6. Installs Ollama via Homebrew unless LLMTUNER_SKIP_OLLAMA=1
#   7. Symlinks `llmtuner` into ~/.local/bin and adds the PATH line to ~/.zshrc
#   8. Runs `llmtuner doctor` and prints next steps
#
# Non-interactive by design (safe for curl | bash): it never asks for input and
# never writes secrets. API keys are optional later — edit ~/.llmtuner/.env.
#
# Overrides: LLMTUNER_INSTALL_DIR (default ~/.llmtuner), LLMTUNER_SKIP_OLLAMA=1.

set -eo pipefail

REPO_URL="https://github.com/lecharles/llm-fine-tuner-agent-tester.git"
INSTALL_DIR="${LLMTUNER_INSTALL_DIR:-$HOME/.llmtuner}"

say()  { printf '✅ %s\n' "$1"; }
step() { printf '\n🎸 %s\n' "$1"; }
warn() { printf '⚠️  %s\n' "$1"; }
die()  { printf '❌ %s\n' "$1"; exit 1; }

# --- Guard: macOS only -------------------------------------------------------
[ "$(uname -s)" = "Darwin" ] || die "This installer is macOS-only (training needs MLX on Apple Silicon). For the VPS/team instance use the root install.sh flow instead."

# --- Prereqs: Command Line Tools + git ---------------------------------------
step "Checking prerequisites"
if ! xcode-select -p >/dev/null 2>&1; then
    die "Xcode Command Line Tools missing. Run \`xcode-select --install\` (a GUI dialog will pop up), then re-run this installer."
fi
say "Xcode Command Line Tools present"
command -v git >/dev/null 2>&1 || die "git not found even with CLT installed. Open a new Terminal and retry."
say "git $(git --version | awk '{print $3}')"

HAS_BREW=0
command -v brew >/dev/null 2>&1 && HAS_BREW=1

py_ok() {
    # $1: python binary; returns 0 when it is 3.12+
    command -v "$1" >/dev/null 2>&1 || return 1
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'
}

# --- Python 3.12+ ------------------------------------------------------------
step "Locating Python 3.12+"
PYTHON_BIN=""
for cand in python3.12 python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if py_ok "$cand"; then PYTHON_BIN="$cand"; break; fi
done
if [ -z "$PYTHON_BIN" ] && [ "$HAS_BREW" = "1" ]; then
    warn "No Python 3.12+ found — installing python@3.12 via Homebrew"
    brew install python@3.12
    for cand in "$(brew --prefix)/bin/python3.12" python3.12; do
        if py_ok "$cand"; then PYTHON_BIN="$cand"; break; fi
    done
fi
[ -n "$PYTHON_BIN" ] || die "Python 3.12+ is required. Install Homebrew (https://brew.sh) and re-run, or install Python from https://python.org."
say "$("$PYTHON_BIN" --version)"

# --- Repo: clone or update ---------------------------------------------------
step "Placing the local runtime"
if [ -d "$INSTALL_DIR/.git" ]; then
    say "Updating existing install at $INSTALL_DIR"
    git -C "$INSTALL_DIR" pull --quiet
else
    [ -e "$INSTALL_DIR" ] && die "$INSTALL_DIR exists but is not a git checkout. Move it away or set LLMTUNER_INSTALL_DIR."
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    say "Cloned into $INSTALL_DIR"
fi

# --- venv + backend deps (MLX lives here) ------------------------------------
step "Setting up the Python environment (.venv)"
cd "$INSTALL_DIR"
if [ ! -x .venv/bin/python ]; then
    "$PYTHON_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet \
    fastapi 'uvicorn[standard]' sqlalchemy alembic pydantic-settings \
    python-dotenv 'passlib[bcrypt]' 'python-jose[cryptography]' \
    'pydantic[email]' python-multipart bcrypt==4.0.1 httpx \
    anthropic openai datasets mlx-lm
say "Backend + mlx-lm installed"

if [ ! -f .env ]; then
    cat > .env <<'ENVSTUB'
# LLM Tuner env (created by install/macos.sh).
# Add optional provider keys later, one KEY=value line per key.
ENVSTUB
    chmod 600 .env
fi
say "~/.llmtuner/.env ready (add API keys there later if you want hosted compare)"

# --- Frontend build ----------------------------------------------------------
step "Building the web UI"
if command -v npm >/dev/null 2>&1; then
    (cd frontend && npm ci --silent && npm run build >/dev/null)
    say "Frontend built"
else
    warn "npm not found — skipping the UI build. Install Node 18+ (brew install node) and re-run to get the browser shell."
fi

# --- Ollama (local generation) -----------------------------------------------
step "Ollama for local generation"
if [ "${LLMTUNER_SKIP_OLLAMA:-0}" = "1" ]; then
    warn "Skipped by LLMTUNER_SKIP_OLLAMA=1 (compare/auto-select of local models will be unavailable)"
elif command -v ollama >/dev/null 2>&1; then
    say "Ollama already installed"
elif [ "$HAS_BREW" = "1" ]; then
    brew install ollama >/dev/null
    say "Ollama installed via Homebrew (start it with \`ollama serve\` or the Ollama app)"
else
    warn "No Homebrew — install Ollama from https://ollama.com if you want local generation"
fi

# --- CLI launcher on PATH ----------------------------------------------------
step "Installing the \`llmtuner\` command"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/llmtuner" <<EOF
#!/bin/bash
cd "$INSTALL_DIR"
. .venv/bin/activate
python -m cli.llmtuner "\$@"
EOF
chmod +x "$HOME/.local/bin/llmtuner"
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    if ! grep -q '.local/bin' "$HOME/.zshrc" 2>/dev/null; then
        printf '\n# llmtuner CLI (added by install/macos.sh)\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.zshrc"
    fi
    warn "Added ~/.local/bin to PATH in ~/.zshrc — open a new Terminal for \`llmtuner\` to resolve"
fi
say "launcher ready: ~/.local/bin/llmtuner"

# --- Doctor + summary --------------------------------------------------------
step "Preflight (llmtuner doctor)"
"$HOME/.local/bin/llmtuner" doctor || warn "doctor reported issues — see output above"

echo
say "Local runtime installed at $INSTALL_DIR"
echo "Next steps:"
echo "  llmtuner doctor   # re-check the environment any time"
echo "  llmtuner up       # start the app (http://localhost:8000)"
