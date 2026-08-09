from app.core.normalization import Document, SourceType
import uuid
from pathlib import Path
from datetime import datetime, timezone
from app.core.exceptions import IngestionError
import pdfplumber

def extract_pdf(file_path: Path, notebook_id: str) -> Document:
    content = ""
    pages_count = 0
    try:
        with pdfplumber.open(file_path) as pdf:
            pages_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    content = content + text + "\n"
    except Exception as e:
        raise IngestionError(f"Failed to read PDF file: {e}") from e
    if not content.strip():
        raise IngestionError("No extractable text found in PDF (may be a scanned/image-only document)")
    document = Document(
        document_id = str(uuid.uuid4()),
        notebook_id = notebook_id,
        content = content,
        source_type = SourceType.PDF,
        source_identifier = file_path.name,
        title = file_path.stem,
        ingested_at = datetime.now(timezone.utc),
        raw_metadata = {
        "original_filename": file_path.name,
        "file_size_bytes": file_path.stat().st_size,
        "pages_count": pages_count
        }
    )
    return document