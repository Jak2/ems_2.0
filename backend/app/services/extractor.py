import io
import re
from typing import Optional
import pdfplumber
try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None
    Image = None


def normalize_text(text: str) -> str:
    """Normalize extracted text to match natural typing patterns.

    Fixes common PDF extraction issues:
    - Excessive whitespace and line breaks
    - Inconsistent spacing
    - Special characters
    """
    if not text:
        return ""

    # Replace common special characters with standard equivalents
    text = text.replace('\u2019', "'")  # Right single quote
    text = text.replace('\u2018', "'")  # Left single quote
    text = text.replace('\u201c', '"')  # Left double quote
    text = text.replace('\u201d', '"')  # Right double quote
    text = text.replace('\u2013', '-')  # En dash
    text = text.replace('\u2014', '-')  # Em dash
    text = text.replace('\u2022', '-')  # Bullet point
    text = text.replace('\u00a0', ' ')  # Non-breaking space
    text = text.replace('\u200b', '')   # Zero-width space
    text = text.replace('\uf0b7', '-')  # Wingdings bullet

    # Normalize multiple spaces to single space
    text = re.sub(r' +', ' ', text)

    # Normalize multiple newlines to at most 2 (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    # Remove empty lines at start and end
    text = text.strip()

    return text


def extract_text_from_bytes(data: bytes) -> str:
    """Extract text from a PDF file (bytes). Uses pdfplumber for a reliable text extraction.

    The extracted text is normalized to match what a user would naturally type,
    fixing common PDF extraction issues like excessive whitespace, special characters,
    and layout artifacts.
    """
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = []
            for p in pdf.pages:
                # Extract text with custom settings for better results
                page_text = p.extract_text(
                    x_tolerance=3,
                    y_tolerance=3,
                    layout=False,  # Don't try to preserve layout - it can cause issues
                    x_density=7.25,
                    y_density=13
                ) or ""
                pages.append(page_text)

            text = "\n\n".join(pages)

            # If extraction produced no text, attempt OCR fallback (if pytesseract is available)
            if (not text or text.strip() == "") and pytesseract:
                ocr_pages = []
                for p in pdf.pages:
                    try:
                        # pdfplumber Page.to_image returns an object with a PIL Image at .original
                        imgobj = p.to_image(resolution=150)
                        pil_img = getattr(imgobj, "original", None)
                        if pil_img is None and Image:
                            # fallback: convert page bbox to image via crop/convert (best-effort)
                            pil_img = imgobj.render()
                        if pil_img is not None:
                            ocr_text = pytesseract.image_to_string(pil_img)
                            ocr_pages.append(ocr_text)
                    except Exception:
                        continue
                ocr_text_all = "\n\n".join(ocr_pages)
                # if OCR succeeded for any pages, prefer OCR text
                if ocr_text_all.strip():
                    text = ocr_text_all

            # Normalize the extracted text to match natural typing patterns
            return normalize_text(text)
    except Exception:
        # fallback: return empty string
        return ""
