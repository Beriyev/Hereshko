from pydantic import BaseModel
from app.core.normalization import SourceType

class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    notebook_id: str
    content: str
    position_type: SourceType
    page_number: int | None = None
    timestamp_seconds: float | None = None
    paragraph_index: int | None = None
    slide_number: int | None = None
    metadata: dict = {}