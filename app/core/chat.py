from pydantic import BaseModel
from datetime import datetime

from enum import Enum


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str


class Conversation(BaseModel):
    session_id: str
    notebook_id: str
    created_at: datetime
    messages: list[ChatMessage] = []