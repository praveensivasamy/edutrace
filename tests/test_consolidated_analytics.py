from app.api.routes_dashboard import _ordered_tests
from app.services.analytics_service import AnalyticsService


def test_student_rankings_aggregate_totals():
    rows = [
        {
            "student_name": "Asha",
            "class_name": "X",
            "section": "B",
            "subject_name": "Math",
            "score": 18,
            "max_marks": 20,
            "percentage": 90,
        },
        {
            "student_name": "Asha",
            "class_name": "X",
            "section": "B",
            "subject_name": "Science",
            "score": 36,
            "max_marks": 40,
            "percentage": 90,
        },
        {
            "student_name": "Ravi",
            "class_name": "X",
            "section": "C",
            "subject_name": "Math",
            "score": 19,
            "max_marks": 20,
            "percentage": 95,
        },
    ]

    rankings = AnalyticsService.student_rankings(rows)

    assert rankings[0]["student_name"] == "Ravi"
    assert rankings[0]["percentage"] == 95
    assert rankings[1]["student_name"] == "Asha"
    assert rankings[1]["score"] == 54
    assert rankings[1]["max_marks"] == 60


def test_subject_and_section_summaries():
    rows = [
        {"student_name": "Asha", "section": "B", "subject_name": "Math", "percentage": 90},
        {"student_name": "Ravi", "section": "B", "subject_name": "Math", "percentage": 80},
        {"student_name": "Mira", "section": "C", "subject_name": "Science", "percentage": 70},
    ]

    subjects = AnalyticsService.subject_summary(rows)
    sections = AnalyticsService.section_summary(rows)

    assert subjects[0]["subject_name"] == "Math"
    assert subjects[0]["average_pct"] == 85
    assert sections == [
        {"section": "B", "students": 2, "average_pct": 85},
        {"section": "C", "students": 1, "average_pct": 70},
    ]


def test_student_vs_top_by_subject_finds_student_and_top_10():
    rows = []
    for index in range(1, 12):
        rows.append(
            {
                "student_name": f"Student {index}",
                "class_name": "X",
                "section": "A",
                "exam_term": "CYCLE TEST - I",
                "subject_name": "Math",
                "score": 21 - index,
                "max_marks": 20,
                "percentage": 105 - (index * 5),
            }
        )
    rows.append(
        {
            "student_name": "Svanik P",
            "class_name": "X",
            "section": "B",
            "exam_term": "CYCLE TEST - I",
            "subject_name": "Math",
            "score": 10,
            "max_marks": 20,
            "percentage": 50,
        }
    )

    comparisons = AnalyticsService.student_vs_top_by_subject(rows, "svanik", top_n=10)

    assert len(comparisons) == 1
    assert comparisons[0]["target"]["student_name"] == "Svanik P"
    assert comparisons[0]["target"]["rank"] == 12
    assert len(comparisons[0]["top_students"]) == 10
    assert comparisons[0]["top_students"][0]["student_name"] == "Student 1"


def test_student_rank_trend_by_subject_tracks_test_wise_rank():
    rows = [
        {
            "student_name": "Topper",
            "exam_term": "CYCLE TEST - I",
            "subject_name": "Math",
            "section": "A",
            "score": 20,
            "max_marks": 20,
            "percentage": 100,
        },
        {
            "student_name": "Svanik P",
            "exam_term": "CYCLE TEST - I",
            "subject_name": "Math",
            "section": "B",
            "score": 18,
            "max_marks": 20,
            "percentage": 90,
        },
        {
            "student_name": "Svanik P",
            "exam_term": "SE-1",
            "subject_name": "Math",
            "section": "B",
            "score": 39,
            "max_marks": 40,
            "percentage": 97.5,
        },
        {
            "student_name": "Topper",
            "exam_term": "SE-1",
            "subject_name": "Math",
            "section": "A",
            "score": 38,
            "max_marks": 40,
            "percentage": 95,
        },
    ]

    trends = AnalyticsService.student_rank_trend_by_subject(rows, "svanik")

    assert trends == [
        {
            "subject_name": "Math",
            "subject_display_name": "Math",
            "points": [
                {
                    "exam_term": "CYCLE TEST - I",
                    "exam_display_name": "CYCLE TEST - I",
                    "subject_display_name": "Math",
                    "rank": 2,
                    "percentage": 90,
                    "score": 18,
                    "max_marks": 20,
                    "student_count": 2,
                    "rank_delta": 0,
                    "movement": "baseline",
                },
                {
                    "exam_term": "SE-1",
                    "exam_display_name": "SE-1",
                    "subject_display_name": "Math",
                    "rank": 1,
                    "percentage": 97.5,
                    "score": 39,
                    "max_marks": 40,
                    "student_count": 2,
                    "rank_delta": 1,
                    "movement": "improved",
                },
            ],
        }
    ]


