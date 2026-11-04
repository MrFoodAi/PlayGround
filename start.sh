#!/usr/bin/env bash
# start.sh — Build (when needed) and serve the static GoldAI XAU Bot dashboard.
# Runs in the foreground on PORT (default 3000) so start-project.sh can health-check it.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

: "${PORT:=3000}"
export PORT

SRC_DIR="$PROJECT_DIR/src"
BUILD_DIR="$PROJECT_DIR/dist"
OPENCODE_WEB_DIR="${OPENCODE_WEB_DIR:-}"

echo "[start] PROJECT_DIR=$PROJECT_DIR"
echo "[start] PORT=$PORT"
echo "[start] SRC_DIR=$SRC_DIR"
echo "[start] BUILD_DIR=$BUILD_DIR"

/usr/bin/time -p test -f package.json

# Install dependencies. The server uses only Node built-ins, so npm install is a
# reproducibility/no-op step; it is safe to skip when offline.
if [[ -f package.json && ! -d node_modules ]]; then
  /usr/bin/time -p npm install --no-audit --no-fund || true
fi

# Build: ensure the static output exists in dist/ (copy source -> built output).
/usr/bin/time -p mkdir -p "$BUILD_DIR"
if [[ ! -f "$BUILD_DIR/index.html" || "$SRC_DIR/index.html" -nt "$BUILD_DIR/index.html" ]]; then
  /usr/bin/time -p cp "$SRC_DIR/index.html" "$BUILD_DIR/index.html"
fi
echo "[start] build output ready: $BUILD_DIR"

# Write deployment-output.json for controller metadata / capture evidence.
if [[ -n "$OPENCODE_WEB_DIR" ]]; then
  /usr/bin/time -p mkdir -p "$OPENCODE_WEB_DIR"
  /usr/bin/time -p /usr/bin/printf '%s' "{\"project\":\"$PROJECT_DIR\",\"directory\":\"$BUILD_DIR\"}" > "$OPENCODE_WEB_DIR/deployment-output.json"
  echo "[start] wrote $OPENCODE_WEB_DIR/deployment-output.json"
fi

echo "[start] serving $BUILD_DIR on http://0.0.0.0:$PORT (foreground)"
exec /usr/bin/time -p node server.js
