from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.routes_admin import router as admin_router
from app.api.routes_audit import router as audit_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_marks import router as marks_router
from app.api.routes_uploads import router as uploads_router
from app.core.logging import configure_logging
from app.db.bootstrap import init_db
from app.db.session import engine

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db(engine)
    yield


app = FastAPI(title="EduTrace", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def prevent_auth_state_caching(request, call_next) -> Response:
    response = await call_next(request)
    if not request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.include_router(dashboard_router)
app.include_router(marks_router)
app.include_router(uploads_router)
app.include_router(admin_router)
app.include_router(audit_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "edutrace"}


@app.get("/.auth/logout", include_in_schema=False)
def local_auth_logout() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=303)


def run() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
