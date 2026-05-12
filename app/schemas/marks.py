from pydantic import BaseModel, Field


class MarkCreate(BaseModel):
    academic_year: str = "2026-2027"
    class_name: str = "IX"
    section: str = "B"
    exam_term: str
    exam_date: str | None = None
    subject_name: str
    student_name: str
    roll_no: str | None = None
    gender: str | None = None
    score: float | None = Field(default=None, ge=0)
    max_marks: float = Field(gt=0)
    absent_flag: str = "N"
    remarks: str | None = None
    source_upload_id: int | None = None


class MarkView(BaseModel):
    id: int
    academic_year: str
    class_name: str
    section: str
    exam_term: str
    exam_date: str | None
    subject_name: str
    student_name: str
    score: float | None
    max_marks: float
    percentage: float | None
    absent_flag: str
    remarks: str | None

    model_config = {"from_attributes": True}
