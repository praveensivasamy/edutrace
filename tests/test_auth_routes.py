import base64
import json

from app.db.base import Base
from app.db.models import Exam, Mark, ParseJob, Student, Subject, Upload
from app.db.session import get_db
from app.main import app
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
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    return encoded


def _client_with_empty_db() -> TestClient:
    assert MODELS
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


def test_admin_is_allowed_for_mutating_marks_route():
    try:
        client = _client_with_empty_db()
        response = client.post(
            "/marks/add",
            headers={"X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Admin")},
            data={
                "academic_year": "2026-2027",
                "class_name": "IX",
                "section": "B",
                "exam_term": "T1",
                "subject_name": "Math",
                "student_name": "Asha",
                "max_marks": "100",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 303


def test_viewer_is_forbidden_for_mutating_marks_route():
    try:
        client = _client_with_empty_db()
        response = client.post(
            "/marks/add",
            headers={"X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Viewer")},
            data={"subject_name": "Math", "student_name": "Asha"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_missing_principal_is_forbidden_for_protected_route():
    try:
        client = _client_with_empty_db()
        response = client.post("/uploads/paste", data={"csv_text": "x,y\n1,2"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_viewer_can_access_read_only_dashboard():
    try:
        client = _client_with_empty_db()
        response = client.get(
            "/",
            headers={"X-MS-CLIENT-PRINCIPAL": _principal_header("EduTrace.Viewer")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
