#!/bin/sh
cd "$(dirname "$0")" || exit 1
exec python3 app.py --host 127.0.0.1 --port 8080
