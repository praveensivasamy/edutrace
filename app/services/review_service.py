import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db.repositories.mark_repository import MarkRepository
from app.schemas.marks import MarkCreate
from app.services.privacy_service import PrivacyService

logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(self, db: Session):
        self.db = db

    def approve_candidates(
        self,
        upload_id: int,
        rows: list[dict[str, Any]],
        selected_indices: set[int] | None = None,
    ) -> int:
        repo = MarkRepository(self.db)
        privacy = PrivacyService(self.db)
        privacy.require_key_for_anonymized_upload()
        approved = 0
        try:
            for index, row in enumerate(rows):
                if selected_indices is not None and index not in selected_indices:
                    continue
                required_values = (
                    row.get("student_name"),
                    row.get("subject_name"),
                    row.get("exam_term"),
                )
                if not all(required_values):
                    continue
                row = {**row, "student_name": PrivacyService.storage_name(row["student_name"])}
                data = MarkCreate(**row, source_upload_id=upload_id)
                repo.upsert_mark(data, commit=False)
                approved += 1
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception(
                "approval_failed upload_id=%s approved_before_error=%s",
                upload_id,
                approved,
            )
            raise
        logger.info("approval_completed upload_id=%s approved=%s", upload_id, approved)
        return approved
