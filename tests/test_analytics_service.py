from app.services.analytics_service import AnalyticsService


def test_summary_empty_rows():
    assert AnalyticsService.summary([])["records"] == 0


def test_summary_with_rows():
    rows = [
        {"student_name": "A", "subject_name": "Math", "percentage": 80},
        {"student_name": "B", "subject_name": "Math", "percentage": 90},
    ]
    summary = AnalyticsService.summary(rows)
    assert summary["records"] == 2
    assert summary["students"] == 2
    assert summary["subjects"] == 1
    assert summary["average_pct"] == 85
