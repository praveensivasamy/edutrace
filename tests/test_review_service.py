from app.db.base import Base
from app.db.models import Exam, Mark, ParseJob, Student, Subject, Upload
from app.db.repositories.mark_repository import MarkRepository
from app.db.repositories.upload_repository import UploadRepository
from app.services.review_service import ReviewService
from app.services.upload_service import UploadService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

MODELS = (Exam, ParseJob, Student, Subject)


def test_approve_candidates_commits_marks_with_upload_source():
    assert MODELS
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    upload = Upload(file_name="marks.csv", file_path="uploads/marks.csv", upload_status="uploaded")
    session.add(upload)
    session.commit()

    approved = ReviewService(session).approve_candidates(
        upload.id,
        [
            {
                "academic_year": "2026-2027",
                "class_name": "IX",
                "section": "B",
                "exam_term": "T1",
                "exam_date": None,
                "subject_name": "Math",
                "student_name": "Asha",
                "score": 18,
                "max_marks": 20,
                "absent_flag": "N",
                "remarks": None,
            }
        ],
    )

    rows = MarkRepository(session).list_marks()
    mark = session.query(Mark).one()

    assert approved == 1
    assert rows[0]["student_name"] == "Asha"
    assert rows[0]["percentage"] == 90
    assert mark.source_upload_id == upload.id


def test_pasted_csv_creates_review_candidates_without_committing_marks(tmp_path):
    assert MODELS
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    service = UploadService(session)
    service.settings.upload_dir = tmp_path

    result = service.save_pasted_csv(
        "student_name,subject_name,exam_term,score,max_marks\nAsha,Math,T1,18,20\n"
    )

    parse_job = UploadRepository(session).latest_parse_job(result["upload_id"])

    assert result["parse_status"] == "needs_review"
    assert result["candidate_count"] == 1
    assert parse_job is not None
    assert session.query(Mark).count() == 0


def test_approve_candidates_only_commits_selected_rows():
    assert MODELS
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    upload = Upload(file_name="marks.csv", file_path="uploads/marks.csv", upload_status="uploaded")
    session.add(upload)
    session.commit()

    rows = [
        {
            "academic_year": "2026-2027",
            "class_name": "IX",
            "section": "B",
            "exam_term": "T1",
            "exam_date": None,
            "subject_name": "Math",
            "student_name": "Asha",
            "score": 18,
            "max_marks": 20,
            "absent_flag": "N",
            "remarks": None,
        },
        {
            "academic_year": "2026-2027",
            "class_name": "IX",
            "section": "B",
            "exam_term": "T1",
            "exam_date": None,
            "subject_name": "Science",
            "student_name": "Ravi",
            "score": 16,
            "max_marks": 20,
            "absent_flag": "N",
            "remarks": None,
        },
    ]

    approved = ReviewService(session).approve_candidates(upload.id, rows, selected_indices={1})

    saved_rows = MarkRepository(session).list_marks()
    assert approved == 1
    assert saved_rows[0]["student_name"] == "Ravi"
