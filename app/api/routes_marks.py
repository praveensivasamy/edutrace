from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_admin
from app.db.repositories.mark_repository import MarkRepository
from app.db.session import get_db
from app.schemas.marks import MarkCreate
from app.services.csv_service import CsvService

router = APIRouter(prefix="/marks", tags=["marks"], dependencies=[Depends(get_current_user)])


@router.get("/api")
def list_marks(db: Annotated[Session, Depends(get_db)]):
    return MarkRepository(db).list_marks()


@router.get("/export.csv")
def export_marks_csv(db: Annotated[Session, Depends(get_db)]):
    rows = MarkRepository(db).list_marks()
    csv_text = CsvService.rows_to_csv(rows)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=edutrace_marks.csv"},
    )


@router.post("/add")
def add_mark(
    _: Annotated[object, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    academic_year: Annotated[str, Form()] = "2026-2027",
    class_name: Annotated[str, Form()] = "IX",
    section: Annotated[str, Form()] = "B",
    exam_term: Annotated[str, Form()] = "",
    exam_date: Annotated[str, Form()] = "",
    subject_name: Annotated[str, Form()] = "",
    student_name: Annotated[str, Form()] = "",
    score: Annotated[float | None, Form()] = None,
    max_marks: Annotated[float, Form()] = 100,
    absent_flag: Annotated[str, Form()] = "N",
    remarks: Annotated[str, Form()] = "",
):
    MarkRepository(db).upsert_mark(
        _mark_create(
            academic_year=academic_year,
            class_name=class_name,
            section=section,
            exam_term=exam_term,
            exam_date=exam_date,
            subject_name=subject_name,
            student_name=student_name,
            score=score,
            max_marks=max_marks,
            absent_flag=absent_flag,
            remarks=remarks,
        )
    )
    return RedirectResponse(url="/", status_code=303)


@router.post("/{mark_id}/edit")
def edit_mark(
    mark_id: int,
    _: Annotated[object, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    score: Annotated[float | None, Form()] = None,
    max_marks: Annotated[float, Form()] = 100,
    absent_flag: Annotated[str, Form()] = "N",
    remarks: Annotated[str, Form()] = "",
):
    mark = MarkRepository(db).update_mark_numbers(
        mark_id=mark_id,
        score=score,
        max_marks=max_marks,
        absent_flag=absent_flag,
        remarks=remarks or None,
    )
    if not mark:
        raise HTTPException(status_code=404, detail="Mark not found")
    return RedirectResponse(url="/dashboards/approved-marks", status_code=303)


def _mark_create(
    *,
    academic_year: str,
    class_name: str,
    section: str,
    exam_term: str,
    exam_date: str,
    subject_name: str,
    student_name: str,
    score: float | None,
    max_marks: float,
    absent_flag: str,
    remarks: str,
) -> MarkCreate:
    return MarkCreate(
        academic_year=academic_year,
        class_name=class_name,
        section=section,
        exam_term=exam_term,
        exam_date=exam_date or None,
        subject_name=subject_name,
        student_name=student_name,
        score=score,
        max_marks=max_marks,
        absent_flag=absent_flag,
        remarks=remarks or None,
    )
