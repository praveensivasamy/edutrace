import re
from collections import defaultdict
from datetime import date


class AnalyticsService:
    @staticmethod
    def summary(rows: list[dict]) -> dict:
        if not rows:
            return {
                "records": 0,
                "students": 0,
                "subjects": 0,
                "average_pct": 0,
                "highest_pct": 0,
                "lowest_pct": 0,
            }
        percentages = [r["percentage"] for r in rows if r.get("percentage") is not None]
        return {
            "records": len(rows),
            "students": len({r["student_name"] for r in rows}),
            "subjects": len({r["subject_name"] for r in rows}),
            "average_pct": round(sum(percentages) / len(percentages), 1) if percentages else 0,
            "highest_pct": max(percentages) if percentages else 0,
            "lowest_pct": min(percentages) if percentages else 0,
        }

    @staticmethod
    def subject_trend(rows: list[dict]) -> list[dict]:
        grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
        labels: dict[tuple[str, str], dict] = {}
        for row in rows:
            if row.get("percentage") is not None:
                grouped[(row["subject_name"], row["exam_term"])].append(row["percentage"])
                labels[(row["subject_name"], row["exam_term"])] = row

        trend = []
        for (subject, term), values in sorted(grouped.items()):
            trend.append(
                {
                    "label": f"{subject} - {term}",
                    "subject": subject,
                    "subject_display_name": labels[(subject, term)].get(
                        "subject_display_name", subject
                    ),
                    "exam_term": term,
                    "exam_display_name": labels[(subject, term)].get("exam_display_name", term),
                    "average_pct": round(sum(values) / len(values), 1),
                    "highest_pct": max(values),
                    "lowest_pct": min(values),
                }
            )
        return trend

    @staticmethod
    def student_rankings(rows: list[dict], limit: int = 12) -> list[dict]:
        grouped: dict[str, dict] = {}
        for row in rows:
            score = row.get("score")
            max_marks = row.get("max_marks")
            if score is None or not max_marks:
                continue

            key = row["student_name"]
            student = grouped.setdefault(
                key,
                {
                    "student_name": row["student_name"],
                    "class_name": row["class_name"],
                    "section": row["section"],
                    "score": 0,
                    "max_marks": 0,
                    "subjects": 0,
                },
            )
            student["score"] += score
            student["max_marks"] += max_marks
            student["subjects"] += 1

        rankings = []
        for student in grouped.values():
            percentage = (
                round((student["score"] / student["max_marks"]) * 100, 1)
                if student["max_marks"]
                else 0
            )
            rankings.append({**student, "percentage": percentage})

        return sorted(rankings, key=lambda item: item["percentage"], reverse=True)[:limit]

    @staticmethod
    def subject_summary(rows: list[dict]) -> list[dict]:
        grouped: dict[str, list[float]] = defaultdict(list)
        labels: dict[str, str] = {}
        for row in rows:
            labels[row["subject_name"]] = row.get("subject_display_name", row["subject_name"])
            if row.get("percentage") is not None:
                grouped[row["subject_name"]].append(row["percentage"])

        return [
            {
                "subject_name": subject,
                "subject_display_name": labels.get(subject, subject),
                "average_pct": round(sum(values) / len(values), 1),
                "highest_pct": max(values),
                "lowest_pct": min(values),
                "records": len(values),
            }
            for subject, values in sorted(grouped.items())
        ]

    @staticmethod
    def section_summary(rows: list[dict]) -> list[dict]:
        grouped: dict[str, list[float]] = defaultdict(list)
        students: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            section = row["section"]
            students[section].add(row["student_name"])
            if row.get("percentage") is not None:
                grouped[section].append(row["percentage"])

        return [
            {
                "section": section,
                "students": len(students[section]),
                "average_pct": round(sum(values) / len(values), 1) if values else 0,
            }
            for section, values in sorted(grouped.items())
        ]

    @staticmethod
    def subject_toppers_by_test(rows: list[dict]) -> list[dict]:
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows:
            if row.get("score") is not None and row.get("percentage") is not None:
                grouped[(row["exam_term"], row["subject_name"])].append(row)

        toppers = []
        for (exam_term, subject_name), group_rows in sorted(
            grouped.items(), key=lambda item: AnalyticsService._subject_test_sort_key(item[0])
        ):
            top_percentage = max(row["percentage"] for row in group_rows)
            top_rows = [row for row in group_rows if row["percentage"] == top_percentage]
            top_score = max(row["score"] for row in top_rows)
            max_marks = top_rows[0]["max_marks"]
            toppers.append(
                {
                    "exam_term": exam_term,
                    "exam_display_name": top_rows[0].get("exam_display_name", exam_term),
                    "subject_name": subject_name,
                    "subject_display_name": top_rows[0].get(
                        "subject_display_name", subject_name
                    ),
                    "score": top_score,
                    "max_marks": max_marks,
                    "percentage": top_percentage,
                    "students": sorted(
                        {
                            f"{row['student_name']} ({row['section']})"
                            for row in top_rows
                        }
                    ),
                }
            )
        return toppers

    @staticmethod
    def grouped_subject_toppers_by_test(rows: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for topper in AnalyticsService.subject_toppers_by_test(rows):
            grouped[topper["exam_term"]].append(topper)
        return [
            {
                "exam_term": exam_term,
                "exam_display_name": subjects[0].get("exam_display_name", exam_term),
                "subjects": subjects,
            }
            for exam_term, subjects in sorted(
                grouped.items(),
                key=lambda item: AnalyticsService._exam_sort_key(item[0]),
            )
        ]

    @staticmethod
    def student_vs_top_by_subject(
        rows: list[dict],
        student_query: str,
        top_n: int = 10,
        exam_order: list[str] | None = None,
    ) -> list[dict]:
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        normalized_query = student_query.strip().lower()

        for row in rows:
            if row.get("percentage") is None:
                continue
            grouped[(row["exam_term"], row["subject_name"])].append(row)

        comparisons = []
        for (exam_term, subject_name), group_rows in sorted(
            grouped.items(),
            key=lambda item: AnalyticsService._subject_test_sort_key(item[0], exam_order),
        ):
            ranked = sorted(
                group_rows,
                key=lambda row: (
                    row["percentage"],
                    row["score"] if row.get("score") is not None else -1,
                ),
                reverse=True,
            )
            top_students = [
                {
                    "rank": index + 1,
                    "student_name": row["student_name"],
                    "section": row["section"],
                    "score": row["score"],
                    "max_marks": row["max_marks"],
                    "percentage": row["percentage"],
                }
                for index, row in enumerate(ranked[:top_n])
            ]
            target = AnalyticsService._find_student_rank(ranked, normalized_query)
            comparisons.append(
                {
                    "exam_term": exam_term,
                    "exam_display_name": group_rows[0].get("exam_display_name", exam_term),
                    "subject_name": subject_name,
                    "subject_display_name": group_rows[0].get(
                        "subject_display_name", subject_name
                    ),
                    "target": target,
                    "top_students": top_students,
                    "top_average_pct": AnalyticsService._average(
                        row["percentage"] for row in ranked[:top_n]
                    ),
                    "highest_pct": ranked[0]["percentage"] if ranked else 0,
                }
            )
        return comparisons

    @staticmethod
    def student_rank_trend_by_subject(
        rows: list[dict], student_query: str, exam_order: list[str] | None = None
    ) -> list[dict]:
        grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        normalized_query = student_query.strip().lower()

        for row in rows:
            if row.get("percentage") is not None:
                grouped[row["subject_name"]][row["exam_term"]].append(row)

        trends = []
        for subject_name, tests in sorted(grouped.items()):
            points = []
            for exam_term, group_rows in sorted(tests.items()):
                ranked = sorted(
                    group_rows,
                    key=lambda row: (
                        row["percentage"],
                        row["score"] if row.get("score") is not None else -1,
                    ),
                    reverse=True,
                )
                target = AnalyticsService._find_student_rank(ranked, normalized_query)
                if target:
                    points.append(
                        {
                            "exam_term": exam_term,
                            "exam_display_name": group_rows[0].get(
                                "exam_display_name", exam_term
                            ),
                            "subject_display_name": group_rows[0].get(
                                "subject_display_name", subject_name
                            ),
                            "rank": target["rank"],
                            "percentage": target["percentage"],
                            "score": target["score"],
                            "max_marks": target["max_marks"],
                            "student_count": len(ranked),
                        }
                    )
            if points:
                sorted_points = AnalyticsService._sort_test_points(points, exam_order)
                for index, point in enumerate(sorted_points):
                    previous = sorted_points[index - 1] if index else None
                    point["rank_delta"] = previous["rank"] - point["rank"] if previous else 0
                    if not previous:
                        point["movement"] = "baseline"
                    elif point["rank"] < previous["rank"]:
                        point["movement"] = "improved"
                    elif point["rank"] > previous["rank"]:
                        point["movement"] = "dropped"
                    else:
                        point["movement"] = "same"
                trends.append(
                    {
                        "subject_name": subject_name,
                        "subject_display_name": sorted_points[0].get(
                            "subject_display_name", subject_name
                        ),
                        "points": sorted_points,
                    }
                )
        return trends

    @staticmethod
    def filter_rows(
        rows: list[dict],
        exam_terms: list[str] | None = None,
        subjects: list[str] | None = None,
    ) -> list[dict]:
        exam_filter = {value for value in (exam_terms or []) if value}
        subject_filter = {value for value in (subjects or []) if value}
        return [
            row
            for row in rows
            if (not exam_filter or row["exam_term"] in exam_filter)
            and (not subject_filter or row["subject_name"] in subject_filter)
        ]

    @staticmethod
    def student_comparison(
        rows: list[dict],
        student_names: list[str],
        exam_terms: list[str] | None = None,
        subjects: list[str] | None = None,
    ) -> list[dict]:
        selected_students = {value for value in student_names if value}
        if not selected_students:
            return []

        filtered_rows = AnalyticsService.filter_rows(rows, exam_terms, subjects)
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in filtered_rows:
            if row.get("percentage") is not None:
                grouped[(row["exam_term"], row["subject_name"])].append(row)

        comparisons = []
        for (exam_term, subject_name), group_rows in sorted(
            grouped.items(),
            key=lambda item: AnalyticsService._subject_test_sort_key(item[0]),
        ):
            ranked = sorted(
                group_rows,
                key=lambda row: (
                    row["percentage"],
                    row["score"] if row.get("score") is not None else -1,
                ),
                reverse=True,
            )
            rank_by_student = {row["student_name"]: index + 1 for index, row in enumerate(ranked)}
            selected_rows = [
                {
                    "student_name": row["student_name"],
                    "section": row["section"],
                    "score": row["score"],
                    "max_marks": row["max_marks"],
                    "percentage": row["percentage"],
                    "rank": rank_by_student[row["student_name"]],
                }
                for row in ranked
                if row["student_name"] in selected_students
            ]
            if selected_rows:
                comparisons.append(
                    {
                        "exam_term": exam_term,
                        "exam_display_name": group_rows[0].get("exam_display_name", exam_term),
                        "subject_name": subject_name,
                        "subject_display_name": group_rows[0].get(
                            "subject_display_name", subject_name
                        ),
                        "leader": AnalyticsService._comparison_leader(selected_rows),
                        "students": selected_rows,
                    }
                )
        return comparisons

    @staticmethod
    def grouped_student_comparison(comparisons: list[dict]) -> list[dict]:
        grouped: dict[str, dict] = {}
        for comparison in comparisons:
            group = grouped.setdefault(
                comparison["exam_term"],
                {
                    "exam_term": comparison["exam_term"],
                    "exam_display_name": comparison["exam_display_name"],
                    "subjects": [],
                },
            )
            group["subjects"].append(comparison)
        return list(grouped.values())

    @staticmethod
    def group_by_test(items: list[dict]) -> list[dict]:
        grouped: dict[str, dict] = {}
        for item in items:
            group = grouped.setdefault(
                item["exam_term"],
                {
                    "exam_term": item["exam_term"],
                    "exam_display_name": item.get("exam_display_name", item["exam_term"]),
                    "items": [],
                },
            )
            group["items"].append(item)
        return list(grouped.values())

    @staticmethod
    def student_options(rows: list[dict]) -> list[str]:
        return sorted({row["student_name"] for row in rows if row.get("student_name")})

    @staticmethod
    def analysis_options(rows: list[dict]) -> dict[str, list[str]]:
        return {
            "exam_terms": AnalyticsService.exam_term_order(rows),
            "subjects": sorted({row["subject_name"] for row in rows if row.get("subject_name")}),
            "exam_labels": {
                row["exam_term"]: row.get("exam_display_name", row["exam_term"])
                for row in rows
                if row.get("exam_term")
            },
            "subject_labels": {
                row["subject_name"]: row.get("subject_display_name", row["subject_name"])
                for row in rows
                if row.get("subject_name")
            },
        }

    @staticmethod
    def _sort_test_points(points: list[dict], exam_order: list[str] | None = None) -> list[dict]:
        return sorted(
            points,
            key=lambda point: AnalyticsService._exam_sort_key(point["exam_term"], exam_order),
        )

    @staticmethod
    def exam_term_order(rows: list[dict]) -> list[str]:
        dates_by_term: dict[str, date] = {}
        terms = {row["exam_term"] for row in rows if row.get("exam_term")}
        for row in rows:
            exam_term = row.get("exam_term")
            if not exam_term:
                continue
            parsed = AnalyticsService._parse_exam_start_date(row.get("exam_date") or "")
            if parsed and (exam_term not in dates_by_term or parsed < dates_by_term[exam_term]):
                dates_by_term[exam_term] = parsed
        return sorted(
            terms,
            key=lambda term: (
                dates_by_term.get(term) is None,
                dates_by_term.get(term) or date.max,
                AnalyticsService._exam_sort_key(term),
            ),
        )

    @staticmethod
    def _exam_sort_key(exam_term: str, exam_order: list[str] | None = None) -> tuple[int, str]:
        if exam_order and exam_term in exam_order:
            return exam_order.index(exam_term), exam_term
        normalized = exam_term.upper()
        if "CYCLE" in normalized:
            return 0, normalized
        if normalized.startswith("SE"):
            return 1, normalized
        return 2, normalized

    @staticmethod
    def _subject_test_sort_key(
        value: tuple[str, str], exam_order: list[str] | None = None
    ) -> tuple[int, str, str]:
        exam_term, subject_name = value
        exam_sort, normalized_exam = AnalyticsService._exam_sort_key(exam_term, exam_order)
        return exam_sort, normalized_exam, subject_name

    @staticmethod
    def _find_student_rank(ranked_rows: list[dict], normalized_query: str) -> dict | None:
        for index, row in enumerate(ranked_rows):
            if normalized_query in row["student_name"].lower():
                return {
                    "rank": index + 1,
                    "student_name": row["student_name"],
                    "section": row["section"],
                    "score": row["score"],
                    "max_marks": row["max_marks"],
                    "percentage": row["percentage"],
                }
        return None

    @staticmethod
    def _average(values) -> float:
        value_list = list(values)
        return round(sum(value_list) / len(value_list), 1) if value_list else 0

    @staticmethod
    def _comparison_leader(rows: list[dict]) -> dict:
        if not rows:
            return {"status": "none", "label": "No score", "percentage": None}
        highest = max(row["percentage"] for row in rows)
        leaders = [row["student_name"] for row in rows if row["percentage"] == highest]
        if len(leaders) == len(rows) and len(rows) > 1:
            return {"status": "equal", "label": "All equal", "percentage": highest}
        if len(leaders) > 1:
            return {
                "status": "equal",
                "label": f"Equal lead: {', '.join(leaders)}",
                "percentage": highest,
            }
        return {"status": "leading", "label": f"{leaders[0]} leading", "percentage": highest}

    @staticmethod
    def _parse_exam_start_date(value: str) -> date | None:
        match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", value)
        if not match:
            return None
        day, month, year = (int(part) for part in match.groups())
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None
