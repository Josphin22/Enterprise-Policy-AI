#!/bin/bash
set -e

echo "=== Enterprise Policy AI Backend Starting ==="

# Wait for PostgreSQL if DATABASE_URL is configured for postgres
if [[ "$DATABASE_URL" =~ ^postgres(ql)?:// ]]; then
    echo "Waiting for PostgreSQL database to be reachable..."
    # Extract host and port using Python
    python - << 'EOF'
import os, sys, time, urllib.parse
db_url = os.getenv("DATABASE_URL", "")
parsed = urllib.parse.urlparse(db_url)
host = parsed.hostname or "postgres"
port = parsed.port or 5432
import socket
start = time.time()
while time.time() - start < 45:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"PostgreSQL is reachable at {host}:{port}")
            sys.exit(0)
    except OSError:
        time.sleep(1)
print(f"Warning: PostgreSQL at {host}:{port} not immediately reachable, proceeding with app startup.")
EOF
fi

# Run safe database migrations if alembic is available, or ensure schema initialization
echo "Applying database schema initialization..."
python - << 'EOF'
import os, sys
try:
    from app.database.connection import init_db
    init_db()
    print("Database schema successfully initialized.")
except Exception as exc:
    print(f"Database schema init note: {exc}")
EOF

echo "Starting Uvicorn production server..."
# Production ASGI runner: 2 workers, no reload, binding to 0.0.0.0:8000
exec uvicorn app.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8000}" \
    --workers "${WORKERS:-2}" \
    --log-level "${LOG_LEVEL:-info}" \
    --no-access-log
