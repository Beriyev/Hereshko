from pydantic import BaseModel

class MindMapNode(BaseModel):
    id: str
    parent_id: str | None
    title: str
    summary: str

class MindMap(BaseModel):
    nodes: list[MindMapNode]

class MindMapRequest(BaseModel):
    document_id: str
