import base64
import json
from types import SimpleNamespace

from app.api.routes_dashboard import _privacy_safe_target_rows, _resolve_target_rows
from app.db.base import Base
from app.db.models import Exam, Mark, ParseJob, Student, Subject, Upload
from app.db.repositories.mark_repository import MarkRepository
from app.db.session import get_db
from app.main import app
from app.schemas.marks import MarkCreate
from app.services.privacy_service import PrivacyService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

MODELS = (Exam, Mark, ParseJob, Student, Subject, Upload)


def _principal_header(
    *roles: str,
    user_id: str = "user-1",
    user_name: str = "user@example.com",
) -> str:
    payload = {
        "userId": user_id,
        "userDetails": user_name,
        "claims": [{"typ": "roles", "val": role} for role in roles],
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def _client_with_empty_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_target_dashboard_rows_show_revealed_target_name_only_for_target():
    assert MODELS
    rows = [
        {
            "student_name": "Svanik P",
            "student_key": "Student 0001",
            "section": "B",
        },
        {
            "student_name": "Asha R",
            "student_key": "Student 0002",
            "section": "B",
        },
    ]

    private_rows, matched = _privacy_safe_target_rows(rows, "Svanik")

    visible_names = {row["student_name"] for row in private_rows}
    assert matched is True
    assert visible_names == {"Svanik P", "Student 0002"}


def test_target_dashboard_rows_show_alias_when_names_are_not_revealed():
    rows = [
        {
            "student_name": "Student 0001",
            "student_key": "Student 0001",
            "section": "B",
        },
        {
            "student_name": "Student 0002",
            "student_key": "Student 0002",
            "section": "B",
        },
    ]

    private_rows, matched = _privacy_safe_target_rows(rows, "Student 0001")

    visible_names = {row["student_name"] for row in private_rows}
    assert matched is True
    assert visible_names == {"Student 0001", "Student 0002"}


def test_target_dashboard_rows_show_all_revealed_names_when_privacy_is_disabled():
    rows = [
        {
            "student_name": "Svanik P",
            "student_key": "Student 0001",
            "section": "B",
        },
        {
            "student_name": "Asha R",
            "student_key": "Student 0002",
            "section": "B",
        },
    ]

    private_rows, matched = _privacy_safe_target_rows(
        rows,
        "Svanik",
        privacy_enabled=False,
    )

    visible_names = {row["student_name"] for row in private_rows}
    assert matched is True
    assert visible_names == {"Svanik P", "Asha R"}


def test_target_dashboard_rows_keep_configured_name_when_no_rows_match():
    rows = [
        {
            "student_name": "Asha R",
            "student_key": "Asha R",
            "section": "B",
        }
    ]

    private_rows, matched = _privacy_safe_target_rows(rows, "Svanik P")

    assert matched is False
    assert private_rows[0]["student_name"] == "Asha R"


def test_resolve_target_rows_falls_back_to_alias_for_anonymized_db():
    rows = [
        {
            "student_name": "Student 0001",
            "student_key": "Student 0001",
            "section": "B",
        },
        {
            "student_name": "Student 0002",
            "student_key": "Student 0002",
            "section": "B",
        },
    ]

    private_rows, display_label, analytics_query = _resolve_target_rows(
        rows,
        target_display_name="Svanik P",
        target_alias="Student 0001",
        privacy_enabled=False,
    )

    assert display_label == "Svanik P"
    assert analytics_query == "Student 0001"
    assert private_rows[0]["student_name"] == "Student 0001"


def test_privacy_page_is_separate_from_admin_page():
    try:
        client = _client_with_empty_db()
        headers = {"X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Admin")}
        admin_response = client.get("/admin", headers=headers)
        privacy_response = client.get("/admin/privacy", headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert admin_response.status_code == 200
    assert privacy_response.status_code == 200
    assert "Anonymize DB" not in admin_response.text
    assert "Privacy masking is disabled" in privacy_response.text
    assert "EDUTRACE_PRIVACY_ENABLED=true" in privacy_response.text
    assert "Download current SQLite DB" in privacy_response.text
    assert "Restore SQLite DB" in privacy_response.text
    assert "Anonymize DB" not in privacy_response.text
    assert 'href="/admin/privacy"' in admin_response.text


def test_dashboard_hides_ingest_controls_and_admin_shows_them():
    try:
        client = _client_with_empty_db()
        admin_headers = {"X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Admin")}
        viewer_headers = {"X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Viewer")}

        admin_dashboard = client.get("/", headers=admin_headers)
        viewer_dashboard = client.get("/", headers=viewer_headers)
        admin_page = client.get("/admin", headers=admin_headers)
    finally:
        app.dependency_overrides.clear()

    assert admin_dashboard.status_code == 200
    assert viewer_dashboard.status_code == 200
    assert admin_page.status_code == 200

    assert "/uploads/api" not in admin_dashboard.text
    assert "/uploads/paste" not in admin_dashboard.text
    assert "Open Admin Dashboard" in admin_dashboard.text

    assert "/uploads/api" not in viewer_dashboard.text
    assert "/uploads/paste" not in viewer_dashboard.text
    assert "Open Admin Dashboard" not in viewer_dashboard.text

    assert "/uploads/api" in admin_page.text
    assert "/uploads/paste" in admin_page.text


