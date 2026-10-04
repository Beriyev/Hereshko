from pydantic import BaseModel
from datetime import datetime

class NotebookResponse(BaseModel):
    notebook_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    source_count: int

class NotebookTitleUpdate(BaseModel):
    title: str

class SourceResponse(BaseModel):
    document_id: str
    notebook_id: str
    title: str
    source_type: str
    source_identifier: str
    ingested_at: datetime
    metadata: dict

class SourceListResponse(BaseModel):
    sources: list[SourceResponse]

class SummaryResponse(BaseModel):
    title: str
    summary: str
    source_count: int
    updated_at: datetime

class GeneratedOverview(BaseModel):
    title: str
    summary: str
