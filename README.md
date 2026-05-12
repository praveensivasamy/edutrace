# EduTrace

EduTrace is a FastAPI + SQLite student marks analytics starter project.

It is designed for local PyCharm development first, with a clean path to Podman/Docker Hub/Azure Container Apps later.

## Features in this starter

- FastAPI application
- SQLite database
- SQLAlchemy 2.x models
- Repository/service layering
- Jinja2 dashboard
- HTMX-ready templates
- Chart.js dashboard chart
- CSV export endpoint
- Manual mark entry form
- Upload placeholder for future OCR/AI parsing
- Podman-compatible `Containerfile`
- `uv` dependency management
- `project-goal.md` architecture blueprint

## Requirements

- Python 3.14
- uv
- Podman optional

> If Python 3.14 is not yet installed locally, install it first and point PyCharm to that interpreter.

## Install uv

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Create environment

```bash
uv venv
```

## Install dependencies

```bash
uv sync
```

## Run locally

```bash
uv run uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Run smoke test

With the app running:

```bash
uv run python scripts/smoke_test.py
```

## Seed sample data

The app automatically creates tables on startup. You can seed sample data from the dashboard or run:

```bash
uv run python scripts/seed_sample_data.py
```

## Build with Podman

```bash
podman build -t edutrace:latest .
```

## Run with Podman

```bash
podman run --rm -p 8000:8000 -v ./data:/app/data -v ./uploads:/app/uploads edutrace:latest
```

## Push to Docker Hub

```bash
podman login docker.io
podman tag edutrace:latest YOUR_DOCKERHUB_USER/edutrace:latest
podman push YOUR_DOCKERHUB_USER/edutrace:latest
```

## Project layout

```text
app/
  api/
  core/
  db/
  schemas/
  services/
  templates/
  static/
  ai/
scripts/
data/
uploads/
```

## Notes

- SQLite is stored at `data/edutrace.db` by default.
- Uploaded files are stored in `uploads/`.
- For Azure deployment without mounted storage, data can be lost on container restart/redeploy.
- For learning, start local first, then move to Azure Container Apps.
