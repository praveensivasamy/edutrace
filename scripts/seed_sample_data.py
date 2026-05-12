from app.db.repositories.mark_repository import MarkRepository
from app.db.session import SessionLocal, init_db
from app.schemas.marks import MarkCreate

SAMPLE_ROWS = [
    MarkCreate(exam_term="SE-1", subject_name="French II Language", student_name="Svanik P", score=34, max_marks=40),
    MarkCreate(exam_term="T1", subject_name="Biology", student_name="Svanik P", score=17.5, max_marks=20),
    MarkCreate(exam_term="T1", subject_name="Social", student_name="Svanik P", score=16.5, max_marks=20),
    MarkCreate(exam_term="SE-1", subject_name="French II Language", student_name="Ananya Anand", score=37.5, max_marks=40),
    MarkCreate(exam_term="T1", subject_name="Biology", student_name="Nathan Nivedh Anandaraj", score=19.5, max_marks=20),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        repo = MarkRepository(db)
        for row in SAMPLE_ROWS:
            repo.upsert_mark(row)
        print(f"Seeded {len(SAMPLE_ROWS)} sample records.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
