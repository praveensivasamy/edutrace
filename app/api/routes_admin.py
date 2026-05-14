from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.db.bootstrap import init_db
from app.db.repositories.mark_repository import MarkRepository
from app.db.session import engine, get_db
from app.services.admin_service import AdminService
from app.services.privacy_service import PrivacyService, clear_reveal_key

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="app/templates")


def _require_privacy_enabled() -> None:
    if not PrivacyService.privacy_enabled():
        raise HTTPException(status_code=404, detail="Privacy features are disabled.")


@router.get("", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Annotated[Session, Depends(get_db)]):
    service = AdminService(db)
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "stats": service.stats(),
            "exam_dates": service.exam_date_options(),
            "exam_display_names": MarkRepository(db).list_exam_display_names(),
            "subject_display_names": MarkRepository(db).list_subject_display_names(),
            "is_admin": True,
        },
    )


def _display_name_context(db: Session) -> dict:
    repo = MarkRepository(db)
    return {
        "exam_display_names": repo.list_exam_display_names(),
        "subject_display_names": repo.list_subject_display_names(),
    }


@router.get("/exam-dates/fragment", response_class=HTMLResponse)
def exam_dates_fragment(request: Request, db: Annotated[Session, Depends(get_db)]):
    return templates.TemplateResponse(
        request=request,
        name="_exam_dates_panel.html",
        context={"exam_dates": AdminService(db).exam_date_options(), "is_admin": True},
    )


@router.get("/display-names/fragment", response_class=HTMLResponse)
def display_names_fragment(request: Request, db: Annotated[Session, Depends(get_db)]):
    return templates.TemplateResponse(
        request=request,
        name="_display_names_panel.html",
        context={**_display_name_context(db), "is_admin": True},
    )


@router.get("/privacy/fragment", response_class=HTMLResponse)
def privacy_fragment(request: Request, db: Annotated[Session, Depends(get_db)]):
    return templates.TemplateResponse(
        request=request,
        name="_privacy_panel.html",
        context={"privacy": PrivacyService(db).status(), "is_admin": True},
    )


@router.get("/privacy", response_class=HTMLResponse)
def privacy_dashboard(request: Request, db: Annotated[Session, Depends(get_db)]):
    return templates.TemplateResponse(
        request=request,
        name="privacy_dashboard.html",
        context={"privacy": PrivacyService(db).status(), "is_admin": True},
    )


@router.post("/purge")
def purge_data(
    confirm: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    if confirm.strip().upper() != "PURGE":
        raise HTTPException(status_code=400, detail='Type "PURGE" to confirm.')
    AdminService(db).purge_all()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/vacuum")
def vacuum_database(db: Annotated[Session, Depends(get_db)]):
    AdminService(db).vacuum()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/exam-dates")
def update_exam_date(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    academic_year: Annotated[str, Form()],
    exam_term: Annotated[str, Form()],
    exam_date: Annotated[str, Form()] = "",
):
    updated = AdminService(db).approve_exam_date(
        academic_year=academic_year,
        exam_term=exam_term,
        exam_date=exam_date or None,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Exam not found")
    if request.headers.get("hx-request"):
        return templates.TemplateResponse(
            request=request,
            name="_exam_dates_panel.html",
            context={"exam_dates": AdminService(db).exam_date_options(), "is_admin": True},
        )
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/display-names/exams")
def update_exam_display_name(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    exam_id: Annotated[int, Form()],
    display_name: Annotated[str, Form()] = "",
):
    if not MarkRepository(db).update_exam_display_name(exam_id, display_name):
        raise HTTPException(status_code=404, detail="Exam not found")
    if request.headers.get("hx-request"):
        return templates.TemplateResponse(
            request=request,
            name="_display_names_panel.html",
            context={**_display_name_context(db), "is_admin": True},
        )
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/display-names/subjects")
def update_subject_display_name(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    subject_id: Annotated[int, Form()],
    display_name: Annotated[str, Form()] = "",
):
    if not MarkRepository(db).update_subject_display_name(subject_id, display_name):
        raise HTTPException(status_code=404, detail="Subject not found")
    if request.headers.get("hx-request"):
        return templates.TemplateResponse(
            request=request,
            name="_display_names_panel.html",
            context={**_display_name_context(db), "is_admin": True},
        )
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/privacy/anonymize")
def anonymize_student_names(
    db: Annotated[Session, Depends(get_db)],
    passphrase: Annotated[str, Form()],
):
    _require_privacy_enabled()
    try:
        key_bytes = PrivacyService(db).anonymize_students(passphrase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=key_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="student-name-key.student-key.json"'
        },
    )


@router.post("/privacy/load-key")
async def load_student_reveal_key(
    request: Request,
    key_file: Annotated[UploadFile, File()],
    passphrase: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    _require_privacy_enabled()
    try:
        PrivacyService.load_reveal_key(await key_file.read(), passphrase)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if request.headers.get("hx-request"):
        return templates.TemplateResponse(
            request=request,
            name="_privacy_panel.html",
            context={"privacy": PrivacyService(db).status(), "is_admin": True},
        )
    return RedirectResponse(url="/admin/privacy", status_code=303)


@router.post("/privacy/clear-key")
def clear_student_reveal_key(request: Request, db: Annotated[Session, Depends(get_db)]):
    _require_privacy_enabled()
    clear_reveal_key()
    if request.headers.get("hx-request"):
        return templates.TemplateResponse(
            request=request,
            name="_privacy_panel.html",
            context={"privacy": PrivacyService(db).status(), "is_admin": True},
        )
    return RedirectResponse(url="/admin/privacy", status_code=303)


@router.post("/privacy/rotate-key")
def rotate_student_key(new_passphrase: Annotated[str, Form()]):
    _require_privacy_enabled()
    try:
        key_bytes = PrivacyService.rotate_key(new_passphrase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=key_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                'attachment; filename="student-name-key-rotated.student-key.json"'
            )
        },
    )


@router.get("/privacy/download-current-db")
def download_current_database():
    path = PrivacyService.current_database_path()
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="SQLite database file not found")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=f"edutrace-current-{timestamp}.db",
    )


@router.post("/privacy/restore-db")
async def restore_database_backup(db_file: Annotated[UploadFile, File()]):
    content = await db_file.read()
    try:
        engine.dispose()
        PrivacyService.restore_database(content, db_file.filename)
        engine.dispose()
        init_db(engine)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/admin/privacy", status_code=303)
