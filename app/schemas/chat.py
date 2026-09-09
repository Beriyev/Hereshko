from pydantic import BaseModel


class ChatRequest(BaseModel):
    notebook_id: str
    query: str
    session_id: str | None = None

class Citation(BaseModel):
    marker: int
    chunk_id: str
    content: str
    source_type: str
    source_name: str | None = None
    page_number: int | None = None
    paragraph_index: int | None = None
    slide_number: int | None = None
    timestamp_seconds: float | None = None
    source_url: str | None = None

class ChatResponse(BaseModel):
    answer: str
    sources: list[Citation]