def test_student_rank_trend_respects_custom_exam_order():
    rows = [
        {
            "student_name": "Svanik P",
            "exam_term": "CYCLE TEST - I",
            "subject_name": "Math",
            "section": "B",
            "score": 18,
            "max_marks": 20,
            "percentage": 90,
        },
        {
            "student_name": "Svanik P",
            "exam_term": "SE-1",
            "subject_name": "Math",
            "section": "B",
            "score": 39,
            "max_marks": 40,
            "percentage": 97.5,
        },
    ]

    trends = AnalyticsService.student_rank_trend_by_subject(
        rows, "svanik", exam_order=["SE-1", "CYCLE TEST - I"]
    )

    assert [point["exam_term"] for point in trends[0]["points"]] == ["SE-1", "CYCLE TEST - I"]


def test_ordered_tests_keeps_submitted_order_and_appends_missing_terms():
    assert _ordered_tests(
        available_exam_terms=["CYCLE TEST - I", "SE-1", "FINAL"],
        selected_exam_terms=["CYCLE TEST - I", "SE-1", "FINAL"],
        submitted_order=["FINAL", "SE-1"],
    ) == ["FINAL", "SE-1", "CYCLE TEST - I"]


def test_analysis_options_orders_tests_by_exam_start_date():
    rows = [
        {"exam_term": "SE-1", "exam_date": "12.08.26 to 13.08.26", "subject_name": "Math"},
        {"exam_term": "CYCLE TEST - I", "exam_date": "06.04.26", "subject_name": "Math"},
        {"exam_term": "MODEL", "exam_date": "", "subject_name": "Math"},
    ]

    options = AnalyticsService.analysis_options(rows)

    assert options["exam_terms"] == ["CYCLE TEST - I", "SE-1", "MODEL"]


def test_subject_toppers_by_test_includes_tied_student_names():
    rows = [
        {
            "student_name": "Asha",
            "section": "B",
            "exam_term": "CYCLE TEST - I",
            "subject_name": "Math",
            "score": 20,
            "max_marks": 20,
            "percentage": 100,
        },
        {
            "student_name": "Ravi",
            "section": "C",
            "exam_term": "CYCLE TEST - I",
            "subject_name": "Math",
            "score": 20,
            "max_marks": 20,
            "percentage": 100,
        },
        {
            "student_name": "Svanik P",
            "section": "B",
            "exam_term": "CYCLE TEST - I",
            "subject_name": "Math",
            "score": 18,
            "max_marks": 20,
            "percentage": 90,
        },
    ]

    toppers = AnalyticsService.subject_toppers_by_test(rows)

    assert toppers == [
            {
                "exam_term": "CYCLE TEST - I",
                "exam_display_name": "CYCLE TEST - I",
                "subject_name": "Math",
                "subject_display_name": "Math",
                "score": 20,
            "max_marks": 20,
            "percentage": 100,
            "students": ["Asha (B)", "Ravi (C)"],
        }
    ]


def test_grouped_subject_toppers_by_test_groups_under_exam_heading():
    rows = [
        {
            "student_name": "Asha",
            "section": "B",
            "exam_term": "CYCLE TEST - I",
            "subject_name": "Math",
            "score": 20,
            "max_marks": 20,
            "percentage": 100,
        },
        {
            "student_name": "Ravi",
            "section": "C",
            "exam_term": "SE-1",
            "subject_name": "Math",
            "score": 40,
            "max_marks": 40,
            "percentage": 100,
        },
    ]

    grouped = AnalyticsService.grouped_subject_toppers_by_test(rows)

    assert grouped == [
        {
            "exam_term": "CYCLE TEST - I",
            "exam_display_name": "CYCLE TEST - I",
            "subjects": [
                {
                    "exam_term": "CYCLE TEST - I",
                    "exam_display_name": "CYCLE TEST - I",
                    "subject_name": "Math",
                    "subject_display_name": "Math",
                    "score": 20,
                    "max_marks": 20,
                    "percentage": 100,
                    "students": ["Asha (B)"],
                }
            ],
        },
        {
            "exam_term": "SE-1",
            "exam_display_name": "SE-1",
            "subjects": [
                {
                    "exam_term": "SE-1",
                    "exam_display_name": "SE-1",
                    "subject_name": "Math",
                    "subject_display_name": "Math",
                    "score": 40,
                    "max_marks": 40,
                    "percentage": 100,
                    "students": ["Ravi (C)"],
                }
            ],
        },
    ]


