import logging

from sqlalchemy import Engine, text

from app.db.base import Base

logger = logging.getLogger(__name__)


def init_db(engine: Engine) -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_performance_indexes(engine)
    logger.info("database_initialized")


def ensure_performance_indexes(engine: Engine) -> None:
    index_statements = [
        "create index if not exists ix_exam_partition on exams (academic_year, exam_term)",
        "create unique index if not exists ux_exam_academic_year_term on exams "
        "(academic_year, exam_term)",
        "create index if not exists ix_mark_lookup on marks (exam_id, subject_id, student_id)",
    ]
    with engine.begin() as connection:
        consolidate_exam_scope(connection)
        remove_exam_class_section_columns(connection)
        ensure_display_name_columns(connection)
        for statement in index_statements:
            connection.execute(text(statement))


def consolidate_exam_scope(connection) -> None:
    groups = connection.execute(
        text(
            """
            select academic_year, exam_term, min(id) as canonical_id
            from exams
            group by academic_year, exam_term
            having count(*) > 1
            """
        )
    ).mappings()
    for group in groups:
        duplicate_ids = [
            row.id
            for row in connection.execute(
                text(
                    """
                    select id
                    from exams
                    where academic_year = :academic_year
                      and exam_term = :exam_term
                      and id != :canonical_id
                    """
                ),
                group,
            )
        ]
        if not duplicate_ids:
            continue
        canonical_date = connection.execute(
            text(
                """
                select exam_date
                from exams
                where academic_year = :academic_year
                  and exam_term = :exam_term
                  and exam_date is not null
                  and trim(exam_date) != ''
                order by id
                limit 1
                """
            ),
            group,
        ).scalar_one_or_none()
        if canonical_date:
            connection.execute(
                text("update exams set exam_date = :exam_date where id = :canonical_id"),
                {"exam_date": canonical_date, "canonical_id": group["canonical_id"]},
            )
        for duplicate_id in duplicate_ids:
            connection.execute(
                text("update marks set exam_id = :canonical_id where exam_id = :duplicate_id"),
                {"canonical_id": group["canonical_id"], "duplicate_id": duplicate_id},
            )
            connection.execute(
                text("delete from exams where id = :duplicate_id"),
                {"duplicate_id": duplicate_id},
            )
        logger.info(
            "exam_scope_consolidated academic_year=%s exam_term=%s duplicates=%s",
            group["academic_year"],
            group["exam_term"],
            len(duplicate_ids),
        )


def remove_exam_class_section_columns(connection) -> None:
    columns = {row.name for row in connection.execute(text("pragma table_info(exams)")).mappings()}
    if not {"class_name", "section"}.intersection(columns):
        return

    connection.execute(text("pragma foreign_keys = off"))
    connection.execute(
        text(
            """
            create table exams_normalized (
                id integer not null primary key,
                exam_term varchar(100) not null,
                display_name varchar(120),
                exam_date varchar(20),
                academic_year varchar(20) not null,
                created_at datetime default current_timestamp,
                constraint uq_exam_academic_year_term unique (academic_year, exam_term)
            )
            """
        )
    )
    connection.execute(
        text(
            """
            insert into exams_normalized (
                id, exam_term, display_name, exam_date, academic_year, created_at
            )
            select id, exam_term, null, exam_date, academic_year, created_at
            from exams
            """
        )
    )
    connection.execute(text("drop table exams"))
    connection.execute(text("alter table exams_normalized rename to exams"))
    connection.execute(text("pragma foreign_keys = on"))
    logger.info("exam_table_normalized_removed_class_section")


def ensure_display_name_columns(connection) -> None:
    for table in ("exams", "subjects"):
        columns = {
            row.name
            for row in connection.execute(text(f"pragma table_info({table})")).mappings()
        }
        if "display_name" not in columns:
            connection.execute(text(f"alter table {table} add column display_name varchar(120)"))
            logger.info("display_name_column_added table=%s", table)
