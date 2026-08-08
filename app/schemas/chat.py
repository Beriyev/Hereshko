from pydantic import BaseModel


class ChatRequest(BaseModel):
    notebook_id: str
    query: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[str]