from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db.repositories.mark_repository import MarkRepository
from app.db.session import get_db
from app.schemas.marks import MarkCreate
from app.services.csv_service import CsvService

router = APIRouter(prefix="/marks", tags=["marks"])


@router.get("/api")
def list_marks(db: Session = Depends(get_db)):
    return MarkRepository(db).list_marks()


@router.get("/export.csv")
def export_marks_csv(db: Session = Depends(get_db)):
    rows = MarkRepository(db).list_marks()
    csv_text = CsvService.rows_to_csv(rows)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=edutrace_marks.csv"},
    )


@router.post("/add")
def add_mark(
    academic_year: str = Form("2026-2027"),
    class_name: str = Form("IX"),
    section: str = Form("B"),
    exam_term: str = Form(...),
    exam_date: str = Form(""),
    subject_name: str = Form(...),
    student_name: str = Form(...),
    score: float | None = Form(None),
    max_marks: float = Form(...),
    absent_flag: str = Form("N"),
    remarks: str = Form(""),
    db: Session = Depends(get_db),
):
    data = MarkCreate(
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
    MarkRepository(db).upsert_mark(data)
    return RedirectResponse(url="/", status_code=303)
