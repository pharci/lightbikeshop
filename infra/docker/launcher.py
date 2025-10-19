import os, sys, time, socket, subprocess

ROLE = os.getenv("APP_ROLE", "web")

# каталоги
os.makedirs("/app/staticfiles", exist_ok=True)
os.makedirs("/app/media", exist_ok=True)

def wait_for_tcp(host: str, port: int, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), 2):
                return
        except OSError:
            time.sleep(1)
    print(f"Timeout waiting for {host}:{port}", file=sys.stderr)
    sys.exit(1)

def wait_for_redis(host: str, port: int, password: str | None, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), 2) as s:
                s.settimeout(2)
                if password:
                    s.sendall(f"AUTH {password}\r\n".encode())
                    if not s.recv(128).startswith(b"+OK"):
                        raise OSError("AUTH failed")
                s.sendall(b"PING\r\n")  # inline protocol
                if s.recv(128).startswith(b"+PONG"):
                    return
        except OSError:
            time.sleep(1)
    print("Timeout waiting for Redis PING", file=sys.stderr)
    sys.exit(1)

# env
PGHOST = os.getenv("POSTGRES_HOST", "db")
PGPORT = int(os.getenv("POSTGRES_PORT", "5432"))

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

DB_TIMEOUT = int(os.getenv("WAIT_DB_TIMEOUT", "120"))
REDIS_TIMEOUT = int(os.getenv("WAIT_REDIS_TIMEOUT", "120"))

# wait Postgres (TCP)
wait_for_tcp(PGHOST, PGPORT, DB_TIMEOUT)

# wait Redis (AUTH+PING)
wait_for_redis(REDIS_HOST, REDIS_PORT, REDIS_PASSWORD or None, REDIS_TIMEOUT)

def execv(argv: list[str]) -> None:
    os.execvp(argv[0], argv)

if ROLE == "web":
    subprocess.check_call([sys.executable, "manage.py", "migrate", "--noinput"])
    subprocess.check_call([sys.executable, "manage.py", "collectstatic", "--noinput", "--clear"])
    execv([
        "gunicorn", "lightbikeshop.wsgi:application",
        "--bind", "0.0.0.0:8000",
        "--workers", os.getenv("GUNICORN_WORKERS", "2"),
        "--threads", os.getenv("GUNICORN_THREADS", "2"),
        "--timeout", os.getenv("GUNICORN_TIMEOUT", "60"),
        "--access-logfile", "-",
        "--error-logfile", "-",
        "--log-level", os.getenv("GUNICORN_LOG_LEVEL", "info"),
    ])
elif ROLE == "worker":
    execv(["celery", "-A", "lightbikeshop", "worker", "-l", "INFO"])
elif ROLE == "beat":
    execv(["celery", "-A", "lightbikeshop", "beat", "-l", "INFO"])
else:
    print(f"Unknown APP_ROLE: {ROLE}", file=sys.stderr); sys.exit(1)
