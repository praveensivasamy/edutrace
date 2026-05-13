import logging
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.parse_job import ParseJob
from app.db.models.upload import Upload
from app.db.repositories.mark_repository import MarkRepository
from app.services.parse_service import ParseService

logger = logging.getLogger(__name__)


class AdminService:
    TABLES = ("marks", "parse_jobs", "uploads", "students", "subjects", "exams")

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def stats(self) -> dict:
        table_counts = {}
        for table in self.TABLES:
            table_counts[table] = self.db.execute(
                text(f"select count(*) from {table}")
            ).scalar_one()

        db_path = self._sqlite_path()
        page_size = self.db.execute(text("pragma page_size")).scalar_one()
        page_count = self.db.execute(text("pragma page_count")).scalar_one()
        freelist_count = self.db.execute(text("pragma freelist_count")).scalar_one()
        upload_files = [path for path in self.settings.upload_dir.glob("*") if path.is_file()]

        return {
            "table_counts": table_counts,
            "database_path": str(db_path) if db_path else "external database",
            "database_size_kb": (
                round(db_path.stat().st_size / 1024, 1) if db_path and db_path.exists() else 0
            ),
            "sqlite_allocated_kb": round((page_size * page_count) / 1024, 1),
            "sqlite_free_kb": round((page_size * freelist_count) / 1024, 1),
            "upload_file_count": len(upload_files),
            "upload_size_kb": round(sum(path.stat().st_size for path in upload_files) / 1024, 1),
        }

    def exam_date_options(self) -> list[dict]:
        grouped = {
            (row["academic_year"], row["exam_term"]): {
                **row,
                "candidate_count": 0,
                "source": "Approved",
            }
            for row in MarkRepository(self.db).list_exam_dates()
        }

        stmt = (
            select(ParseJob, Upload)
            .join(Upload, ParseJob.upload_id == Upload.id)
            .where(ParseJob.parser_status == "needs_review")
            .order_by(ParseJob.id.desc())
        )
        for parse_job, upload in self.db.execute(stmt).all():
            for row in ParseService.from_json(parse_job.extracted_json):
                academic_year = (row.get("academic_year") or "").strip()
                exam_term = (row.get("exam_term") or "").strip()
                if not academic_year or not exam_term:
                    continue
                key = (academic_year, exam_term)
                item = grouped.setdefault(
                    key,
                    {
                        "academic_year": academic_year,
                        "exam_term": exam_term,
                        "exam_date": row.get("exam_date") or "",
                        "exam_count": 0,
                        "candidate_count": 0,
                        "source": "Staged upload",
                    },
                )
                item["candidate_count"] += 1
                if not item["exam_date"] and row.get("exam_date"):
                    item["exam_date"] = row["exam_date"]
                if item["source"] == "Approved":
                    item["source"] = "Approved + staged"
                item["upload_name"] = upload.file_name

        return sorted(grouped.values(), key=lambda item: (item["academic_year"], item["exam_term"]))

    def approve_exam_date(self, academic_year: str, exam_term: str, exam_date: str | None) -> int:
        approved_count = MarkRepository(self.db).update_exam_date(
            academic_year=academic_year,
            exam_term=exam_term,
            exam_date=exam_date,
        )
        staged_count = self._update_staged_exam_date(academic_year, exam_term, exam_date)
        logger.info(
            "exam_date_updated academic_year=%s exam_term=%s approved_rows=%s staged_rows=%s",
            academic_year,
            exam_term,
            approved_count,
            staged_count,
        )
        return approved_count + staged_count

    def purge_all(self) -> dict:
        before = self.stats()
        self.db.execute(text("pragma foreign_keys = off"))
        for table in self.TABLES:
            self.db.execute(text(f"delete from {table}"))
        self.db.commit()

        removed_uploads = []
        for path in self.settings.upload_dir.glob("*"):
            if path.is_file() and path.name != ".gitkeep":
                path.unlink()
                removed_uploads.append(path.name)

        after = self.stats()
        logger.warning(
            "data_purged removed_uploads=%s before_marks=%s after_marks=%s",
            len(removed_uploads),
            before["table_counts"].get("marks"),
            after["table_counts"].get("marks"),
        )
        return {"before": before, "removed_uploads": removed_uploads, "after": after}

    def vacuum(self) -> None:
        self.db.commit()
        connection = self.db.get_bind().raw_connection()
        try:
            connection.execute("vacuum")
            connection.commit()
            logger.info("database_vacuum_completed")
        finally:
            connection.close()

    def _sqlite_path(self) -> Path | None:
        prefix = "sqlite:///"
        database_url = self.settings.database_url
        if not database_url.startswith(prefix):
            return None
        return Path(database_url.removeprefix(prefix))

    def _update_staged_exam_date(
        self, academic_year: str, exam_term: str, exam_date: str | None
    ) -> int:
        updated = 0
        jobs = self.db.scalars(
            select(ParseJob).where(ParseJob.parser_status == "needs_review")
        ).all()
        for job in jobs:
            rows = ParseService.from_json(job.extracted_json)
            changed = False
            for row in rows:
                if (
                    (row.get("academic_year") or "").strip() == academic_year.strip()
                    and (row.get("exam_term") or "").strip() == exam_term.strip()
                ):
                    row["exam_date"] = exam_date.strip() if exam_date else None
                    updated += 1
                    changed = True
            if changed:
                job.extracted_json = ParseService.to_json(rows)
        self.db.commit()
        return updated
