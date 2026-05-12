from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models.exam import Exam
from app.db.models.mark import Mark
from app.db.models.student import Student
from app.db.models.subject import Subject
from app.schemas.marks import MarkCreate


class MarkRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_student(self, data: MarkCreate) -> Student:
        stmt = select(Student).where(
            Student.student_name == data.student_name.strip(),
            Student.class_name == data.class_name.strip(),
            Student.section == data.section.strip(),
            Student.academic_year == data.academic_year.strip(),
        )
        student = self.db.scalar(stmt)
        if student:
            return student

        student = Student(
            student_name=data.student_name.strip(),
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
            Exam.exam_date == data.exam_date,
            Exam.academic_year == data.academic_year.strip(),
            Exam.class_name == data.class_name.strip(),
            Exam.section == data.section.strip(),
        )
        exam = self.db.scalar(stmt)
        if exam:
            return exam

        exam = Exam(
            exam_term=data.exam_term.strip(),
            exam_date=data.exam_date,
            academic_year=data.academic_year.strip(),
            class_name=data.class_name.strip(),
            section=data.section.strip(),
        )
        self.db.add(exam)
        self.db.flush()
        return exam

    def upsert_mark(self, data: MarkCreate) -> Mark:
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

        self.db.commit()
        self.db.refresh(mark)
        return mark

    def list_marks(self) -> list[dict]:
        stmt: Select = (
            select(Mark, Student, Subject, Exam)
            .join(Student, Mark.student_id == Student.id)
            .join(Subject, Mark.subject_id == Subject.id)
            .join(Exam, Mark.exam_id == Exam.id)
            .order_by(Student.student_name, Subject.subject_name, Exam.exam_term)
        )
        result = self.db.execute(stmt).all()
        rows = []
        for mark, student, subject, exam in result:
            percentage = None
            if mark.score is not None and mark.max_marks:
                percentage = round((mark.score / mark.max_marks) * 100, 1)
            rows.append(
                {
                    "id": mark.id,
                    "academic_year": exam.academic_year,
                    "class_name": exam.class_name,
                    "section": exam.section,
                    "exam_term": exam.exam_term,
                    "exam_date": exam.exam_date,
                    "subject_name": subject.subject_name,
                    "student_name": student.student_name,
                    "score": mark.score,
                    "max_marks": mark.max_marks,
                    "percentage": percentage,
                    "absent_flag": mark.absent_flag,
                    "remarks": mark.remarks,
                }
            )
        return rows
