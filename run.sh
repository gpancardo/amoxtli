#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ "$1" = "--lite" ]; then
  port="${2:-8765}"
  echo "Amoxtli · modo estático → http://localhost:$port"
  exec python3 -m http.server -d web "$port"
fi

echo "Amoxtli · completo (búsqueda + chat + grafo) → http://localhost:8765"
python3 server.py
