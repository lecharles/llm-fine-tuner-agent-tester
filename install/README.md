# install/ — macOS local runtime (S23, issue #26)

Goal from the Phase 6 ADR: **one command or one file** places the local
runtime on Carlos-style Macs — the repo checkout, a Python venv with the MLX
training engine, the built web shell, the `llmtuner` CLI, and (optionally)
Ollama for local generation. Everything lives under `~/.llmtuner`.

## Path A — one command (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/lecharles/llm-fine-tuner-agent-tester/main/install/macos.sh | bash
```

## Path B — one file (double-click)

1. Download `macos-installer.command` (from this folder on GitHub: raw view →
   Save Link As…), or copy the whole repo and open `install/`.
2. Double-click it. If Gatekeeper blocks the first run: right-click → **Open**
   → **Open**, or `xattr -d com.apple.quarantine macos-installer.command`.
3. A Terminal window runs the installer (it delegates to `install/macos.sh`).

## What the installer does

1. Guards: refuses to run on anything but macOS (MLX needs Apple Silicon);
   checks Xcode Command Line Tools + git.
2. Ensures Python **3.12+** — installs `python@3.12` via Homebrew when missing.
3. Clones the repo into `~/.llmtuner` (re-running = `git pull`, it's idempotent).
4. Creates `~/.llmtuner/.venv` and installs backend deps + **mlx-lm**
   (the training engine), then writes an empty, key-free `~/.llmtuner/.env`
   (chmod 600) you can add `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` to later.
5. Builds the frontend if `npm` is available; otherwise skips with a notice.
6. Installs **Ollama** via Homebrew unless `LLMTUNER_SKIP_OLLAMA=1`.
7. Links `llmtuner` into `~/.local/bin` (adds the PATH line to `~/.zshrc`).
8. Runs `llmtuner doctor` and prints next steps (`llmtuner up`).

Overrides: `LLMTUNER_INSTALL_DIR` (default `~/.llmtuner`),
`LLMTUNER_SKIP_OLLAMA=1`. The script is non-interactive (never prompts, never
handles secrets) so it is safe over `curl | bash`.

## Uninstall

```bash
rm -rf ~/.llmtuner ~/.local/bin/llmtuner
# remove the two PATH lines install/macos.sh added to ~/.zshrc if present
```

## Status

This slice is **Mac-verify pending**: the lane wrote and syntax-checked the
scripts but cannot run them on Apple Silicon. The numbered verification
recipe lives in the commit body for S23 (`git log` / issue #26).
