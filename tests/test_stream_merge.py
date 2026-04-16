from ui.markdown import dedupe_stream_text, merge_stream_chunk


def test_delta_append():
    b = ""
    b = merge_stream_chunk(b, "Hel")
    b = merge_stream_chunk(b, "lo")
    assert b == "Hello"


def test_cumulative_replace():
    b = ""
    b = merge_stream_chunk(b, "Hello")
    b = merge_stream_chunk(b, "Hello world")
    assert b == "Hello world"


def test_duplicate_chunk_idempotent():
    b = "Hello"
    b = merge_stream_chunk(b, "Hello")
    assert b == "Hello"


def test_cumulative_longer_paragraph():
    b = ""
    b = merge_stream_chunk(b, "Line one")
    b = merge_stream_chunk(b, "Line one\n\nLine two")
    assert b == "Line one\n\nLine two"


def test_dedupe_repeated_lines():
    raw = "Hello\n" * 5 + "\nNext"
    assert dedupe_stream_text(raw).splitlines()[0] == "Hello"
    assert "Next" in dedupe_stream_text(raw)


def test_dedupe_repeated_paragraphs():
    p = "Same para"
    raw = "\n\n".join([p] * 4)
    out = dedupe_stream_text(raw)
    assert out.count("Same para") == 1


def test_dedupe_long_line_stutter():
    unit = "X" * 50
    raw = (unit + " ") * 5
    out = dedupe_stream_text(raw)
    assert unit in out
    assert raw.count("X") > out.count("X")
