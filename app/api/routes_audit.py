from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.db.repositories.mark_repository import MarkRepository
from app.db.session import get_db
from app.services.csv_service import CsvService

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(get_current_user)])
templates = Jinja2Templates(directory="app/templates")


@router.get("/export-excel")
def audit_export_excel(
    db: Annotated[Session, Depends(get_db)],
    exam_term: str = "",
    subject_name: str = "",
    student_name: str = "",
):
    filters = {
        "exam_term": exam_term,
        "subject_name": subject_name,
        "student_name": student_name,
    }
    rows = MarkRepository(db).list_marks(filters)
    if not rows:
        return Response(
            content="",
            media_type="application/vnd.ms-excel",
            headers={"Content-Disposition": "attachment; filename=edutrace_audit.xls"},
        )
    tabular = CsvService.rows_to_tsv(rows)
    return Response(
        content=tabular,
        media_type="application/vnd.ms-excel",
        headers={"Content-Disposition": "attachment; filename=edutrace_audit.xls"},
    )


@router.get("", response_class=HTMLResponse)
def audit_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    exam_term: str = "",
    subject_name: str = "",
    student_name: str = "",
    page: int = 1,
    page_size: int = 50,
):
    repo = MarkRepository(db)
    filters = {
        "exam_term": exam_term,
        "subject_name": subject_name,
        "student_name": student_name,
    }
    marks_page = repo.list_marks_page(filters=filters, page=page, page_size=page_size)
    marks = marks_page.items
    has_filters = any(value.strip() for value in filters.values())
    return templates.TemplateResponse(
        request=request,
        name="_audit_results.html" if request.headers.get("hx-request") else "audit_dashboard.html",
        context={
            "marks": marks,
            "marks_page": marks_page,
            "available_filters": repo.available_filters(),
            "selected_filters": filters,
            "has_filters": has_filters,
            "is_admin": user.is_admin,
        },
    )
