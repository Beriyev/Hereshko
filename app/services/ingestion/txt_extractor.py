
from app.core.normalization import Document, SourceType
import uuid
from pathlib import Path
from datetime import datetime, timezone
from app.core.exceptions import IngestionError


def extract_txt(file_path: Path, notebook_id: str) -> Document:
    try:
        with open(file_path,'r',encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        raise IngestionError(f"Failed to read TXT file: {e}") from e
        

    document = Document(
        document_id = str(uuid.uuid4()),
        notebook_id = notebook_id,
        content = content,
        source_type = SourceType.TXT,
        source_identifier = file_path.name,
        title = file_path.stem,
        ingested_at = datetime.now(timezone.utc),
        raw_metadata = {
        "original_filename": file_path.name,
        "file_size_bytes": file_path.stat().st_size,
        }
    )
    return document
