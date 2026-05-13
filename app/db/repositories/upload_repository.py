from sqlalchemy.orm import Session

from app.db.models.parse_job import ParseJob
from app.db.models.upload import Upload


class UploadRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_upload(self, file_name: str, file_path: str) -> Upload:
        upload = Upload(file_name=file_name, file_path=file_path, upload_status="uploaded")
        self.db.add(upload)
        self.db.flush()
        parse_job = ParseJob(upload_id=upload.id, parser_status="pending")
        self.db.add(parse_job)
        self.db.commit()
        self.db.refresh(upload)
        return upload

    def get_upload(self, upload_id: int) -> Upload | None:
        return self.db.get(Upload, upload_id)

    def latest_parse_job(self, upload_id: int) -> ParseJob | None:
        return (
            self.db.query(ParseJob)
            .filter(ParseJob.upload_id == upload_id)
            .order_by(ParseJob.id.desc())
            .first()
        )

    def update_parse_job(
        self,
        parse_job: ParseJob,
        parser_status: str,
        extracted_json: str | None,
        error_message: str | None,
    ) -> ParseJob:
        parse_job.parser_status = parser_status
        parse_job.extracted_json = extracted_json
        parse_job.error_message = error_message
        self.db.commit()
        self.db.refresh(parse_job)
        return parse_job
