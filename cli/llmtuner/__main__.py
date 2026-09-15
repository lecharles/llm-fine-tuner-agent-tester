"""Phase 6 slice 4: llmtuner CLI launcher.

Usage:
    python -m llmtuner up [--port 8000] [--local]
    python -m llmtuner doctor
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def check_apple_silicon() -> tuple[bool, str]:
    """Check if running on Apple Silicon (required for MLX training)."""
    if platform.system() != "Darwin":
        return False, "Not macOS (MLX requires Apple Silicon)"
    arch = platform.machine()
    if arch != "arm64":
        return False, f"Architecture is {arch}, not arm64"
    return True, "Apple Silicon detected"


def check_mlx_lm() -> tuple[bool, str]:
    """Check if mlx-lm is installed."""
    try:
        import mlx_lm
        return True, f"mlx-lm {mlx_lm.__version__ if hasattr(mlx_lm, '__version__') else 'installed'}"
    except ImportError:
        return False, "mlx-lm not installed (pip install mlx-lm)"


def check_ollama() -> tuple[bool, str]:
    """Check if Ollama is installed and running."""
    if not shutil.which("ollama"):
        return False, "Ollama not found (https://ollama.ai)"
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
        if result.returncode == 0:
            return True, "Ollama running"
        return False, "Ollama installed but not responding"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, "Ollama not responding"


def check_disk_space(min_gb: int = 10) -> tuple[bool, str]:
    """Check if there's enough disk space."""
    home = Path.home()
    stat = shutil.disk_usage(home)
    free_gb = stat.free / (1024**3)
    if free_gb < min_gb:
        return False, f"Only {free_gb:.1f}GB free (need {min_gb}GB)"
    return True, f"{free_gb:.1f}GB free"


def doctor():
    """Run all preflight checks and report status."""
    print("🔍 llmtuner preflight checks\n")
    checks = [
        ("Apple Silicon", check_apple_silicon),
        ("mlx-lm", check_mlx_lm),
        ("Ollama", check_ollama),
        ("Disk space", check_disk_space),
    ]
    all_pass = True
    for name, check_fn in checks:
        ok, msg = check_fn()
        status = "✅" if ok else "❌"
        print(f"{status} {name}: {msg}")
        if not ok:
            all_pass = False
    print()
    if all_pass:
        print("All checks passed. Ready to fine-tune!")
    else:
        print("Some checks failed. Fix the issues above before running 'llmtuner up'.")
    return 0 if all_pass else 1


def up(port: int = 8000, local: bool = True):
    """Start the llmtuner server."""
    print(f"🚀 Starting llmtuner on port {port}...")

    # Run preflight (non-blocking warnings for non-critical checks)
    print("\n🔍 Preflight checks:")
    checks = [
        ("Apple Silicon", check_apple_silicon),
        ("mlx-lm", check_mlx_lm),
        ("Ollama", check_ollama),
        ("Disk space", check_disk_space),
    ]
    warnings = []
    for name, check_fn in checks:
        ok, msg = check_fn()
        status = "✅" if ok else "⚠️ "
        print(f"  {status} {name}: {msg}")
        if not ok:
            warnings.append(name)

    if warnings:
        print(f"\n⚠️  Warnings: {', '.join(warnings)}")
        print("   Training may not work, but the UI will start.\n")

    # Find the backend directory
    # CLI is at cli/llmtuner/__main__.py, backend is at backend/
    backend_dir = Path(__file__).parent.parent.parent / "backend"
    if not backend_dir.exists():
        print(f"❌ Backend not found at {backend_dir}")
        return 1

    # Run migrations
    print("📦 Running database migrations...")
    env = os.environ.copy()
    if local:
        env["LOCAL_MODE"] = "true"

    # Use the venv's Python if it exists, otherwise fall back to sys.executable
    venv_python = backend_dir / ".venv-smoke" / "bin" / "python"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable

    migrate = subprocess.run(
        [python_exe, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
    )
    if migrate.returncode != 0:
        print("❌ Migration failed")
        return 1

    # Start the server
    print(f"\n🌐 Server starting at http://localhost:{port}")
    print("   Press Ctrl+C to stop\n")

    # Open the browser only once the server actually answers /health, so the
    # first page the user ever sees is a real one, not connection-refused.
    def wait_and_open():
        import urllib.request

        url = f"http://127.0.0.1:{port}/health"
        deadline = time.time() + 60
        ready = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                pass
            time.sleep(0.5)
        if not ready:
            print("⚠️  Server not answering /health after 60s — opening the browser anyway.")
        webbrowser.open(f"http://localhost:{port}")

    import threading
    threading.Thread(target=wait_and_open, daemon=True).start()

    # Start uvicorn
    try:
        subprocess.run(
            [python_exe, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=backend_dir,
            env=env,
        )
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped")

    return 0


def main():
    parser = argparse.ArgumentParser(description="llmtuner CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # up command
    up_parser = subparsers.add_parser("up", help="Start the llmtuner server")
    up_parser.add_argument("--port", type=int, default=8000, help="Port to run on (default: 8000)")
    up_parser.add_argument("--local", action="store_true", default=True, help="Run in local mode (default: True)")

    # doctor command
    subparsers.add_parser("doctor", help="Run preflight checks")

    args = parser.parse_args()

    if args.command == "up":
        sys.exit(up(port=args.port, local=args.local))
    elif args.command == "doctor":
        sys.exit(doctor())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
