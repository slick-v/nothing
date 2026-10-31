import io
import re
from collections import Counter

from pypdf import PdfReader
from pypdf.errors import PdfReadError

EDGE_LINES = 2   # headers and footers are in the first or last lines of a page

class PdfError(Exception):
    """The file can't be used. The message is safe to show the user."""



def _line_key(line:str) -> str:
    # digits are ignored, so "Page 3 of 10" and "Page 4 of 10" count as the same line

    return re.sub(r"\d+", "#", line.strip().lower())


def remove_repeated_lines(pages: list[str]) -> list[str]:
    """Remove headers and footers: lines at the edge of at least half the pages."""
    if len(pages) < 3:
        return pages

    page_lines = [[line for line in page.splitlines() if line.strip()] for page in pages]
    counts = Counter()
    for lines in page_lines:
        counts.update({_line_key(line) for line in lines[:EDGE_LINES] + lines[-EDGE_LINES:]})
    repeated = {key for key, count in counts.items() if count >= len(pages) / 2}

    cleaned = []
    for lines in page_lines:
        bottom = len(lines) - EDGE_LINES
        kept = [
            line for i, line in enumerate(lines)
            if not ((i < EDGE_LINES or i >= bottom) and _line_key(line) in repeated)
        ]
        cleaned.append("\n".join(kept))
    return cleaned
def extract_text(data: bytes) -> tuple[str, int]:
    """Return (the whole text with [Page N] markers, page count)."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError:
        raise PdfError("This file isn't a readable PDF, or it is password protected.")

    if not any(page.strip() for page in pages):
        raise PdfError("No text found. Scanned PDFs are images and would need OCR.")

    pages = remove_repeated_lines(pages)
    text = "\n\n".join(f"[Page {number}]\n{page}" for number, page in enumerate(pages, start=1))
    return text.replace("\x00", ""), len(pages)   # Postgres can't store NUL characters