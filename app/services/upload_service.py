import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repositories.upload_repository import UploadRepository
from app.services.parse_service import ParseService

logger = logging.getLogger(__name__)


class UploadService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    async def save_upload(self, file: UploadFile) -> dict:
        original_name = file.filename or "upload.bin"
        suffix = Path(original_name).suffix
        safe_name = f"{uuid4().hex}{suffix}"
        target_path = self.settings.upload_dir / safe_name
        content = await file.read()
        target_path.write_bytes(content)
        logger.info(
            "upload_received file_name=%s stored_as=%s size_bytes=%s",
            original_name,
            safe_name,
            len(content),
        )

        return self._create_parsed_upload(original_name, safe_name, target_path, content)

    def save_pasted_csv(self, csv_text: str) -> dict:
        content = csv_text.strip().encode("utf-8")
        safe_name = f"{uuid4().hex}.csv"
        target_path = self.settings.upload_dir / safe_name
        target_path.write_bytes(content)
        logger.info("csv_pasted stored_as=%s size_bytes=%s", safe_name, len(content))

        return self._create_parsed_upload("pasted-marks.csv", safe_name, target_path, content)

    def _create_parsed_upload(
        self, original_name: str, safe_name: str, target_path: Path, content: bytes
    ) -> dict:
        repository = UploadRepository(self.db)
        upload = repository.create_upload(
            file_name=original_name,
            file_path=str(target_path),
        )
        status, candidates, error = ParseService.parse_upload(original_name, content)
        logger.info(
            "upload_parsed upload_id=%s file_name=%s status=%s candidates=%s",
            upload.id,
            original_name,
            status,
            len(candidates),
        )
        parse_job = repository.latest_parse_job(upload.id)
        if parse_job:
            repository.update_parse_job(
                parse_job=parse_job,
                parser_status=status,
                extracted_json=ParseService.to_json(candidates),
                error_message=error,
            )
        return {
            "upload_id": upload.id,
            "file_name": upload.file_name,
            "stored_as": safe_name,
            "parse_status": status,
            "candidate_count": len(candidates),
            "review_url": f"/uploads/{upload.id}/review",
            "message": error or "File parsed. Review and approve before saving marks.",
        }
