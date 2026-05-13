# EduTrace

EduTrace is a FastAPI + SQLite student marks analytics starter project.

It is designed for local PyCharm development first, with a clean path to Podman/Docker Hub/Azure Container Apps later.

## Metrics

![Python](https://img.shields.io/badge/python-3.14-blue)

![Azure](https://img.shields.io/badge/Azure-Container%20Apps-blue)

![Docker](https://img.shields.io/docker/image-size/praveensiva/edutrace/latest)

[![Build Push and Deploy EduTrace](https://github.com/praveensivasamy/edutrace/actions/workflows/dockerhub-build.yml/badge.svg)](https://github.com/praveensivasamy/edutrace/actions/workflows/dockerhub-build.yml)
## Technical Features in this starter

- FastAPI application
- SQLite database
- SQLAlchemy 2.x models
- Repository/service layering
- Jinja2 dashboard
- HTMX-ready templates
- Chart.js dashboard chart
- CSV export endpoint
- Manual mark entry form
- Upload review flow for Excel/CSV/text marks files
- Paste CSV content directly and preview it before approval
- Screenshot upload staging before OCR/AI parsing is configured
- Human approval before extracted marks are committed to SQLite
- Consolidated dashboard for overall marks and toppers
- Analytics dashboard for subject-wise and test-wise comparison
- Student comparison dashboard for arbitrary student comparison
- Approved Marks dashboard with edit support
- Audit dashboard for approved mark inspection
- Separate Privacy tab for anonymize, reveal, download, and restore flows
- `uv` dependency management

## Requirements

- Python 3.14
- uv

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

## Upload and review flow

Uploaded Excel/CSV/text files are parsed into candidate marks and saved in a parse job. Open the returned review link, correct the rows if needed, and approve them before they are written to the marks table.

You can also paste CSV content directly on the dashboard and preview it as an editable table before approval.

Consolidated marksheets with one student per row and subject scores as columns are expanded into individual mark records for dashboard analytics.

Screenshot/image uploads are stored and tracked, but automatic visual number extraction is intentionally left behind a small parser boundary until an OCR/AI provider is configured.

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


- Use `EDUTRACE_LOG_LEVEL` to control container log verbosity. Default is `INFO`.
- Set `EDUTRACE_PRIVACY_ENABLED=false` to disable privacy masking for all users. This hides anonymize/key/reveal/rotate controls and leaves only SQLite DB download and restore in the Privacy tab. If the DB already stores aliases, restore a real-name DB first.
- Set `EDUTRACE_PRIVACY_ENABLED=true` to enable privacy mode for anonymizing names and loading or rotating reveal keys.
- Admin Privacy can anonymize `students.student_name` before committing the DB. It downloads the encrypted key file. When loaded with its passphrase, real names are shown on screen only and are not written back to SQLite.
- If names are anonymized, load the private key before approving future uploads. Incoming real names are mapped back to their aliases before marks are saved, preventing real names from being reintroduced into the DB.
- To change the key or passphrase, load the current key and use the Privacy panel's rotate action to download a newly encrypted key.
- For Azure free-tier/no-persistence deployments, use Admin Privacy to download the current SQLite DB before redeploying or restarting the container.
- To recover after data loss, upload a downloaded SQLite DB in Admin Privacy. Restore replaces the running DB exactly as uploaded and does not store a backup inside the container. Run anonymization after recovery if the restored DB contains real names and you plan to commit it.
- Keep `private/` and `*.student-key.json` files out of Git.

## Deferred refactors

- Add pagination to large mark tables, especially Approved Marks.
- Split analytics helpers if dashboard logic grows further.
- Add a small Chart.js helper file for shared chart defaults.
- Add more HTMX partial refreshes for dashboard filters where useful.
- Review Azure persistent volume setup before production use.