from enum import Enum
from pydantic import BaseModel
from datetime import datetime

class SourceType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    WEBSITE = "website"
    YOUTUBE = "youtube"

class Document(BaseModel):
    document_id: str
    notebook_id: str
    content: str
    source_type: SourceType
    source_identifier: str
    title: str
    ingested_at: datetime
    raw_metadata: dict