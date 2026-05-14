from collections.abc import Sequence

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session

from app.core.pagination import Page
from app.db.models.exam import Exam
from app.db.models.mark import Mark
from app.db.models.student import Student
from app.db.models.subject import Subject
from app.schemas.marks import MarkCreate
from app.services.privacy_service import PrivacyService


class MarkRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_student(self, data: MarkCreate) -> Student:
        student_name = self.format_student_name(data.student_name)
        stmt = select(Student).where(
            func.lower(Student.student_name) == student_name.lower(),
            Student.class_name == data.class_name.strip(),
            Student.section == data.section.strip(),
            Student.academic_year == data.academic_year.strip(),
        )
        student = self.db.scalar(stmt)
        if student:
            student.student_name = student_name
            return student

        student = Student(
            student_name=student_name,
            roll_no=data.roll_no,
            gender=data.gender,
            class_name=data.class_name.strip(),
            section=data.section.strip(),
            academic_year=data.academic_year.strip(),
        )
        self.db.add(student)
        self.db.flush()
        return student

    def get_or_create_subject(self, subject_name: str) -> Subject:
        normalized = subject_name.strip()
        subject = self.db.scalar(select(Subject).where(Subject.subject_name == normalized))
        if subject:
            return subject
        subject = Subject(subject_name=normalized)
        self.db.add(subject)
        self.db.flush()
        return subject

    def get_or_create_exam(self, data: MarkCreate) -> Exam:
        stmt = select(Exam).where(
            Exam.exam_term == data.exam_term.strip(),
            Exam.academic_year == data.academic_year.strip(),
        )
        exam = self.db.scalar(stmt)
        if exam:
            if not exam.exam_date and data.exam_date:
                exam.exam_date = data.exam_date
            return exam

        exam = Exam(
            exam_term=data.exam_term.strip(),
            exam_date=data.exam_date,
            academic_year=data.academic_year.strip(),
        )
        self.db.add(exam)
        self.db.flush()
        return exam

    def upsert_mark(self, data: MarkCreate, commit: bool = True) -> Mark:
        student = self.get_or_create_student(data)
        subject = self.get_or_create_subject(data.subject_name)
        exam = self.get_or_create_exam(data)

        stmt = select(Mark).where(
            Mark.student_id == student.id,
            Mark.subject_id == subject.id,
            Mark.exam_id == exam.id,
        )
        mark = self.db.scalar(stmt)
        if mark:
            mark.score = data.score
            mark.max_marks = data.max_marks
            mark.absent_flag = data.absent_flag
            mark.remarks = data.remarks
            mark.source_upload_id = data.source_upload_id
        else:
            mark = Mark(
                student_id=student.id,
                subject_id=subject.id,
                exam_id=exam.id,
                score=data.score,
                max_marks=data.max_marks,
                absent_flag=data.absent_flag,
                remarks=data.remarks,
                source_upload_id=data.source_upload_id,
            )
            self.db.add(mark)

        if commit:
            self.db.commit()
            self.db.refresh(mark)
        else:
            self.db.flush()
        return mark

    def list_exam_dates(self) -> list[dict]:
        rows = self.db.scalars(
            select(Exam).order_by(Exam.academic_year, Exam.exam_term)
        ).all()
        grouped: dict[tuple[str, str], dict] = {}
        for exam in rows:
            key = (exam.academic_year, exam.exam_term)
            item = grouped.setdefault(
                key,
                {
                    "academic_year": exam.academic_year,
                    "exam_term": exam.exam_term,
                    "exam_date": exam.exam_date or "",
                    "exam_count": 0,
                },
            )
            item["exam_count"] += 1
            if not item["exam_date"] and exam.exam_date:
                item["exam_date"] = exam.exam_date
        return sorted(grouped.values(), key=lambda item: (item["academic_year"], item["exam_term"]))

    def update_exam_date(self, academic_year: str, exam_term: str, exam_date: str | None) -> int:
        result = self.db.execute(
            update(Exam)
            .where(
                Exam.academic_year == academic_year.strip(),
                Exam.exam_term == exam_term.strip(),
            )
            .values(exam_date=exam_date.strip() if exam_date else None)
        )
        self.db.commit()
        return result.rowcount or 0

    def list_exam_display_names(self) -> list[dict]:
        rows = self.db.scalars(select(Exam).order_by(Exam.academic_year, Exam.exam_term)).all()
        return [
            {
                "id": exam.id,
                "academic_year": exam.academic_year,
                "exam_term": exam.exam_term,
                "display_name": exam.display_name or "",
                "effective_name": exam.display_name or exam.exam_term,
                "exam_date": exam.exam_date or "",
            }
            for exam in rows
        ]

    def update_exam_display_name(self, exam_id: int, display_name: str | None) -> bool:
        exam = self.db.get(Exam, exam_id)
        if not exam:
            return False
        exam.display_name = display_name.strip() if display_name and display_name.strip() else None
        self.db.commit()
        return True

    def list_subject_display_names(self) -> list[dict]:
        rows = self.db.scalars(select(Subject).order_by(Subject.subject_name)).all()
        return [
            {
                "id": subject.id,
                "subject_name": subject.subject_name,
                "display_name": subject.display_name or "",
                "effective_name": subject.display_name or subject.subject_name,
            }
            for subject in rows
        ]

    def update_subject_display_name(self, subject_id: int, display_name: str | None) -> bool:
        subject = self.db.get(Subject, subject_id)
        if not subject:
            return False
        subject.display_name = (
            display_name.strip() if display_name and display_name.strip() else None
        )
        self.db.commit()
        return True

    def update_mark_numbers(
        self,
        mark_id: int,
        score: float | None,
        max_marks: float,
        absent_flag: str,
        remarks: str | None,
    ) -> Mark | None:
        mark = self.db.get(Mark, mark_id)
        if not mark:
            return None
        mark.score = score
        mark.max_marks = max_marks
        mark.absent_flag = absent_flag.strip() or "N"
        mark.remarks = remarks
        self.db.commit()
        self.db.refresh(mark)
        return mark

    def list_marks(self, filters: dict[str, str] | None = None) -> list[dict]:
        stmt = self._mark_query(filters)
        return self._rows_from_result(self.db.execute(stmt).all())

    def list_marks_page(
        self,
        filters: dict[str, str] | None = None,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> Page[dict]:
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 200))
        stmt = self._mark_query(filters)
        total_items = self.count_marks(filters)
        paged_stmt = stmt.offset((safe_page - 1) * safe_page_size).limit(safe_page_size)
        rows = self._rows_from_result(self.db.execute(paged_stmt).all())
        return Page(
            items=rows,
            page=safe_page,
            page_size=safe_page_size,
            total_items=total_items,
        )

    def count_marks(self, filters: dict[str, str] | None = None) -> int:
        stmt = self._mark_query(filters, order_by=False).with_only_columns(
            func.count(Mark.id),
            maintain_column_froms=True,
        )
        return int(self.db.scalar(stmt) or 0)

    def _mark_query(
        self,
        filters: dict[str, str] | None = None,
        *,
        order_by: bool = True,
    ) -> Select:
        stmt: Select = (
            select(Mark, Student, Subject, Exam)
            .join(Student, Mark.student_id == Student.id)
            .join(Subject, Mark.subject_id == Subject.id)
            .join(Exam, Mark.exam_id == Exam.id)
        )
        stmt = self._apply_mark_filters(stmt, filters or {})
        if order_by:
            stmt = stmt.order_by(Student.student_name, Subject.subject_name, Exam.exam_term)
        return stmt

    def _apply_mark_filters(self, stmt: Select, filters: dict[str, str]) -> Select:
        if filters.get("academic_year"):
            stmt = stmt.where(Exam.academic_year == filters["academic_year"])
        if filters.get("class_name"):
            stmt = stmt.where(Student.class_name == filters["class_name"])
        if filters.get("section"):
            stmt = stmt.where(Student.section == filters["section"])
        if filters.get("exam_term"):
            stmt = stmt.where(Exam.exam_term == filters["exam_term"])
        if filters.get("student_name"):
            stmt = stmt.where(Student.student_name.ilike(f"%{filters['student_name']}%"))
        if filters.get("subject_name"):
            stmt = stmt.where(Subject.subject_name == filters["subject_name"])
        return stmt

    def _rows_from_result(
        self,
        result: Sequence[tuple[Mark, Student, Subject, Exam]],
    ) -> list[dict]:
        return [
            self._mark_row(mark, student, subject, exam)
            for mark, student, subject, exam in result
        ]

    def _mark_row(self, mark: Mark, student: Student, subject: Subject, exam: Exam) -> dict:
        normalized_name = self.format_student_name(student.student_name)
        percentage = None
        if mark.score is not None and mark.max_marks:
            percentage = round((mark.score / mark.max_marks) * 100, 1)
        return {
            "id": mark.id,
            "academic_year": exam.academic_year,
            "class_name": student.class_name,
            "section": student.section,
            "exam_term": exam.exam_term,
            "exam_display_name": exam.display_name or exam.exam_term,
            "exam_date": exam.exam_date,
            "subject_name": subject.subject_name,
            "subject_display_name": subject.display_name or subject.subject_name,
            "student_name": PrivacyService.display_name(normalized_name),
            "student_key": normalized_name,
            "score": mark.score,
            "max_marks": mark.max_marks,
            "percentage": percentage,
            "absent_flag": mark.absent_flag,
            "remarks": mark.remarks,
        }

    def available_filters(self) -> dict[str, list[str]]:
        exam_stmt = select(
            Exam.academic_year,
            Exam.exam_term,
        ).distinct()
        rows = self.db.execute(exam_stmt).all()
        student_rows = self.db.execute(
            select(Student.class_name, Student.section).distinct()
        ).all()
        return {
            "academic_years": sorted({row.academic_year for row in rows if row.academic_year}),
            "classes": sorted({row.class_name for row in student_rows if row.class_name}),
            "sections": sorted({row.section for row in student_rows if row.section}),
            "students": [
                {
                    "value": student_name,
                    "label": PrivacyService.display_name(student_name),
                }
                for student_name in sorted(
                    {
                        self.format_student_name(student.student_name)
                        for student in self.db.scalars(select(Student)).all()
                    }
                )
                if student_name
            ],
            "exam_terms": [
                {
                    "value": row.exam_term,
                    "label": row.display_name or row.exam_term,
                }
                for row in self.db.scalars(
                    select(Exam).order_by(Exam.display_name, Exam.exam_term)
                ).all()
            ],
            "subjects": [
                {
                    "value": subject.subject_name,
                    "label": subject.display_name or subject.subject_name,
                }
                for subject in self.db.scalars(
                    select(Subject).order_by(Subject.display_name, Subject.subject_name)
                ).all()
            ],
        }

    @staticmethod
    def format_student_name(student_name: str) -> str:
        return " ".join(word.capitalize() for word in student_name.split())
