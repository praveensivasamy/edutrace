from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.repositories.mark_repository import MarkRepository
from app.db.session import get_db
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/audit", tags=["audit"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def audit_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    exam_term: str = "",
    subject_name: str = "",
    student_name: str = "",
):
    repo = MarkRepository(db)
    filters = {
        "exam_term": exam_term,
        "subject_name": subject_name,
        "student_name": student_name,
    }
    has_filters = any(value.strip() for value in filters.values())
    marks = repo.list_marks(filters) if has_filters else []
    return templates.TemplateResponse(
        request=request,
        name="audit_dashboard.html",
        context={
            "marks": marks,
            "grouped_marks": AnalyticsService.group_by_test(marks),
            "available_filters": repo.available_filters(),
            "selected_filters": filters,
            "has_filters": has_filters,
        },
    )
