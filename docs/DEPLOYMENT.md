# Deployment Guide

## Local demonstration

Use Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python ml/train_model.py
python ml/compare_models.py
python app.py
```

Windows uses `.venv\\Scripts\\Activate.ps1` instead of `source .venv/bin/activate`.

## Configuration

Copy `.env.example` to `.env` and set a strong secret key for any shared environment.

```text
SECRET_KEY=replace-with-a-long-random-secret
APP_ENV=production
SESSION_COOKIE_SECURE=1
```

## Production architecture

For a real deployment, place a production WSGI server behind HTTPS and a reverse proxy, move from SQLite to PostgreSQL, store media in object storage, enable CSRF/rate limiting, and configure backups and centralized logs.

## Health check

`GET /api/health` reports application version, database readiness and ML model readiness.
