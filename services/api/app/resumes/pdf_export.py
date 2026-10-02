"""Plain, extractable Resume Studio PDFs using the existing pypdf dependency."""
from __future__ import annotations

import io
import textwrap
import unicodedata
from dataclasses import dataclass

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 54
FONT_SIZE = 10
LINE_HEIGHT = 14
LINE_COLUMNS = (PAGE_WIDTH - 2 * MARGIN) // (FONT_SIZE * 0.6)
LINES_PER_PAGE = (PAGE_HEIGHT - 2 * MARGIN) // LINE_HEIGHT


class UnsupportedPdfText(ValueError):
    """Text cannot be rendered faithfully with the built-in PDF font."""


@dataclass(frozen=True)
class ResumePdf:
    content: bytes
    page_count: int


def export_resume_pdf(text: str) -> ResumePdf:
    """Wrap and paginate all text at readable size; never shrink or truncate it.

    Courier's fixed character width makes fitting deterministic. WinAnsi supports
    Latin text and common punctuation. Reject other glyphs explicitly instead of
    replacing essential candidate information with missing-glyph boxes.
    """
    if any(unicodedata.category(char).startswith("C") and char not in "\n\r\t" for char in text):
        raise UnsupportedPdfText("PDF export cannot render hidden control characters")
    try:
        text.encode("cp1252")
    except UnicodeEncodeError as exc:
        raise UnsupportedPdfText("PDF export does not support all characters in this resume") from exc

    lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4).split("\n"):
        lines.extend(textwrap.wrap(
            line, width=int(LINE_COLUMNS), drop_whitespace=False,
            replace_whitespace=False, break_on_hyphens=False,
        ) or [""])

    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Courier"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    }))
    for start in range(0, len(lines), LINES_PER_PAGE):
        page = writer.add_blank_page(PAGE_WIDTH, PAGE_HEIGHT)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        })
        commands = [f"BT /F1 {FONT_SIZE} Tf {LINE_HEIGHT} TL {MARGIN} {PAGE_HEIGHT - MARGIN} Td"]
        for index, line in enumerate(lines[start:start + LINES_PER_PAGE]):
            if index:
                commands.append("T*")
            # Hex strings preserve literal candidate text without PDF operators
            # interpreting parentheses, slashes, or other content as instructions.
            commands.append(f"<{line.encode('cp1252').hex()}> Tj")
        commands.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return ResumePdf(content=output.getvalue(), page_count=len(writer.pages))
