from app.db.base import Base
from app.db.models import Exam, Mark, ParseJob, Student, Subject, Upload
from app.db.repositories.mark_repository import MarkRepository
from app.schemas.marks import MarkCreate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

MODELS = (Exam, Mark, ParseJob, Student, Subject, Upload)


def test_repository_formats_student_name_and_updates_mark_numbers():
    assert MODELS
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = MarkRepository(session)

    mark = repo.upsert_mark(
        MarkCreate(
            student_name="BHAVISHYA A N",
            section="D",
            class_name="X",
            academic_year="2026-27",
            exam_term="CYCLE TEST - I",
            subject_name="Eng",
            score=19,
            max_marks=20,
        )
    )

    repo.update_mark_numbers(
        mark.id,
        score=18.5,
        max_marks=20,
        absent_flag="N",
        remarks="Corrected",
    )
    rows = repo.list_marks()

    assert rows[0]["student_name"] == "Bhavishya A N"
    assert rows[0]["score"] == 18.5
    assert rows[0]["percentage"] == 92.5
    assert rows[0]["remarks"] == "Corrected"


def test_repository_lists_marks_by_partition_filters():
    assert MODELS
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
    repo.upsert_mark(
        MarkCreate(
            student_name="Svanik P",
            section="B",
            class_name="X",
            academic_year="2026-27",
            exam_term="SE-1",
            subject_name="Math",
            score=38,
            max_marks=40,
        )
    )

    rows = repo.list_marks({"exam_term": "SE-1"})

    assert len(rows) == 1
    assert rows[0]["exam_term"] == "SE-1"


def test_repository_lists_marks_by_student_name_filter():
    assert MODELS
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
    repo.upsert_mark(
        MarkCreate(
            student_name="Ravi",
            section="B",
            class_name="X",
            academic_year="2026-27",
            exam_term="CYCLE TEST - I",
            subject_name="Math",
            score=19,
            max_marks=20,
        )
    )

    rows = repo.list_marks({"student_name": "svan"})

    assert len(rows) == 1
    assert rows[0]["student_name"] == "Svanik P"


def test_repository_lists_marks_by_subject_filter():
    assert MODELS
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
    repo.upsert_mark(
        MarkCreate(
            student_name="Svanik P",
            section="B",
            class_name="X",
            academic_year="2026-27",
            exam_term="CYCLE TEST - I",
            subject_name="Eng",
            score=19,
            max_marks=20,
        )
    )

    rows = repo.list_marks({"subject_name": "Eng"})

    assert len(rows) == 1
    assert rows[0]["subject_name"] == "Eng"


def test_repository_updates_exam_date_by_academic_year_and_test_type():
    assert MODELS
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = MarkRepository(session)
    for section in ("B", "C"):
        repo.upsert_mark(
            MarkCreate(
                student_name=f"Svanik {section}",
                section=section,
                class_name="X",
                academic_year="2026-27",
                exam_term="CYCLE TEST - I",
                exam_date="06.04.26",
                subject_name="Math",
                score=18,
                max_marks=20,
            )
        )

    updated = repo.update_exam_date("2026-27", "CYCLE TEST - I", "07.04.26")

    assert updated == 1
    assert repo.list_exam_dates() == [
        {
            "academic_year": "2026-27",
            "exam_term": "CYCLE TEST - I",
            "exam_date": "07.04.26",
            "exam_count": 1,
        }
    ]
    assert {row["exam_date"] for row in repo.list_marks()} == {"07.04.26"}


def test_repository_uses_one_exam_per_academic_year_and_test_type():
    assert MODELS
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = MarkRepository(session)
    for section in ("B", "C"):
        repo.upsert_mark(
            MarkCreate(
                student_name=f"Student {section}",
                section=section,
                class_name="X",
                academic_year="2026-27",
                exam_term="CYCLE TEST - I",
                subject_name="Math",
                score=18,
                max_marks=20,
            )
        )

    rows = repo.list_marks()

    assert session.query(Exam).count() == 1
    assert session.query(Exam).one().exam_term == "CYCLE TEST - I"
    assert {row["section"] for row in rows} == {"B", "C"}
    assert len(repo.list_marks({"section": "B"})) == 1


def test_repository_updates_exam_and_subject_display_names():
    assert MODELS
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
            subject_name="Eng",
            score=18,
            max_marks=20,
        )
    )
    exam_id = repo.list_exam_display_names()[0]["id"]
    subject_id = repo.list_subject_display_names()[0]["id"]

    assert repo.update_exam_display_name(exam_id, "Cycle Test 1")
    assert repo.update_subject_display_name(subject_id, "English")

    row = repo.list_marks()[0]
    assert row["exam_term"] == "CYCLE TEST - I"
    assert row["exam_display_name"] == "Cycle Test 1"
    assert row["subject_name"] == "Eng"
    assert row["subject_display_name"] == "English"
