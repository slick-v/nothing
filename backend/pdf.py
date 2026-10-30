import io


from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfError(Exception):
    """The file can't be used. The message is safe to show the user."""


def extract_text(data:bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError:
        raise PdfError("This file isn't a readable PDF, or it is password protected.")


    if not any(page.strip() for page in pages):
        raise PdfError("No text found. Scanned PDFs are images and would need OCR.")

    text = "\n\n".join(f"[Page {number}]\n{page}" for number, page in enumerate(pages, start=1))
    return text.replace("\x00", ""), len(pages) 