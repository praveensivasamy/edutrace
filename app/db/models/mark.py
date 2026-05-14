from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Mark(Base):
    __tablename__ = "marks"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "subject_id",
            "exam_id",
            name="uq_mark_student_subject_exam",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_marks: Mapped[float] = mapped_column(Float, nullable=False)
    absent_flag: Mapped[str] = mapped_column(String(5), nullable=False, default="N")
    remarks: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id"), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    student = relationship("Student", back_populates="marks")
    subject = relationship("Subject", back_populates="marks")
    exam = relationship("Exam", back_populates="marks")
    source_upload = relationship("Upload", back_populates="marks")
