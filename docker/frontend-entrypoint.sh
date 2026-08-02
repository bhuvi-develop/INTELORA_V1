#!/bin/sh
# =============================================================================
# INTELORA — runtime configuration injection
#
# Executed by the nginx image's entrypoint before the server starts. Writes the
# environment-specific API endpoints into /config.js, which index.html loads
# ahead of the application bundle. This is what allows one built image to run
# in any environment.
# =============================================================================
set -eu

TARGET="/usr/share/nginx/html/config.js"

API_BASE_URL="${INTELORA_API_BASE_URL:-http://localhost:8000}"
WS_URL="${INTELORA_WS_URL:-ws://localhost:8000/ws/live}"

cat > "$TARGET" <<EOF
window.__INTELORA_CONFIG__ = {
  apiBaseUrl: "${API_BASE_URL}",
  wsUrl: "${WS_URL}"
};
EOF

echo "[intelora] runtime config written to ${TARGET} (api=${API_BASE_URL})"
