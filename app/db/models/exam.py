from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint(
            "exam_term", "exam_date", "academic_year", "class_name", "section", name="uq_exam_scope"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    exam_term: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    exam_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    class_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    marks = relationship("Mark", back_populates="exam")
