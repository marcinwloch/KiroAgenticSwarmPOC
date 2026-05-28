#!/bin/bash

# Bootstrap script for Nortal Kiro Swarm demo (macOS/Linux)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Marcin Włoch Kiro Swarm Demo Bootstrap ==="

# Step 1: Check uv
echo ""
echo "[1/3] Checking uv..."
if ! command -v uv &> /dev/null; then
    echo "  uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo "  uv installed."
else
    echo "  uv $(uv --version)"
fi

# Step 2: Sync mcp-server
echo ""
echo "[2/3] Running 'uv sync' in mcp-server/..."
cd "$REPO_ROOT/mcp-server"
uv sync --python 3.12 --frozen --no-dev
echo "  uv sync OK"

# Step 3: Smoke test (load non-secret endpoints — same vars as .kiro/settings/mcp.json)
echo ""
echo "[3/3] Running smoke test..."
if [ -f "$REPO_ROOT/aws-endpoints.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$REPO_ROOT/aws-endpoints.env"
    set +a
    echo "  Loaded aws-endpoints.env"
else
    echo "  WARNING: aws-endpoints.env not found — smoke test may fail"
fi
uv run python -m swarm_mcp.server --self-test
echo "  Smoke test OK"

echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "Next steps:"
echo "  1. Set AWS credentials: aws configure --profile nortal-swarm"
echo "  2. Open this folder in Kiro IDE"
echo "  3. Reload MCP servers (if needed) and see 'nortal-swarm' with 8 tools"
echo "  4. Check README.md for demo instructions"
