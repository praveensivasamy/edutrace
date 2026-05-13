from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.repositories.mark_repository import MarkRepository
from app.db.session import get_db
from app.services.analytics_service import AnalyticsService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    academic_year: str = "",
    class_name: str = "",
    section: str = "",
    exam_term: str = "",
):
    repo = MarkRepository(db)
    filters = {
        "academic_year": academic_year,
        "class_name": class_name,
        "section": section,
        "exam_term": exam_term,
    }
    rows = repo.list_marks(filters)
    summary = AnalyticsService.summary(rows)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "summary": summary,
            "rows": rows,
            "trend": AnalyticsService.subject_trend(rows),
            "student_rankings": AnalyticsService.student_rankings(rows),
            "subject_summary": AnalyticsService.subject_summary(rows),
            "subject_toppers": AnalyticsService.grouped_subject_toppers_by_test(rows),
            "section_summary": AnalyticsService.section_summary(rows),
            "available_filters": repo.available_filters(),
            "selected_filters": filters,
        },
    )


@router.get("/dashboards/svanik", response_class=HTMLResponse)
def svanik_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    exam_term: Annotated[list[str] | None, Query()] = None,
    subject: Annotated[list[str] | None, Query()] = None,
    ordered_exam_term: Annotated[list[str] | None, Query()] = None,
):
    rows = MarkRepository(db).list_marks()
    student_name = "Svanik"
    options = AnalyticsService.analysis_options(rows)
    selected_exam_terms = exam_term or []
    selected_subjects = subject or []
    ordered_exam_terms = _ordered_tests(
        options["exam_terms"],
        selected_exam_terms,
        ordered_exam_term or [],
    )
    filtered_rows = AnalyticsService.filter_rows(rows, selected_exam_terms, selected_subjects)
    comparisons = AnalyticsService.student_vs_top_by_subject(
        filtered_rows, student_name, top_n=10, exam_order=ordered_exam_terms
    )
    rank_trends = AnalyticsService.student_rank_trend_by_subject(
        filtered_rows, student_name, exam_order=ordered_exam_terms
    )
    return templates.TemplateResponse(
        request=request,
        name="student_comparison_dashboard.html",
        context={
            "student_name": student_name,
            "comparisons": comparisons,
            "grouped_comparisons": AnalyticsService.group_by_test(comparisons),
            "rank_trends": rank_trends,
            "options": options,
            "selected_exam_terms": selected_exam_terms,
            "selected_subjects": selected_subjects,
            "ordered_exam_terms": ordered_exam_terms,
            "matched_name": next(
                (
                    comparison["target"]["student_name"]
                    for comparison in comparisons
                    if comparison["target"]
                ),
                None,
            ),
        },
    )


@router.get("/dashboards/student-compare", response_class=HTMLResponse)
def student_compare_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[list[str] | None, Query()] = None,
    exam_term: Annotated[list[str] | None, Query()] = None,
    subject: Annotated[list[str] | None, Query()] = None,
):
    rows = MarkRepository(db).list_marks()
    selected_students = student or []
    selected_exam_terms = exam_term or []
    selected_subjects = subject or []
    options = AnalyticsService.analysis_options(rows)
    comparisons = AnalyticsService.student_comparison(
        rows,
        student_names=selected_students,
        exam_terms=selected_exam_terms,
        subjects=selected_subjects,
    )
    grouped_comparisons = AnalyticsService.grouped_student_comparison(comparisons)
    return templates.TemplateResponse(
        request=request,
        name="student_compare_dashboard.html",
        context={
            "student_options": AnalyticsService.student_options(rows),
            "options": options,
            "selected_students": selected_students,
            "selected_exam_terms": selected_exam_terms,
            "selected_subjects": selected_subjects,
            "comparisons": comparisons,
            "grouped_comparisons": grouped_comparisons,
            "has_selection": len(selected_students) >= 2,
        },
    )


def _ordered_tests(
    available_exam_terms: list[str],
    selected_exam_terms: list[str],
    submitted_order: list[str],
) -> list[str]:
    included = selected_exam_terms or available_exam_terms
    submitted = [term for term in submitted_order if term in included]
    remainder = [term for term in included if term not in submitted]
    return submitted + remainder


@router.get("/dashboards/approved-marks", response_class=HTMLResponse)
def approved_marks_dashboard(request: Request, db: Annotated[Session, Depends(get_db)]):
    repo = MarkRepository(db)
    rows = repo.list_marks()
    return templates.TemplateResponse(
        request=request,
        name="approved_marks_dashboard.html",
        context={
            "rows": rows,
            "grouped_rows": AnalyticsService.group_by_test(rows),
            "summary": AnalyticsService.summary(rows),
        },
    )
