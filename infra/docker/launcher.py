import os, sys, time, subprocess

ROLE = os.getenv("APP_ROLE", "web")
# папки
os.makedirs("/app/staticfiles", exist_ok=True)
os.makedirs("/app/media", exist_ok=True)

# wait Postgres
PGHOST = os.getenv("POSTGRES_HOST", "db")
PGPORT = os.getenv("POSTGRES_PORT", "5432")
PGUSER = os.getenv("POSTGRES_USER", "app")
PGDB   = os.getenv("POSTGRES_DB", "app")

for i in range(120):
    r = subprocess.run(
        ["pg_isready","-h",PGHOST,"-p",PGPORT,"-U",PGUSER,"-d",PGDB],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if r.returncode == 0:
        break
    time.sleep(1)
else:
    print("Postgres not ready", file=sys.stderr); sys.exit(1)

# wait Redis
RH   = os.getenv("REDIS_HOST","redis")
RP   = os.getenv("REDIS_PORT","6379")
RPWD = os.getenv("REDIS_PASSWORD","")
for i in range(120):
    cmd = ["redis-cli","-h",RH,"-p",RP,"PING"]
    if RPWD: cmd = ["redis-cli","-h",RH,"-p",RP,"-a",RPWD,"PING"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if "PONG" in (r.stdout or ""):
        break
    time.sleep(1)
else:
    print("Redis not ready", file=sys.stderr); sys.exit(1)

def execv(argv): os.execvp(argv[0], argv)

if ROLE == "web":
    subprocess.check_call([sys.executable,"manage.py","migrate","--noinput"])
    subprocess.check_call([sys.executable,"manage.py","collectstatic","--noinput"])
    execv([
        "gunicorn","lightbikeshop.wsgi:application",
        "--bind","0.0.0.0:8000",
        "--workers", os.getenv("GUNICORN_WORKERS","2"),
        "--threads", os.getenv("GUNICORN_THREADS","2"),
        "--timeout","60",
        "--access-logfile","-",
        "--error-logfile","-",
        "--log-level","info",
    ])
elif ROLE == "worker":
    execv(["celery","-A","lightbikeshop","worker","-l","INFO"])
elif ROLE == "beat":
    execv(["celery","-A","lightbikeshop","beat","-l","INFO"])
else:
    print(f"Unknown APP_ROLE: {ROLE}", file=sys.stderr); sys.exit(1)
