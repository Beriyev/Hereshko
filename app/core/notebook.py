from pydantic import BaseModel
from datetime import datetime

class Notebook(BaseModel):
    notebook_id: str
    user_id: str
    title: str
    created_at: datetime