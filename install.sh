#!/bin/bash
# Phase 6 slice 5: llmtuner installer.
# Usage: curl -fsSL https://raw.githubusercontent.com/lecharles/llm-fine-tuner-agent-tester/main/install.sh | bash
#
# What this does:
#   1. Checks for Python 3.12+
#   2. Clones the repo (or updates if already present)
#   3. Creates a venv and installs dependencies
#   4. Builds the frontend
#   5. Creates a symlink so `llmtuner` is on PATH
#   6. Runs doctor to verify

set -euo pipefail

INSTALL_DIR="${LLMTUNER_INSTALL_DIR:-$HOME/.llmtuner}"
REPO_URL="https://github.com/lecharles/llm-fine-tuner-agent-tester.git"

echo "🎸 llmtuner installer"
echo "   Install directory: $INSTALL_DIR"
echo

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install Python 3.12+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 12 ]); then
    echo "❌ Python $PYTHON_VERSION found, but 3.12+ is required."
    exit 1
fi

echo "✅ Python $PYTHON_VERSION"

# Clone or update the repo
if [ -d "$INSTALL_DIR" ]; then
    echo "📦 Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --quiet
else
    echo "📦 Cloning repository..."
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Create venv
echo "🐍 Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install backend dependencies
echo "📦 Installing backend dependencies..."
pip install --quiet --upgrade pip
pip install --quiet \
    fastapi 'uvicorn[standard]' sqlalchemy alembic pydantic-settings \
    python-dotenv 'passlib[bcrypt]' 'python-jose[cryptography]' \
    'pydantic[email]' python-multipart bcrypt==4.0.1 httpx \
    anthropic openai datasets

# Install frontend dependencies and build
echo "🎨 Building frontend..."
cd frontend
if command -v npm &> /dev/null; then
    npm ci --silent
    npm run build
else
    echo "⚠️  npm not found, skipping frontend build. Install Node.js 18+ to build the UI."
fi
cd ..

# Create symlink
echo "🔗 Creating llmtuner command..."
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/llmtuner" <<EOF
#!/bin/bash
cd "$INSTALL_DIR"
source .venv/bin/activate
python3 -m cli.llmtuner "\$@"
EOF
chmod +x "$HOME/.local/bin/llmtuner"

# Check if ~/.local/bin is on PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo
    echo "⚠️  ~/.local/bin is not on your PATH."
    echo "   Add this to your ~/.zshrc or ~/.bashrc:"
    echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo
fi

# Run doctor
echo
echo "🔍 Running preflight checks..."
"$HOME/.local/bin/llmtuner" doctor

echo
echo "✅ Installation complete!"
echo
echo "Next steps:"
echo "  llmtuner up          # start the app"
echo "  llmtuner doctor      # check prerequisites"
echo
echo "The app will open at http://localhost:8000"
