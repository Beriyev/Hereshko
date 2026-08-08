from pydantic import BaseModel
from datetime import datetime

class CreateNotebookRequest(BaseModel):
    title: str

class NotebookResponse(BaseModel):
    notebook_id: str
    title: str
    created_at: datetime