from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.repositories.mark_repository import MarkRepository
from app.db.session import get_db
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


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
        context={"exam_dates": AdminService(db).exam_date_options()},
    )


@router.get("/display-names/fragment", response_class=HTMLResponse)
def display_names_fragment(request: Request, db: Annotated[Session, Depends(get_db)]):
    return templates.TemplateResponse(
        request=request,
        name="_display_names_panel.html",
        context=_display_name_context(db),
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
            context={"exam_dates": AdminService(db).exam_date_options()},
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
            context=_display_name_context(db),
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
            context=_display_name_context(db),
        )
    return RedirectResponse(url="/admin", status_code=303)