def test_filter_rows_supports_multiple_tests_and_subjects():
    rows = [
        {"exam_term": "CYCLE TEST - I", "subject_name": "Math"},
        {"exam_term": "CYCLE TEST - I", "subject_name": "Eng"},
        {"exam_term": "SE-1", "subject_name": "Math"},
        {"exam_term": "SE-1", "subject_name": "Sci"},
    ]

    filtered = AnalyticsService.filter_rows(
        rows,
        exam_terms=["CYCLE TEST - I", "SE-1"],
        subjects=["Math"],
    )

    assert filtered == [
        {"exam_term": "CYCLE TEST - I", "subject_name": "Math"},
        {"exam_term": "SE-1", "subject_name": "Math"},
    ]


def test_student_comparison_compares_selected_students_by_test_and_subject():
    rows = [
        {
            "student_name": "Asha",
            "section": "B",
            "exam_term": "CYCLE TEST - I",
            "exam_display_name": "Cycle Test 1",
            "subject_name": "Math",
            "subject_display_name": "Mathematics",
            "score": 18,
            "max_marks": 20,
            "percentage": 90,
        },
        {
            "student_name": "Ravi",
            "section": "C",
            "exam_term": "CYCLE TEST - I",
            "exam_display_name": "Cycle Test 1",
            "subject_name": "Math",
            "subject_display_name": "Mathematics",
            "score": 19,
            "max_marks": 20,
            "percentage": 95,
        },
        {
            "student_name": "Mira",
            "section": "D",
            "exam_term": "CYCLE TEST - I",
            "exam_display_name": "Cycle Test 1",
            "subject_name": "Math",
            "subject_display_name": "Mathematics",
            "score": 20,
            "max_marks": 20,
            "percentage": 100,
        },
    ]

    comparisons = AnalyticsService.student_comparison(
        rows,
        student_names=["Asha", "Ravi"],
        exam_terms=["CYCLE TEST - I"],
        subjects=["Math"],
    )

    assert comparisons == [
        {
            "exam_term": "CYCLE TEST - I",
            "exam_display_name": "Cycle Test 1",
            "subject_name": "Math",
            "subject_display_name": "Mathematics",
            "leader": {
                "status": "leading",
                "label": "Ravi leading",
                "percentage": 95,
            },
            "students": [
                {
                    "student_name": "Ravi",
                    "section": "C",
                    "score": 19,
                    "max_marks": 20,
                    "percentage": 95,
                    "rank": 2,
                },
                {
                    "student_name": "Asha",
                    "section": "B",
                    "score": 18,
                    "max_marks": 20,
                    "percentage": 90,
                    "rank": 3,
                },
            ],
        }
    ]
    assert AnalyticsService.grouped_student_comparison(comparisons) == [
        {
            "exam_term": "CYCLE TEST - I",
            "exam_display_name": "Cycle Test 1",
            "subjects": comparisons,
        }
    ]


def test_student_comparison_marks_equal_leaders():
    rows = [
        {
            "student_name": "Asha",
            "section": "B",
            "exam_term": "SE-1",
            "subject_name": "Math",
            "score": 38,
            "max_marks": 40,
            "percentage": 95,
        },
        {
            "student_name": "Ravi",
            "section": "C",
            "exam_term": "SE-1",
            "subject_name": "Math",
            "score": 38,
            "max_marks": 40,
            "percentage": 95,
        },
    ]

    comparisons = AnalyticsService.student_comparison(rows, ["Asha", "Ravi"])

    assert comparisons[0]["leader"] == {
        "status": "equal",
        "label": "All equal",
        "percentage": 95,
    }


def test_group_by_test_groups_items_under_exam_heading():
    grouped = AnalyticsService.group_by_test(
        [
            {
                "exam_term": "CYCLE TEST - I",
                "exam_display_name": "Cycle Test 1",
                "subject_name": "Math",
            },
            {
                "exam_term": "CYCLE TEST - I",
                "exam_display_name": "Cycle Test 1",
                "subject_name": "English",
            },
            {"exam_term": "SE-1", "exam_display_name": "SE 1", "subject_name": "Math"},
        ]
    )

    assert grouped == [
        {
            "exam_term": "CYCLE TEST - I",
            "exam_display_name": "Cycle Test 1",
            "items": [
                {
                    "exam_term": "CYCLE TEST - I",
                    "exam_display_name": "Cycle Test 1",
                    "subject_name": "Math",
                },
                {
                    "exam_term": "CYCLE TEST - I",
                    "exam_display_name": "Cycle Test 1",
                    "subject_name": "English",
                },
            ],
        },
        {
            "exam_term": "SE-1",
            "exam_display_name": "SE 1",
            "items": [
                {
                    "exam_term": "SE-1",
                    "exam_display_name": "SE 1",
                    "subject_name": "Math",
                }
            ],
        },
    ]
