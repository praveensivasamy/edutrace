import io
from zipfile import ZipFile

from app.services.parse_service import ParseService


def test_parse_csv_upload_extracts_mark_candidates():
    content = b"student_name,subject_name,exam_term,score,max_marks\nAsha,Math,T1,18,20\n"

    status, candidates, error = ParseService.parse_upload("marks.csv", content)

    assert status == "needs_review"
    assert error is None
    assert candidates == [
        {
            "academic_year": "2026-2027",
            "class_name": "X",
            "section": "B",
            "exam_term": "T1",
            "exam_date": None,
            "subject_name": "Math",
            "student_name": "Asha",
            "roll_no": None,
            "gender": None,
            "score": 18.0,
            "max_marks": 20.0,
            "absent_flag": "N",
            "remarks": None,
            "source_upload_id": None,
        }
    ]


def test_parse_image_upload_waits_for_visual_parser():
    status, candidates, error = ParseService.parse_upload("screen.png", b"image")

    assert status == "pending"
    assert candidates == []
    assert "OCR/AI" in error


def test_parse_matrix_csv_expands_subject_columns():
    content = (
        b"SPRINGDAYS SENIOR SECONDARY SCHOOL,,,,,,\n"
        b"Overall Consolidated Mark list (2026-27),,,,,,\n"
        b"CYCLE TEST - I,,,,,,\n"
        b"STD. X ,,,,,,\n"
        b"DATE HELD : 06.04.26 to 27.04.26,,,,,,\n"
        b"S.NO,NAMES,SEC,LANG,Eng,Mat ,SE 1 Eng,TOTAL,%,RANK\n"
        b",,,,20,20,40,80,,\n"
        b"1,BHAVISHYA A N,D,T,19.0,20.0,38.5,77.5,96.9,1\n"
    )

    status, candidates, error = ParseService.parse_upload("matrix.csv", content)

    assert status == "needs_review"
    assert error is None
    assert len(candidates) == 3
    assert candidates[0]["student_name"] == "BHAVISHYA A N"
    assert candidates[0]["class_name"] == "X"
    assert candidates[0]["section"] == "D"
    assert candidates[0]["exam_term"] == "CYCLE TEST - I"
    assert candidates[0]["exam_date"] == "06.04.26 to 27.04.26"
    assert candidates[0]["subject_name"] == "Eng"
    assert candidates[0]["score"] == 19
    assert candidates[0]["max_marks"] == 20
    assert candidates[2]["exam_term"] == "SE-1"
    assert candidates[2]["subject_name"] == "Eng"
    assert candidates[2]["max_marks"] == 40


def test_parse_matrix_csv_without_max_row_uses_inferred_max_marks():
    content = (
        b"S.NO,NAMES,SEC,LANG,Eng,Mat ,SE 1 Eng,TOTAL,%,RANK\n"
        b"1,BHAVISHYA A N,D,T,19.0,20.0,38.5,77.5,96.9,1\n"
    )

    _, candidates, _ = ParseService.parse_upload("matrix.csv", content)

    assert candidates[0]["score"] == 19
    assert candidates[0]["max_marks"] == 20
    assert candidates[2]["score"] == 38.5
    assert candidates[2]["max_marks"] == 40


def test_parse_xlsx_consolidated_workbook():
    workbook = _minimal_xlsx(
        [
            ["SPRINGDAYS SENIOR SECONDARY SCHOOL", "", "", "", "", "", ""],
            ["Overall Consolidated Mark list (2026-27)", "", "", "", "", "", ""],
            ["CYCLE TEST - I", "", "", "", "", "", ""],
            ["STD. X ", "", "", "", "", "", ""],
            ["DATE HELD : 06.04.26 to 27.04.26", "", "", "", "", "", ""],
            ["S.NO", "NAMES", "SEC", "LANG", "Eng", "Mat ", "SE 1 Eng"],
            ["", "", "", "", "20", "20", "40"],
            ["1", "BHAVISHYA A N", "D", "T", "19", "20", "38.5"],
        ]
    )

    status, candidates, error = ParseService.parse_upload("marks.xlsx", workbook)

    assert status == "needs_review"
    assert error is None
    assert len(candidates) == 3
    assert candidates[0]["student_name"] == "BHAVISHYA A N"
    assert candidates[0]["subject_name"] == "Eng"
    assert candidates[0]["score"] == 19
    assert candidates[0]["max_marks"] == 20
    assert candidates[0]["class_name"] == "X"
    assert candidates[0]["section"] == "D"
    assert candidates[0]["exam_date"] == "06.04.26 to 27.04.26"
    assert candidates[2]["exam_term"] == "SE-1"
    assert candidates[2]["max_marks"] == 40


def _minimal_xlsx(rows: list[list[str]]) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w") as workbook:
        workbook.writestr("[Content_Types].xml", "")
        workbook.writestr("xl/workbook.xml", "")
        workbook.writestr("xl/worksheets/sheet1.xml", _sheet_xml(rows))
    return output.getvalue()


def _sheet_xml(rows: list[list[str]]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row):
            reference = f"{_column_name(column_index)}{row_index}"
            cells.append(
                f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        "</worksheet>"
    )


def _column_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name
