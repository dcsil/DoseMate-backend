import pytesseract
from PIL import Image
import io

# Optional Windows-specific setup
try:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
except Exception:
    pass  # Safe to ignore on non-Windows

def extract_text_from_image(file_bytes: bytes) -> str:
    """Run OCR on image bytes and return cleaned text."""
    image = Image.open(io.BytesIO(file_bytes)).convert("L")
    text = pytesseract.image_to_string(image)
    return " ".join(text.split())
