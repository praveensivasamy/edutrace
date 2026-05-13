from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repositories.mark_repository import MarkRepository
from app.db.session import get_db
from app.services.analytics_service import AnalyticsService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
TARGET_STUDENT_LABEL = "Target Student"


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


@router.get("/dashboards/target", response_class=HTMLResponse)
def target_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    exam_term: Annotated[list[str] | None, Query()] = None,
    subject: Annotated[list[str] | None, Query()] = None,
    ordered_exam_term: Annotated[list[str] | None, Query()] = None,
):
    rows = MarkRepository(db).list_marks()
    settings = get_settings()
    rows, student_name, analytics_query = _resolve_target_rows(
        rows,
        target_display_name=settings.target_student_query,
        target_alias=settings.target_student_alias,
        privacy_enabled=settings.privacy_enabled,
    )
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
        filtered_rows, analytics_query, top_n=10, exam_order=ordered_exam_terms
    )
    rank_trends = AnalyticsService.student_rank_trend_by_subject(
        filtered_rows, analytics_query, exam_order=ordered_exam_terms
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
                    student_name
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


def _resolve_target_rows(
    rows: list[dict],
    target_display_name: str,
    target_alias: str,
    privacy_enabled: bool = True,
) -> tuple[list[dict], str, str]:
    display_label = target_display_name.strip() or TARGET_STUDENT_LABEL
    candidates = [value.strip() for value in (target_display_name, target_alias) if value.strip()]

    for candidate in candidates:
        candidate_rows, matched = _privacy_safe_target_rows(
            rows,
            candidate,
            privacy_enabled=privacy_enabled,
            display_label=display_label,
        )
        if matched:
            return candidate_rows, display_label, candidate

    return _display_rows(rows, privacy_enabled), display_label, display_label


def _privacy_safe_target_rows(
    rows: list[dict],
    student_query: str,
    privacy_enabled: bool = True,
    display_label: str | None = None,
) -> tuple[list[dict], bool]:
    normalized_query = student_query.strip().lower()
    fallback_label = display_label or student_query.strip() or TARGET_STUDENT_LABEL
    if not normalized_query:
        return _display_rows(rows, privacy_enabled), False

    matched_storage_name = ""
    matched_display_name = ""
    for row in rows:
        display_name = row["student_name"]
        storage_name = row.get("student_key") or display_name
        if normalized_query in display_name.lower() or normalized_query in storage_name.lower():
            matched_storage_name = storage_name
            matched_display_name = display_name
            break

    if not matched_storage_name:
        return _display_rows(rows, privacy_enabled), False

    target_label = matched_display_name or fallback_label
    if not privacy_enabled:
        return rows, True

    private_rows = []
    for row in rows:
        private_row = _storage_name_row(row)
        if private_row["student_name"] == matched_storage_name:
            private_row["student_name"] = target_label
        private_rows.append(private_row)
    return private_rows, True


def _storage_name_row(row: dict) -> dict:
    return {**row, "student_name": row.get("student_key") or row["student_name"]}


def _display_rows(rows: list[dict], privacy_enabled: bool) -> list[dict]:
    if not privacy_enabled:
        return rows
    return [_storage_name_row(row) for row in rows]


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
