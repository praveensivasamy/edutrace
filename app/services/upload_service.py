from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repositories.upload_repository import UploadRepository


class UploadService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    async def save_upload(self, file: UploadFile) -> dict:
        suffix = Path(file.filename or "upload.bin").suffix
        safe_name = f"{uuid4().hex}{suffix}"
        target_path = self.settings.upload_dir / safe_name
        content = await file.read()
        target_path.write_bytes(content)

        upload = UploadRepository(self.db).create_upload(
            file_name=file.filename or safe_name,
            file_path=str(target_path),
        )
        return {
            "upload_id": upload.id,
            "file_name": upload.file_name,
            "stored_as": safe_name,
            "status": upload.upload_status,
            "message": "File uploaded. OCR/AI parsing will be added in the next milestone.",
        }
