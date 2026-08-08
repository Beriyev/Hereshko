from pydantic import BaseModel
from datetime import datetime

class User(BaseModel):
    user_id: str
    email: str
    created_at: datetime
