from app.core.ingestion.parsers import detect_kind, parse


def test_detect_kind_by_mime():
    assert detect_kind("application/pdf", "x") == "pdf"
    assert detect_kind("text/csv", "x") == "csv"
    assert detect_kind("text/html", "x") == "html"
    assert detect_kind("text/plain", "x") == "txt"


def test_detect_kind_by_extension_fallback():
    assert detect_kind("application/octet-stream", "notes.md") == "txt"
    assert detect_kind("", "page.HTM") == "html"
    assert detect_kind("", "mystery.xyz") is None


def test_parse_txt():
    parsed = parse(b"hello world\n\nsecond para", "text/plain", "a.txt")
    assert len(parsed.sections) == 1
    assert "hello world" in parsed.sections[0].text


def test_parse_csv_repeats_headers_and_groups_rows():
    rows = "name,status\n" + "\n".join(f"item{i},open" for i in range(25))
    parsed = parse(rows.encode(), "text/csv", "orders.csv")
    # 25 rows / 10 per section -> 3 sections
    assert len(parsed.sections) == 3
    # header names are repeated inside each row line so chunks stay self-describing
    assert "name: item0" in parsed.sections[0].text
    assert "status: open" in parsed.sections[0].text
    assert parsed.sections[0].meta["rows"] == "1-10"


def test_parse_html_strips_scripts():
    html = b"<html><head><title>T</title></head><body><p>Keep this.</p>"
    html += b"<script>alert('drop me')</script></body></html>"
    parsed = parse(html, "text/html", "p.html")
    text = " ".join(s.text for s in parsed.sections)
    assert "Keep this." in text
    assert "drop me" not in text
    assert parsed.sections[0].meta["title"] == "T"


def test_parse_unsupported_raises():
    try:
        parse(b"data", "application/zip", "a.zip")
    except ValueError as exc:
        assert "Unsupported" in str(exc)
    else:
        raise AssertionError("expected ValueError")
