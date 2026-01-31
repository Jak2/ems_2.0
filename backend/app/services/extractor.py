import io
from typing import Optional
import pdfplumber
try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None
    Image = None


def extract_text_from_bytes(data: bytes) -> str:
    """Extract text from a PDF file (bytes). Uses pdfplumber for a reliable text extraction.
    """
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
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
                    return ocr_text_all
            return text
    except Exception:
        # fallback: return empty string
        return ""
