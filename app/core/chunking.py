from pydantic import BaseModel
from app.core.normalization import SourceType

class ChunkPosition(BaseModel):
    position_type: SourceType
    page_number: int | None = None
    timestamp_seconds: float | None = None
    paragraph_index: int | None = None

class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    notebook_id: str
    content: str
    position: ChunkPosition
    metadata: dict