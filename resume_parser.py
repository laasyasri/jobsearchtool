"""Parse resumes from PDF, DOCX, or plain text."""
import io
from pathlib import Path


def parse_resume(file_obj) -> str:
    """Parse resume from uploaded file object (Streamlit UploadedFile) or path."""
    if file_obj is None:
        return ""

    # Handle Streamlit UploadedFile or raw bytes
    if hasattr(file_obj, "name"):
        name = file_obj.name.lower()
        data = file_obj.read()
    elif isinstance(file_obj, (str, Path)):
        path = Path(file_obj)
        name = path.name.lower()
        data = path.read_bytes()
    else:
        return ""

    if name.endswith(".pdf"):
        return _parse_pdf(data)
    elif name.endswith(".docx"):
        return _parse_docx(data)
    elif name.endswith(".txt") or name.endswith(".md"):
        return data.decode("utf-8", errors="ignore")
    else:
        # Try as plain text
        return data.decode("utf-8", errors="ignore")


def _parse_pdf(data: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages).strip()
    except Exception as e:
        return f"[PDF parse error: {e}]"


def _parse_docx(data: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # Also extract tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text.strip())
        return "\n".join(paragraphs).strip()
    except Exception as e:
        return f"[DOCX parse error: {e}]"
