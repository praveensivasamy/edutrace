from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.constants import DEFAULT_ACADEMIC_YEAR, DEFAULT_CLASS_NAME, DEFAULT_SECTION
from app.db.repositories.upload_repository import UploadRepository
from app.db.session import get_db
from app.services.parse_service import ParseService
from app.services.review_service import ReviewService
from app.services.upload_service import UploadService

router = APIRouter(prefix="/uploads", tags=["uploads"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="app/templates")


@router.post("/api")
async def upload_file(
    request: Request,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
):
    result = await UploadService(db).save_upload(file)
    if request.headers.get("hx-request"):
        return HTMLResponse(_upload_result_html(result))
    return result


@router.post("/paste")
def paste_csv(
    csv_text: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    if not csv_text.strip():
        raise HTTPException(status_code=400, detail="CSV content is required")

    result = UploadService(db).save_pasted_csv(csv_text)
    return RedirectResponse(url=result["review_url"], status_code=303)


@router.get("/{upload_id}/review")
def review_upload(upload_id: int, request: Request, db: Annotated[Session, Depends(get_db)]):
    repository = UploadRepository(db)
    upload = repository.get_upload(upload_id)
    parse_job = repository.latest_parse_job(upload_id)
    if not upload or not parse_job:
        raise HTTPException(status_code=404, detail="Upload not found")

    candidates = ParseService.from_json(parse_job.extracted_json)
    rows = candidates or [_blank_candidate() for _ in range(5)]
    return templates.TemplateResponse(
        request=request,
        name="review_upload.html",
        context={"upload": upload, "parse_job": parse_job, "rows": rows, "is_admin": True},
    )


@router.post("/{upload_id}/approve")
def approve_upload(
    upload_id: int,
    academic_year: Annotated[list[str], Form()],
    class_name: Annotated[list[str], Form()],
    section: Annotated[list[str], Form()],
    exam_term: Annotated[list[str], Form()],
    exam_date: Annotated[list[str], Form()],
    subject_name: Annotated[list[str], Form()],
    student_name: Annotated[list[str], Form()],
    score: Annotated[list[str], Form()],
    max_marks: Annotated[list[str], Form()],
    absent_flag: Annotated[list[str], Form()],
    remarks: Annotated[list[str], Form()],
    db: Annotated[Session, Depends(get_db)],
    selected_rows: Annotated[list[int] | None, Form()] = None,
):
    if not UploadRepository(db).get_upload(upload_id):
        raise HTTPException(status_code=404, detail="Upload not found")

    rows = _approval_rows(
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
    ReviewService(db).approve_candidates(upload_id, rows, set(selected_rows or []))
    return RedirectResponse(url="/", status_code=303)


@router.post("/{upload_id}/reject")
def reject_upload(upload_id: int, db: Annotated[Session, Depends(get_db)]):
    repository = UploadRepository(db)
    parse_job = repository.latest_parse_job(upload_id)
    if not repository.get_upload(upload_id) or not parse_job:
        raise HTTPException(status_code=404, detail="Upload not found")

    repository.update_parse_job(
        parse_job=parse_job,
        parser_status="rejected",
        extracted_json=parse_job.extracted_json,
        error_message="Rejected by user.",
    )
    return RedirectResponse(url="/", status_code=303)


def _blank_candidate() -> dict:
    return {
        "academic_year": DEFAULT_ACADEMIC_YEAR,
        "class_name": DEFAULT_CLASS_NAME,
        "section": DEFAULT_SECTION,
        "exam_term": "",
        "exam_date": "",
        "subject_name": "",
        "student_name": "",
        "score": "",
        "max_marks": 100,
        "absent_flag": "N",
        "remarks": "",
    }


def _optional_float(value: str) -> float | None:
    return float(value) if value else None


def _required_float(value: str, default: float) -> float:
    return float(value) if value else default


def _approval_rows(
    *,
    academic_year: list[str],
    class_name: list[str],
    section: list[str],
    exam_term: list[str],
    exam_date: list[str],
    subject_name: list[str],
    student_name: list[str],
    score: list[str],
    max_marks: list[str],
    absent_flag: list[str],
    remarks: list[str],
) -> list[dict]:
    rows = []
    for index, student in enumerate(student_name):
        rows.append(
            {
                "academic_year": academic_year[index],
                "class_name": class_name[index],
                "section": section[index],
                "exam_term": exam_term[index],
                "exam_date": exam_date[index] or None,
                "subject_name": subject_name[index],
                "student_name": student,
                "score": _optional_float(score[index]),
                "max_marks": _required_float(max_marks[index], 100),
                "absent_flag": absent_flag[index] or "N",
                "remarks": remarks[index] or None,
            }
        )
    return rows


def _upload_result_html(result: dict) -> str:
    return (
        f"<div><strong>{result['parse_status']}</strong>: {result['message']}</div>"
        f"<div>{result['candidate_count']} candidate rows found.</div>"
        f"<a class='text-blue-700 underline' href='{result['review_url']}'>Review upload</a>"
    )
