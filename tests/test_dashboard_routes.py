from types import SimpleNamespace

from app.api.routes_dashboard import _privacy_safe_target_rows, _resolve_target_rows
from app.db.base import Base
from app.db.models import Exam, Mark, ParseJob, Student, Subject, Upload
from app.db.session import get_db
from app.main import app
from app.services.privacy_service import PrivacyService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

MODELS = (Exam, Mark, ParseJob, Student, Subject, Upload)


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
        admin_response = client.get("/admin")
        privacy_response = client.get("/admin/privacy")
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


def test_privacy_disabled_page_only_shows_download_and_restore(monkeypatch):
    monkeypatch.setattr(
        "app.services.privacy_service.get_settings",
        lambda: SimpleNamespace(privacy_enabled=False),
    )
    try:
        client = _client_with_empty_db()
        response = client.get("/admin/privacy")
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
        response = client.post("/admin/privacy/anonymize", data={"passphrase": "private-pass"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
