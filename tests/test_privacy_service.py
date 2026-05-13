import pytest
from app.db.base import Base
from app.db.models import Exam, Mark, ParseJob, Student, Subject, Upload
from app.db.repositories.mark_repository import MarkRepository
from app.schemas.marks import MarkCreate
from app.services.privacy_service import PrivacyService, clear_reveal_key
from app.services.review_service import ReviewService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

MODELS = (Exam, Mark, ParseJob, Student, Subject, Upload)


def test_privacy_key_encrypts_and_decrypts_mapping():
    assert MODELS
    mapping = {"Student 0001": "Svanik P"}

    encrypted = PrivacyService.encrypt_mapping(mapping, "private-pass")

    assert b"Svanik" not in encrypted
    assert PrivacyService.decrypt_mapping(encrypted, "private-pass") == mapping
    with pytest.raises(ValueError):
        PrivacyService.decrypt_mapping(encrypted, "wrong-pass")


def test_anonymize_students_keeps_db_anonymous_and_reveals_names_in_memory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = MarkRepository(session)
    repo.upsert_mark(
        MarkCreate(
            student_name="Svanik P",
            section="B",
            class_name="X",
            academic_year="2026-27",
            exam_term="CYCLE TEST - I",
            subject_name="Math",
            score=18,
            max_marks=20,
        )
    )

    encrypted = PrivacyService(session).anonymize_students("private-pass")

    assert session.query(Student).one().student_name == "Student 0001"
    assert repo.list_marks()[0]["student_name"] == "Student 0001"

    loaded = PrivacyService.load_reveal_key(encrypted, "private-pass")

    assert loaded == 1
    assert repo.list_marks()[0]["student_name"] == "Svanik P"
    assert session.query(Student).one().student_name == "Student 0001"

    clear_reveal_key()
    assert repo.list_marks()[0]["student_name"] == "Student 0001"


def test_approval_requires_key_when_db_is_anonymized_and_maps_real_name_to_alias():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = MarkRepository(session)
    repo.upsert_mark(
        MarkCreate(
            student_name="Svanik P",
            section="B",
            class_name="X",
            academic_year="2026-27",
            exam_term="CYCLE TEST - I",
            subject_name="Math",
            score=18,
            max_marks=20,
        )
    )
    key = PrivacyService(session).anonymize_students("private-pass")
    new_row = {
        "student_name": "Svanik P",
        "section": "B",
        "class_name": "X",
        "academic_year": "2026-27",
        "exam_term": "SE-1",
        "subject_name": "Math",
        "score": 38,
        "max_marks": 40,
    }

    with pytest.raises(ValueError):
        ReviewService(session).approve_candidates(upload_id=1, rows=[new_row])

    PrivacyService.load_reveal_key(key, "private-pass")
    approved = ReviewService(session).approve_candidates(upload_id=1, rows=[new_row])

    assert approved == 1
    assert {student.student_name for student in session.query(Student).all()} == {"Student 0001"}
    assert {row["exam_term"] for row in repo.list_marks()} == {"CYCLE TEST - I", "SE-1"}
