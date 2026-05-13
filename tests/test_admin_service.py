from app.db.base import Base
from app.db.models import Exam, Mark, ParseJob, Student, Subject, Upload
from app.db.repositories.mark_repository import MarkRepository
from app.db.repositories.upload_repository import UploadRepository
from app.schemas.marks import MarkCreate
from app.services.admin_service import AdminService
from app.services.parse_service import ParseService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

MODELS = (Exam, Mark, ParseJob, Student, Subject, Upload)


def test_admin_stats_and_purge(tmp_path):
    assert MODELS
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    MarkRepository(session).upsert_mark(
        MarkCreate(
            student_name="Svanik P",
            class_name="X",
            section="B",
            academic_year="2026-27",
            exam_term="CYCLE TEST - I",
            subject_name="Math",
            score=18,
            max_marks=20,
        )
    )
    upload_file = tmp_path / "marks.xlsx"
    upload_file.write_text("content")

    service = AdminService(session)
    service.settings.upload_dir = tmp_path

    assert service.stats()["table_counts"]["marks"] == 1

    result = service.purge_all()

    assert result["after"]["table_counts"]["marks"] == 0
    assert result["after"]["table_counts"]["students"] == 0
    assert result["removed_uploads"] == ["marks.xlsx"]


def test_admin_exam_dates_include_staged_upload_defaults():
    assert MODELS
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    upload_repo = UploadRepository(session)
    upload = upload_repo.create_upload("marks.xlsx", "uploads/marks.xlsx")
    parse_job = upload_repo.latest_parse_job(upload.id)
    rows = [
        {
            "academic_year": "2026-27",
            "class_name": "X",
            "section": "B",
            "exam_term": "CYCLE TEST - I",
            "exam_date": "06.04.26",
            "subject_name": "Math",
            "student_name": "Svanik P",
            "score": 18,
            "max_marks": 20,
            "absent_flag": "N",
            "remarks": None,
        },
        {
            "academic_year": "2026-27",
            "class_name": "X",
            "section": "B",
            "exam_term": "CYCLE TEST - I",
            "exam_date": "06.04.26",
            "subject_name": "Eng",
            "student_name": "Svanik P",
            "score": 17,
            "max_marks": 20,
            "absent_flag": "N",
            "remarks": None,
        },
    ]
    upload_repo.update_parse_job(parse_job, "needs_review", ParseService.to_json(rows), None)

    service = AdminService(session)

    assert service.exam_date_options() == [
        {
            "academic_year": "2026-27",
            "exam_term": "CYCLE TEST - I",
            "exam_date": "06.04.26",
            "exam_count": 0,
            "candidate_count": 2,
            "source": "Staged upload",
            "upload_name": "marks.xlsx",
        }
    ]

    assert service.approve_exam_date("2026-27", "CYCLE TEST - I", "07.04.26") == 2
    updated_rows = ParseService.from_json(upload_repo.latest_parse_job(upload.id).extracted_json)
    assert {row["exam_date"] for row in updated_rows} == {"07.04.26"}
