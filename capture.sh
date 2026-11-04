#!/usr/bin/env bash
# capture.sh — Open CAPTURE_URL in a headless browser, verify rendered content,
# capture desktop and mobile views, then exit leaving the app running.
#
# Exit codes:
#   75  temporary navigation / browser infrastructure failure
#   1   script or rendering defect
#   0   success
set -euo pipefail

CAPTURE_URL="${CAPTURE_URL:?CAPTURE_URL environment variable is required}"
CAPTURE_DIR="${CAPTURE_DIR:?CAPTURE_DIR environment variable is required}"

BROWSER="${BROWSER:-chromium}"
VIRTUAL_TIME_BUDGET="${VIRTUAL_TIME_BUDGET:-12000}"
MIN_PNG_BYTES="${MIN_PNG_BYTES:-2000}"
RENDER_MARKER="${RENDER_MARKER:-GoldAI}"
TMP_DIR="${RUNNER_TEMP:-/tmp/opencode}"

mkdir -p "$CAPTURE_DIR" "$TMP_DIR"

echo "[capture] url=$CAPTURE_URL"
echo "[capture] dir=$CAPTURE_DIR"
echo "[capture] browser=$BROWSER"

DOM_FILE="$TMP_DIR/capture-dom.txt"
DOM_ERR="$TMP_DIR/capture-dom.err"

# ---- Render check: confirm the page loads and contains expected content ----
echo "[capture] render check (dump-dom)"
if ! /usr/bin/time -p "$BROWSER" --headless=new --disable-gpu --no-sandbox \
     --dump-dom --virtual-time-budget="$VIRTUAL_TIME_BUDGET" \
     "$CAPTURE_URL" >"$DOM_FILE" 2>"$DOM_ERR"; then
  rc=$?
  echo "[capture] browser/dump-dom failed (rc=$rc): temporary infrastructure failure" >&2
  cat "$DOM_ERR" >&2 || true
  exit 75
fi
if ! grep -q "$RENDER_MARKER" "$DOM_FILE"; then
  echo "[capture] rendered content missing marker '$RENDER_MARKER': rendering defect" >&2
  exit 1
fi
echo "[capture] render check passed"

capture_view() {
  local name="$1" width="$2" height="$3" ua="${4:-}"
  local out="$CAPTURE_DIR/final-$name.png"
  local err="$TMP_DIR/capture-$name.err"
  local args=(--headless=new --disable-gpu --no-sandbox \
              --window-size="${width},${height}" \
              --virtual-time-budget="$VIRTUAL_TIME_BUDGET" \
              --screenshot="$out")
  if [[ -n "$ua" ]]; then args+=(--user-agent="$ua"); fi
  echo "[capture] capturing $name (${width}x${height}) -> $out"
  if ! /usr/bin/time -p "$BROWSER" "${args[@]}" "$CAPTURE_URL" >/dev/null 2>"$err"; then
    rc=$?
    echo "[capture] $name screenshot failed (rc=$rc): temporary infrastructure failure" >&2
    cat "$err" >&2 || true
    exit 75
  fi
  if [[ ! -s "$out" ]] || [[ "$(stat -c %s "$out")" -lt "$MIN_PNG_BYTES" ]]; then
    echo "[capture] $name screenshot missing or too small: rendering defect" >&2
    exit 1
  fi
  echo "[capture] $name ok ($(stat -c %s "$out") bytes)"
}

capture_view desktop 1280 720
capture_view mobile 390 844 "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"

echo "[capture] done — app left running"
exit 0
