# Migrations

This starter uses `Base.metadata.create_all()` for a simple first run.

When you are ready for schema migrations, initialise Alembic properly and generate revisions.

Suggested later commands:

```bash
uv run alembic init migrations
uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
```
