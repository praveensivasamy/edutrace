# EduTrace — Project Goal and Architecture Blueprint

## Goal

EduTrace is a lightweight student marks analytics platform for tracking exam performance, subject-wise trends, student progress, and future AI-assisted marksheet extraction.

The project is designed for:

- local development in PyCharm
- FastAPI-based backend learning
- SQLite-based local persistence
- CSV import/export for staging and data exchange
- future OCR / AI pipeline integration
- Podman containerisation
- later deployment to Azure Container Apps

---

## Recommended stack

| Layer | Technology |
|---|---|
| Backend | FastAPI |
| Database | SQLite |
| ORM | SQLAlchemy 2.x |
| Templates | Jinja2 |
| Dynamic UI | HTMX |
| Charts | Chart.js |
| Dependency management | uv |
| Packaging | Wheel + OCI container |
| Container engine | Podman |
| Registry | Docker Hub |
| Cloud target | Azure Container Apps |

---

## Why SQLite

SQLite is used as the application database instead of CSV.

CSV remains useful for:

- import
- export
- staging
- backup
- manual correction in Excel

SQLite is better for:

- querying trends
- avoiding duplicates
- updating records
- future review workflows
- AI pipeline metadata
- migration to PostgreSQL later if needed

---

## Main workflow

```text
Marksheet screenshot / CSV
        ↓
Upload / import layer
        ↓
Review and correction screen
        ↓
SQLite database
        ↓
FastAPI APIs
        ↓
Dashboard and trend views
```

---

## Future AI workflow

```text
Uploaded screenshot
        ↓
OCR extraction
        ↓
AI cleanup / table reconstruction
        ↓
Human review
        ↓
Approved records
        ↓
SQLite marks table
        ↓
Analytics dashboard
```

---

## Project name

Recommended name: **EduTrace**

Reason:

- professional sounding
- not limited only to marks
- suitable for analytics and AI pipeline extension
- good for GitHub, Docker Hub, and Azure deployment

---

## Packaging strategy

Use:

```text
uv + wheel + OCI container
```

### Development

Use `uv` for dependency and virtual environment management.

### Distribution

Use wheel packaging for Python application distribution.

### Deployment

Use an OCI container built with Podman and deployable to Docker Hub / Azure Container Apps.

### Why not shiv initially

Shiv is useful for standalone CLI tools, but EduTrace is a web application with:

- FastAPI server
- templates
- static files
- SQLite DB
- uploads
- container deployment

Therefore, wheel + container packaging is more appropriate.

---

## Cloud deployment direction

For low usage and learning purposes, deploy to:

```text
Azure Container Apps
```

Recommended Azure settings:

- consumption plan
- min replicas: 0 or 1
- max replicas: 1
- small CPU/memory
- avoid expensive logging retention
- use mounted storage only when persistence is required beyond redeploys

---

## Design principle

The project uses layered architecture:

```text
routes → services → repositories → database models
```

This keeps the application extensible and makes future migration to PostgreSQL or AI-based ingestion easier.
