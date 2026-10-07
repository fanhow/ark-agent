#!/bin/zsh
set -eu
ARK_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ARK_ROOT"
exec python3 server.py --port "${ARK_PORT:-8765}"
