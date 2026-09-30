"""Synthetic PDF fixtures built with PyMuPDF.

These builders produce small deterministic PDFs for portable CI tests. They
exercise representative documentary structures: multiple pages, headings,
paragraph lines, lists, images with captions, and vector-drawn tables. No
private clinical PDF is required.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

_BODY_SIZE = 11.0
_HEADING_SIZE = 16.0
_CAPTION_SIZE = 9.0

_PAGE_RECT = pymupdf.Rect(0, 0, 595, 842)


def _write_line(page: pymupdf.Page, text: str, point: pymupdf.Point, size: float) -> None:
    writer = pymupdf.TextWriter(page.rect)
    writer.append(point, text, font=pymupdf.Font("helv"), fontsize=size)
    writer.write_text(page)


def build_text_pdf(path: Path, pages: list[list[str]]) -> None:
    """Build a PDF whose pages contain the given lines at body size."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page(width=_PAGE_RECT.width, height=_PAGE_RECT.height)
        for index, line in enumerate(lines):
            _write_line(page, line, pymupdf.Point(72, 100 + index * 24), _BODY_SIZE)
    doc.save(str(path))
    doc.close()


def build_heading_pdf(path: Path) -> None:
    """Build a PDF with a large heading and two body paragraphs."""
    doc = pymupdf.open()
    page = doc.new_page(width=_PAGE_RECT.width, height=_PAGE_RECT.height)
    _write_line(page, "RECOMENDACIONES PARA EL DIAGNOSTICO", pymupdf.Point(72, 100), _HEADING_SIZE)
    _write_line(
        page,
        "Este es un parrafo de ejemplo con texto en minusculas.",
        pymupdf.Point(72, 140),
        _BODY_SIZE,
    )
    _write_line(page, "Segundo parrafo de contenido narrativo.", pymupdf.Point(72, 164), _BODY_SIZE)
    doc.save(str(path))
    doc.close()


def build_list_pdf(path: Path) -> None:
    """Build a PDF with bullet and numbered list items."""
    doc = pymupdf.open()
    page = doc.new_page(width=_PAGE_RECT.width, height=_PAGE_RECT.height)
    for index, line in enumerate(
        [
            "- primer elemento de lista",
            "- segundo elemento de lista",
            "1. primer elemento numerado",
            "2. segundo elemento numerado",
        ]
    ):
        _write_line(page, line, pymupdf.Point(72, 100 + index * 24), _BODY_SIZE)
    doc.save(str(path))
    doc.close()


def build_image_pdf(path: Path, caption: str = "Figura 1. Flujograma de manejo") -> None:
    """Build a PDF with one embedded image and a caption line below it."""
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 60, 60), False)
    pixmap.set_rect(pixmap.irect, (200, 120, 140))
    doc = pymupdf.open()
    page = doc.new_page(width=_PAGE_RECT.width, height=_PAGE_RECT.height)
    image_rect = pymupdf.Rect(72, 100, 272, 300)
    page.insert_image(image_rect, stream=pixmap.tobytes("png"))
    _write_line(page, caption, pymupdf.Point(72, 310), _CAPTION_SIZE)
    doc.save(str(path))
    doc.close()


def build_table_pdf(path: Path) -> None:
    """Build a PDF with one vector-drawn 2x2 table plus a paragraph below."""
    doc = pymupdf.open()
    page = doc.new_page(width=_PAGE_RECT.width, height=_PAGE_RECT.height)
    outer = pymupdf.Rect(72, 100, 400, 220)
    page.draw_rect(outer, color=(0, 0, 0), width=1)
    page.draw_line(pymupdf.Point(72, 160), pymupdf.Point(400, 160), color=(0, 0, 0), width=1)
    page.draw_line(pymupdf.Point(236, 100), pymupdf.Point(236, 220), color=(0, 0, 0), width=1)
    _write_line(page, "Medicamento", pymupdf.Point(80, 130), _BODY_SIZE)
    _write_line(page, "Dosis", pymupdf.Point(244, 130), _BODY_SIZE)
    _write_line(page, "Ceftriaxona", pymupdf.Point(80, 190), _BODY_SIZE)
    _write_line(page, "1 g", pymupdf.Point(244, 190), _BODY_SIZE)
    _write_line(
        page, "Parrafo posterior a la tabla con texto normal.", pymupdf.Point(72, 260), _BODY_SIZE
    )
    doc.save(str(path))
    doc.close()


def build_empty_page_pdf(path: Path) -> None:
    """Build a PDF with one page that has no text at all."""
    doc = pymupdf.open()
    doc.new_page(width=_PAGE_RECT.width, height=_PAGE_RECT.height)
    doc.save(str(path))
    doc.close()
