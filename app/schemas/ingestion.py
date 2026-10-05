from pydantic import BaseModel
from app.core.normalization import SourceType

class IngestRequest(BaseModel):
    notebook_id: str
    source_type: SourceType
    source_identifier: str

class IngestResponse(BaseModel):
    document_id: str
    status: str

class WebsiteIngestResponse(BaseModel):
    document_ids: list[str]
    status: str

class DocumentProfile(BaseModel):
    document_type: str
    title: str
    summary: str
    topics: list[str]
    keywords: list[str]
    entities: list[str]
    confidence: float