from types import SimpleNamespace

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


def test_approval_requires_key_when_db_is_anonymized_and_maps_real_name_to_alias(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = MarkRepository(session)
    monkeypatch.setattr(PrivacyService, "privacy_enabled", staticmethod(lambda: True))
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


def test_approval_does_not_require_private_key_when_privacy_is_disabled(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = MarkRepository(session)
    repo.upsert_mark(
        MarkCreate(
            student_name="Student 0001",
            section="B",
            class_name="X",
            academic_year="2026-27",
            exam_term="CYCLE TEST - I",
            subject_name="Math",
            score=18,
            max_marks=20,
        )
    )
    monkeypatch.setattr(PrivacyService, "privacy_enabled", staticmethod(lambda: False))

    approved = ReviewService(session).approve_candidates(
        upload_id=1,
        rows=[
            {
                "student_name": "Svanik P",
                "section": "B",
                "class_name": "X",
                "academic_year": "2026-27",
                "exam_term": "SE-1",
                "subject_name": "Math",
                "score": 38,
                "max_marks": 40,
            }
        ],
    )

    assert approved == 1


def test_restore_database_replaces_sqlite_without_container_backup(tmp_path, monkeypatch):
    current_db = tmp_path / "current.db"
    restore_db = tmp_path / "restore.db"
    private_dir = tmp_path / "private"

    current_engine = create_engine(f"sqlite:///{current_db}")
    Base.metadata.create_all(bind=current_engine)
    with current_engine.begin() as connection:
        connection.execute(Student.__table__.insert().values(
            student_name="Old Name",
            class_name="X",
            section="B",
            academic_year="2026-27",
        ))
    current_engine.dispose()

    restore_engine = create_engine(f"sqlite:///{restore_db}")
    Base.metadata.create_all(bind=restore_engine)
    with restore_engine.begin() as connection:
        connection.execute(Student.__table__.insert().values(
            student_name="Restored Name",
            class_name="X",
            section="B",
            academic_year="2026-27",
        ))
    restore_engine.dispose()

    monkeypatch.setattr(
        PrivacyService,
        "current_database_path",
        staticmethod(lambda: str(current_db)),
    )
    monkeypatch.setattr(
        "app.services.privacy_service.get_settings",
        lambda: SimpleNamespace(private_dir=private_dir),
    )

    PrivacyService.restore_database(restore_db.read_bytes(), "restore.db")

    check_engine = create_engine(f"sqlite:///{current_db}")
    with check_engine.begin() as connection:
        restored_name = connection.execute(
            Student.__table__.select().with_only_columns(Student.student_name)
        ).scalar_one()
    check_engine.dispose()

    assert restored_name == "Restored Name"
    assert not (private_dir / "backups").exists()
    assert not (private_dir / "restores" / "restore-upload.tmp").exists()


def test_restore_database_rejects_non_sqlite_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        PrivacyService,
        "current_database_path",
        staticmethod(lambda: str(tmp_path / "current.db")),
    )

    with pytest.raises(ValueError, match="valid SQLite"):
        PrivacyService.restore_database(b"not a database", "notes.txt")
