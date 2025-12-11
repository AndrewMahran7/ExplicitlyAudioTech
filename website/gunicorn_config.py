# Gunicorn configuration for Explicitly web application
# Optimized for AWS t3.medium (4GB RAM, 2 vCPUs)

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
# Use 1 worker to avoid multiple model instances eating RAM
# Use threads for concurrency instead
workers = 1
worker_class = "gthread"
threads = 2  # Allow 2 concurrent requests per worker
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeouts (audio processing takes a long time)
timeout = 600  # 10 minutes for long audio files
graceful_timeout = 30
keepalive = 5

# Process naming
proc_name = "explicitly"

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Pre-load application to load models once at startup
preload_app = True

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print("🚀 Starting Explicitly web server...")
    print(f"   Workers: {workers}")
    print(f"   Threads per worker: {threads}")
    print(f"   Timeout: {timeout}s")
    print(f"   Preload app: {preload_app}")

def when_ready(server):
    """Called just after the server is started."""
    print("✅ Explicitly server is ready to accept connections")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    print("🔄 Reloading workers...")
