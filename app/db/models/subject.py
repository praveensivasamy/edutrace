from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subject_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    marks = relationship("Mark", back_populates="subject")
