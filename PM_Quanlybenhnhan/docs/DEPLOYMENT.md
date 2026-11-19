# Production Deployment Guide

## Overview

Production runs as a Docker Compose stack:

| Service | Image / Build | Role |
|---------|--------------|------|
| `db` | `pgvector/pgvector:pg16` | PostgreSQL 16 + pgvector |
| `redis` | `redis:7-alpine` | Celery broker + cache |
| `web` | `Dockerfile.prod` | Django + Gunicorn (API + admin) |
| `worker` | `Dockerfile.prod` | Celery worker |
| `frontend` | `frontend/Dockerfile` | Vue SPA (multi-stage node build → nginx:alpine) |
| `nginx` | `nginx:1.27-alpine` | Reverse proxy, SSL termination |

Request routing (via Nginx):
- `/khamsk/` → proxied to `frontend` container (nginx:alpine serving built SPA)
- `/api/`, `/admin/` → proxied to Gunicorn (`web`)
- `/static/` → Django collectstatic output (shared volume)
- `/media/` → uploaded files (bind mount)

---

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| VPS | 2 vCPU, 4GB RAM, 50GB SSD, Ubuntu 22.04+ |
| Docker + Compose | v24+ |
| Domain | pointed at server IP (A record) |

---

## First-time Setup

### 1. Clone and configure

```bash
git clone <repo-url> /opt/khamsk
cd /opt/khamsk
cp .env.prod.example .env.prod
nano .env.prod   # fill in real values
```

Generate a strong secret key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Set at minimum in `.env.prod`:
- `DJANGO_SECRET_KEY` (64 hex chars)
- `POSTGRES_PASSWORD` and matching `DATABASE_URL`
- `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` (your domain)

> **Note:** docker-compose `env_file` does not expand `${VARS}`. Write `DATABASE_URL` in full.

### 2. Obtain SSL certificate (Let's Encrypt)

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d ycaohoahong.com -d www.ycaohoahong.com
```

Certs land in `/etc/letsencrypt/live/ycaohoahong.com/` (mounted read-only into Nginx).

Update `nginx/prod.conf` `server_name` and `ssl_certificate` paths if your domain differs.

### 3. Deploy

```bash
chmod +x docker/deploy.sh
./docker/deploy.sh
```

The script builds all images (backend + frontend), starts the stack, and runs migrations + collectstatic.

### 4. Create superuser

```bash
docker compose -f docker-compose.prod.yml exec web python src/manage.py createsuperuser
```

### 5. Seed embeddings (after diagnosis data exists)

```bash
docker compose -f docker-compose.prod.yml exec web python src/manage.py reembed --all
```

---

## Routine Deploys

```bash
cd /opt/khamsk
./docker/deploy.sh
```

The script pulls `main`, rebuilds images, restarts, and migrates.

---

## SSL Renewal

Let's Encrypt certs expire every 90 days. Add a cron job:

```bash
0 3 * * * certbot renew --quiet && docker compose -f /opt/khamsk/docker-compose.prod.yml restart nginx
```

---

## Common Operations

```bash
C="docker compose -f docker-compose.prod.yml"

$C ps                      # Stack status
$C logs -f web             # Tail web logs
$C logs -f worker          # Tail Celery logs
$C exec web python src/manage.py <cmd>   # Run a management command
$C restart web             # Restart a service
$C down                    # Stop the stack (keeps volumes)
$C down -v                 # Stop + delete volumes (DESTRUCTIVE — wipes DB)
```

### Database backup

```bash
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U quanlybenhnhan quanlybenhnhan > backup_$(date +%F).sql
```

### Database restore

```bash
cat backup.sql | docker compose -f docker-compose.prod.yml exec -T db \
  psql -U quanlybenhnhan quanlybenhnhan
```

---

## CI/CD (GitHub Actions)

`.github/workflows/deploy.yml` SSHes into the server and runs the deploy script on push to `main`. Required repo secrets: `SERVER_HOST`, `SERVER_USER`, `SSH_KEY`.

```yaml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /opt/khamsk
            ./docker/deploy.sh
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 502 Bad Gateway | `web` container up? `$C logs web` for Gunicorn errors |
| SPA loads blank | `frontend` container up? `$C logs frontend` for build errors |
| CSS/JS 404 | `collectstatic` ran? `static_files` volume populated? |
| CSRF errors on admin | `CSRF_TRUSTED_ORIGINS` includes `https://` domain |
| DB connection refused | `DATABASE_URL` matches POSTGRES_* creds; `db` healthy |
| SSL warnings | Cert paths in `nginx/prod.conf` match certbot output |