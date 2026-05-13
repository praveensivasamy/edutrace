import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from app.core.constants import DEFAULT_ACADEMIC_YEAR, DEFAULT_CLASS_NAME, DEFAULT_SECTION
from app.schemas.marks import MarkCreate

SPREADSHEET_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


class ParseService:
    CSV_EXTENSIONS = {".csv", ".txt"}
    XLSX_EXTENSIONS = {".xlsx"}
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    MATRIX_META_COLUMNS = {"sno", "names", "name", "sec", "lang", "total", "%", "rank"}

    @classmethod
    def parse_upload(
        cls, file_name: str, content: bytes
    ) -> tuple[str, list[dict[str, Any]], str | None]:
        extension = Path(file_name).suffix.lower()
        if extension in cls.CSV_EXTENSIONS:
            return cls._parse_csv(content)
        if extension in cls.XLSX_EXTENSIONS:
            return cls._parse_xlsx(content)
        if extension in cls.IMAGE_EXTENSIONS:
            return (
                "pending",
                [],
                "Screenshot uploaded. Configure OCR/AI parsing before auto-extraction.",
            )
        return "unsupported", [], f"Unsupported file type: {extension or 'unknown'}"

    @staticmethod
    def to_json(candidates: list[dict[str, Any]]) -> str:
        return json.dumps(candidates)

    @staticmethod
    def from_json(value: str | None) -> list[dict[str, Any]]:
        if not value:
            return []
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []

    @classmethod
    def _parse_csv(cls, content: bytes) -> tuple[str, list[dict[str, Any]], str | None]:
        text = content.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
        matrix_header_index = cls._find_matrix_header_index(rows)
        if matrix_header_index is not None:
            return "needs_review", cls._parse_matrix_rows(rows, matrix_header_index), None

        reader = csv.DictReader(io.StringIO(text))
        candidates = [cls._row_to_candidate(row) for row in reader if row]
        return "needs_review", candidates, None

    @classmethod
    def _parse_xlsx(cls, content: bytes) -> tuple[str, list[dict[str, Any]], str | None]:
        rows = cls._xlsx_rows(content)
        matrix_header_index = cls._find_matrix_header_index(rows)
        if matrix_header_index is None:
            return "unsupported", [], "No consolidated marks table found in workbook."
        return "needs_review", cls._parse_matrix_rows(rows, matrix_header_index), None

    @classmethod
    def _xlsx_rows(cls, content: bytes) -> list[list[str]]:
        with ZipFile(io.BytesIO(content)) as workbook:
            shared_strings = cls._xlsx_shared_strings(workbook)
            sheet_path = cls._first_sheet_path(workbook)
            sheet = ET.fromstring(workbook.read(sheet_path))

        rows = []
        for row in sheet.findall("m:sheetData/m:row", SPREADSHEET_NS):
            values = []
            for cell in row.findall("m:c", SPREADSHEET_NS):
                index = cls._xlsx_column_index(cell.attrib.get("r", "A1"))
                while len(values) <= index:
                    values.append("")
                values[index] = cls._xlsx_cell_value(cell, shared_strings)
            rows.append(values)
        return rows

    @staticmethod
    def _xlsx_shared_strings(workbook: ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in workbook.namelist():
            return []
        root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
        return [
            "".join(text.text or "" for text in item.findall(".//m:t", SPREADSHEET_NS))
            for item in root.findall("m:si", SPREADSHEET_NS)
        ]

    @staticmethod
    def _first_sheet_path(workbook: ZipFile) -> str:
        sheet_names = sorted(
            name
            for name in workbook.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        if not sheet_names:
            raise ValueError("Workbook has no worksheets.")
        return sheet_names[0]

    @classmethod
    def _xlsx_cell_value(cls, cell: ET.Element, shared_strings: list[str]) -> str:
        if cell.attrib.get("t") == "inlineStr":
            return "".join(
                text.text or "" for text in cell.findall(".//m:t", SPREADSHEET_NS)
            ).strip()

        value = cell.find("m:v", SPREADSHEET_NS)
        if value is None or value.text is None:
            return ""
        if cell.attrib.get("t") == "s":
            return shared_strings[int(value.text)].strip()
        return value.text.strip()

    @staticmethod
    def _xlsx_column_index(reference: str) -> int:
        column = re.sub(r"[^A-Z]", "", reference.upper())
        index = 0
        for char in column:
            index = index * 26 + ord(char) - 64
        return index - 1

    @classmethod
    def _find_matrix_header_index(cls, rows: list[list[str]]) -> int | None:
        for index, row in enumerate(rows):
            normalized = {cls._normalize_header(value) for value in row}
            if {"sno", "names"}.issubset(normalized):
                return index
        return None

    @classmethod
    def _parse_matrix_rows(cls, rows: list[list[str]], header_index: int) -> list[dict[str, Any]]:
        headers = rows[header_index]
        max_marks = cls._matrix_max_marks(headers, rows, header_index)
        defaults = cls._matrix_defaults(rows[:header_index])
        columns = cls._matrix_subject_columns(headers)
        candidates = []

        for row in rows[header_index + 1 :]:
            if not cls._is_student_matrix_row(headers, row):
                continue
            student_name = cls._matrix_value(headers, row, "names").strip()
            section = cls._matrix_value(headers, row, "sec").strip() or defaults["section"]
            for column_index, header in columns:
                score = cls._float_or_none(cls._cell(row, column_index))
                if score is None:
                    continue
                exam_term, subject_name = cls._matrix_subject(header, defaults["exam_term"])
                mark = MarkCreate(
                    academic_year=defaults["academic_year"],
                    class_name=defaults["class_name"],
                    section=section,
                    exam_term=exam_term,
                    exam_date=defaults["exam_date"],
                    subject_name=subject_name,
                    student_name=student_name,
                    score=score,
                    max_marks=max_marks.get(column_index, cls._infer_max_marks(header)),
                )
                candidates.append(mark.model_dump())

        return candidates

    @classmethod
    def _matrix_subject_columns(cls, headers: list[str]) -> list[tuple[int, str]]:
        columns = []
        for index, header in enumerate(headers):
            normalized = cls._normalize_header(header)
            if header.strip() and normalized not in cls.MATRIX_META_COLUMNS:
                columns.append((index, header.strip()))
        return columns

    @classmethod
    def _matrix_max_marks(
        cls, headers: list[str], rows: list[list[str]], header_index: int
    ) -> dict[int, float]:
        # In the consolidated report, the row immediately after the header carries max marks.
        # If that row is already a student row, fall back to subject-name based inference.
        if header_index + 1 >= len(rows):
            return {}
        max_row = rows[header_index + 1]
        if cls._is_student_matrix_row(headers, max_row):
            return {
                index: cls._infer_max_marks(header)
                for index, header in cls._matrix_subject_columns(headers)
            }
        values = {}
        for index, header in cls._matrix_subject_columns(headers):
            value = cls._float_or_none(cls._cell(max_row, index))
            if value is not None:
                values[index] = value
            else:
                values[index] = cls._infer_max_marks(header)
        return values

    @classmethod
    def _matrix_defaults(cls, preamble: list[list[str]]) -> dict[str, str | None]:
        # Expected metadata rows:
        # 1 school, 2 report/year, 3 test name, 4 standard, 5 date range.
        lines = [" ".join(cell.strip() for cell in row if cell.strip()) for row in preamble]
        text = " ".join(lines)
        return {
            "academic_year": cls._extract_academic_year(text) or DEFAULT_ACADEMIC_YEAR,
            "class_name": cls._extract_class_name(text) or DEFAULT_CLASS_NAME,
            "section": DEFAULT_SECTION,
            "exam_term": cls._extract_exam_term(lines) or "Uploaded marks",
            "exam_date": cls._extract_exam_date(text),
        }

    @classmethod
    def _is_student_matrix_row(cls, headers: list[str], row: list[str]) -> bool:
        student_name = cls._matrix_value(headers, row, "names").strip()
        serial = cls._matrix_value(headers, row, "sno").strip()
        return bool(student_name and serial.isdigit())

    @classmethod
    def _matrix_value(cls, headers: list[str], row: list[str], name: str) -> str:
        for index, header in enumerate(headers):
            if cls._normalize_header(header) == name:
                return cls._cell(row, index)
        return ""

    @staticmethod
    def _matrix_subject(header: str, default_exam_term: str) -> tuple[str, str]:
        normalized = " ".join(header.split())
        match = re.match(r"^(SE\s*\d+)\s+(.+)$", normalized, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper().replace(" ", "-"), match.group(2).strip()
        return default_exam_term, normalized

    @staticmethod
    def _infer_max_marks(header: str) -> float:
        return 40.0 if re.match(r"^\s*SE\s*\d+", header, flags=re.IGNORECASE) else 20.0

    @staticmethod
    def _extract_academic_year(text: str) -> str | None:
        match = re.search(r"20\d{2}\s*[-/]\s*\d{2,4}", text)
        return match.group(0).replace(" ", "") if match else None

    @staticmethod
    def _extract_class_name(text: str) -> str | None:
        match = re.search(r"\bSTD\.?\s+([A-Z0-9]+)\b", text, flags=re.IGNORECASE)
        return match.group(1).upper() if match else None

    @staticmethod
    def _extract_exam_term(lines: list[str]) -> str | None:
        return next(
            (line for line in lines if "TEST" in line.upper() or "EXAM" in line.upper()),
            None,
        )

    @staticmethod
    def _extract_exam_date(text: str) -> str | None:
        match = re.search(
            r"\b\d{2}\.\d{2}\.\d{2,4}(?:\s+to\s+\d{2}\.\d{2}\.\d{2,4})?\b",
            text,
            flags=re.IGNORECASE,
        )
        return match.group(0) if match else None

    @staticmethod
    def _cell(row: list[str], index: int) -> str:
        return row[index].strip() if index < len(row) else ""

    @staticmethod
    def _normalize_header(value: str) -> str:
        if value.strip() == "%":
            return "%"
        return re.sub(r"[^a-z0-9]", "", value.lower())

    @staticmethod
    def _row_to_candidate(row: dict[str, str | None]) -> dict[str, Any]:
        normalized = {str(key).strip().lower(): (value or "").strip() for key, value in row.items()}

        def first(*names: str, default: str = "") -> str:
            return next((normalized[name] for name in names if normalized.get(name)), default)

        mark = MarkCreate(
            academic_year=first("academic_year", "academic year", default=DEFAULT_ACADEMIC_YEAR),
            class_name=first("class_name", "class", default=DEFAULT_CLASS_NAME),
            section=first("section", default=DEFAULT_SECTION),
            exam_term=first("exam_term", "term", "exam"),
            exam_date=first("exam_date", "date") or None,
            subject_name=first("subject_name", "subject"),
            student_name=first("student_name", "student", "name"),
            score=ParseService._float_or_none(first("score", "marks", "mark")),
            max_marks=ParseService._float_or_default(first("max_marks", "max", "total"), 100),
            absent_flag=first("absent_flag", "absent", default="N"),
            remarks=first("remarks", "remark") or None,
        )
        return mark.model_dump()

    @staticmethod
    def _float_or_none(value: str) -> float | None:
        return float(value) if value else None

    @staticmethod
    def _float_or_default(value: str, default: float) -> float:
        return float(value) if value else default
