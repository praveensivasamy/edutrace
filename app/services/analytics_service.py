from collections import defaultdict


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
        for row in rows:
            if row.get("percentage") is not None:
                grouped[(row["subject_name"], row["exam_term"])].append(row["percentage"])

        trend = []
        for (subject, term), values in sorted(grouped.items()):
            trend.append(
                {
                    "label": f"{subject} - {term}",
                    "subject": subject,
                    "exam_term": term,
                    "average_pct": round(sum(values) / len(values), 1),
                    "highest_pct": max(values),
                    "lowest_pct": min(values),
                }
            )
        return trend
