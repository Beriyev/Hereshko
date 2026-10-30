from pydantic import BaseModel
from enum import Enum


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    id: int | None = None
    role: ChatRole
    content: str
