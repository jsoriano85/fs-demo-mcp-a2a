from pathlib import Path

from docs.build_guide import build


def test_presenter_guide_is_a_pdf(tmp_path: Path) -> None:
    output = tmp_path / "guide.pdf"
    build(output)
    data = output.read_bytes()

    assert data.startswith(b"%PDF")
    assert len(data) > 10_000
