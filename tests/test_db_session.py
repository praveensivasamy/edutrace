from app.db.bootstrap import (
    consolidate_exam_scope,
    ensure_display_name_columns,
    remove_exam_class_section_columns,
)
from sqlalchemy import create_engine, text


def test_exam_migration_removes_class_section_and_keeps_mark_links():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                create table exams (
                    id integer primary key,
                    exam_term varchar(100) not null,
                    exam_date varchar(20),
                    academic_year varchar(20) not null,
                    class_name varchar(50) not null,
                    section varchar(50) not null,
                    created_at datetime default current_timestamp
                )
                """
            )
        )
        connection.execute(text("create table marks (id integer primary key, exam_id integer)"))
        connection.execute(
            text(
                """
                insert into exams (id, exam_term, exam_date, academic_year, class_name, section)
                values
                    (1, 'CYCLE TEST - I', '06.04.26', '2026-27', 'X', 'B'),
                    (2, 'CYCLE TEST - I', '06.04.26', '2026-27', 'X', 'C')
                """
            )
        )
        connection.execute(text("insert into marks (id, exam_id) values (1, 2)"))

        consolidate_exam_scope(connection)
        remove_exam_class_section_columns(connection)
        connection.execute(
            text(
                """
                create table subjects (
                    id integer primary key,
                    subject_name varchar(200) not null
                )
                """
            )
        )
        ensure_display_name_columns(connection)

        columns = {
            row.name
            for row in connection.execute(text("pragma table_info(exams)")).mappings()
        }
        subject_columns = {
            row.name
            for row in connection.execute(text("pragma table_info(subjects)")).mappings()
        }
        exams = connection.execute(text("select id, exam_term from exams")).all()
        mark_exam_id = connection.execute(text("select exam_id from marks")).scalar_one()

    assert "class_name" not in columns
    assert "section" not in columns
    assert "display_name" in columns
    assert "display_name" in subject_columns
    assert exams == [(1, "CYCLE TEST - I")]
    assert mark_exam_id == 1
