from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    upload_status: Mapped[str] = mapped_column(String(50), nullable=False, default="uploaded")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    marks = relationship("Mark", back_populates="source_upload")
    parse_jobs = relationship("ParseJob", back_populates="upload", cascade="all, delete-orphan")