def test_privacy_disabled_page_only_shows_download_and_restore(monkeypatch):
    monkeypatch.setattr(
        "app.services.privacy_service.get_settings",
        lambda: SimpleNamespace(privacy_enabled=False),
    )
    try:
        client = _client_with_empty_db()
        response = client.get(
            "/admin/privacy",
            headers={"X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Admin")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Privacy masking is disabled" in response.text
    assert "Download current SQLite DB" in response.text
    assert "Restore SQLite DB" in response.text
    assert "Anonymize DB" not in response.text
    assert "Reveal Names On Screen" not in response.text


def test_privacy_disabled_blocks_key_and_anonymize_routes(monkeypatch):
    monkeypatch.setattr(PrivacyService, "privacy_enabled", staticmethod(lambda: False))
    try:
        client = _client_with_empty_db()
        response = client.post(
            "/admin/privacy/anonymize",
            headers={"X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Admin")},
            data={"passphrase": "private-pass"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_approved_marks_dashboard_supports_pagination():
    db_override = None
    try:
        client = _client_with_empty_db()
        db_override = app.dependency_overrides[get_db]()
        db = next(db_override)
        repo = MarkRepository(db)
        for index in range(1, 46):
            repo.upsert_mark(
                MarkCreate(
                    student_name=f"Student {index:03d}",
                    section="B",
                    class_name="X",
                    academic_year="2026-27",
                    exam_term="CYCLE TEST - I",
                    subject_name="Math",
                    score=18,
                    max_marks=20,
                )
            )
        response = client.get(
            "/dashboards/approved-marks?page=2&page_size=20",
            headers={"X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Admin")},
        )
    finally:
        try:
            if db_override is not None:
                db_override.close()
        except Exception:
            pass
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Showing 20 row(s) on page 2 of 3." in response.text
    assert "Student 021" in response.text
    assert "Student 001" not in response.text


def test_audit_dashboard_htmx_returns_results_partial():
    db_override = None
    try:
        client = _client_with_empty_db()
        db_override = app.dependency_overrides[get_db]()
        db = next(db_override)
        MarkRepository(db).upsert_mark(
            MarkCreate(
                student_name="Student 001",
                section="B",
                class_name="X",
                academic_year="2026-27",
                exam_term="CYCLE TEST - I",
                subject_name="Math",
                score=18,
                max_marks=20,
            )
        )
        response = client.get(
            "/audit?student_name=Student",
            headers={
                "X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Admin"),
                "HX-Request": "true",
            },
        )
    finally:
        try:
            if db_override is not None:
                db_override.close()
        except Exception:
            pass
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert 'id="audit-results"' in response.text
    assert "Student 001" in response.text


def test_student_compare_limits_selected_students_to_ten():
    query = "&".join([f"student=Student%20{index:03d}" for index in range(1, 12)])
    try:
        client = _client_with_empty_db()
        response = client.get(
            f"/dashboards/student-compare?{query}",
            headers={"X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Admin")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Maximum 10 students can be compared at once." in response.text
    assert "Student 010" in response.text
    assert "Student 011" not in response.text
