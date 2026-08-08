from pydantic import BaseModel
from app.core.normalization import SourceType

class IngestRequest(BaseModel):
    notebook_id: str
    source_type: SourceType
    source_identifier: str

class IngestResponse(BaseModel):
    document_id: str
    status: str