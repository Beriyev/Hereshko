import re
import tempfile
from pathlib import Path

from app.core.normalization import Document
from app.storage.database import DATA_DIR

persist_dir = DATA_DIR / "persist"

def document_directory(document_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9-_]+",document_id):
        raise ValueError("Invalid Document ID")
    return persist_dir / document_id

def persist_document(document: Document) -> Path:
    directory = document_directory(document_id=document.document_id)
    directory.mkdir(parents=True,exist_ok=True)
    path = directory / "document.json"
    path.write_text(
        data=document.model_dump_json(indent=2),
        encoding="utf-8"
    )
    return path

def load_document(document_id: str) -> Document:
    directory = document_directory(document_id=document_id)
    path = Path(directory / "document.json")
    return Document.model_validate_json(path.read_text(encoding="utf-8"))

