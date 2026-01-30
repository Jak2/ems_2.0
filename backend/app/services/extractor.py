import io
from typing import Optional
import pdfplumber


def extract_text_from_bytes(data: bytes) -> str:
    """Extract text from a PDF file (bytes). Uses pdfplumber for a reliable text extraction.
    """
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n\n".join(pages)
            return text
    except Exception:
        # fallback: return empty string
        return ""
