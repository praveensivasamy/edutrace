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
