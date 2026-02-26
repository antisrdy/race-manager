"""Gunicorn production configuration."""

# Network
bind = "0.0.0.0:8000"

# Workers — keep at 2 for SQLite to minimise write contention.
# Increase only if you migrate to a server-based database (Postgres, MySQL).
workers = 2
worker_class = "sync"

# Timeouts
timeout = 120
keepalive = 5

# Logging to stdout/stderr (captured by Docker / systemd)
accesslog = "-"
errorlog = "-"
loglevel = "info"

proc_name = "race-manager"
