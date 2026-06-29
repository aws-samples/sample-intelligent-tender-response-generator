import fitz
import re

from io import BytesIO
from pypdf import PdfReader


def normalize_text(text: str) -> str:
    """
    Normalization geared for tender PDFs:
    - collapse whitespace
    - remove repeated hyphenation artifacts (optional)
    - keep accents (Spanish) but you can strip if you want
    """

    if not text:
        return ""

    # Join hyphenated line breaks: "adminis-\ntrativas" -> "administrativas"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Normalize newlines/spaces
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_page_count(pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    return str(len(reader.pages))


def extract_text_and_page_count(pdf_bytes: bytes, n_pages: int):
    """
    Extracts text from up to N pages (PyMuPDF).
    Returns: (combined_text, total_pages_in_pdf, extracted_page_indices_0based)
    """

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        total = doc.page_count
        page_indexes = list(range(min(total, n_pages)))
        chunks = []

        for idx in page_indexes:
            page = doc.load_page(idx)
            txt = page.get_text("text") or ""
            txt = normalize_text(txt)

            if txt:
                chunks.append(f"\n\n[Page {idx + 1}/{total}]\n{txt}")

    return "\n".join(chunks).strip(), total
