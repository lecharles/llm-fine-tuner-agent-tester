#!/bin/bash
# S23 (#26): "one file" installer — double-click this in Finder and Terminal
# runs the macOS local-runtime installer for LLM Tuner.
#
# If you already cloned the repo, it runs the copy next to it; otherwise it
# fetches the current installer from GitHub and runs that. Nothing is asked
# interactively; the runtime lands in ~/.llmtuner.
#
# First double-click may be blocked by Gatekeeper ("cannot be opened because
# the developer cannot be verified"). Right-click the file -> Open -> Open,
# or strip quarantine in Terminal:  xattr -d com.apple.quarantine <this file>

set -eo pipefail
cd "$(dirname "$0")" 2>/dev/null || true

echo "🎸 LLM Tuner — Mac installer"
echo

RAW_URL="https://raw.githubusercontent.com/lecharles/llm-fine-tuner-agent-tester/main/install/macos.sh"
if [ -f "install/macos.sh" ]; then
    exec bash "install/macos.sh"
fi
curl -fsSL "$RAW_URL" -o "/tmp/llmtuner-macos.sh" && exec bash "/tmp/llmtuner-macos.sh"
