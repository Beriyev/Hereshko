from app.core.chat import ChatMessage, ChatRole, Conversation
import threading
from datetime import datetime, timezone

class ConversationStore:
    def __init__(self):
        self.conversations: dict[str, Conversation] = {}
        self.lock = threading.Lock()

    def get_or_create(self, session_id: str, notebook_id: str) -> Conversation:
        with self.lock:
            conv = self.conversations.get(session_id)
            if conv is None:
                conv = Conversation(
                    session_id=session_id,
                    notebook_id=notebook_id,
                    created_at=datetime.now(timezone.utc)
                )
                self.conversations[session_id] = conv
            return conv

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        with self.lock:
            conv = self.conversations.get(session_id)
            if conv is None:
                return
            conv.messages.append(ChatMessage(role=ChatRole.USER,content=user_msg))
            conv.messages.append(ChatMessage(role=ChatRole.ASSISTANT,content=assistant_msg))

    def get_recent(self, session_id: str, n: int) -> list[ChatMessage]:
        with self.lock:
            conv = self.conversations.get(session_id)
            if conv is None:
                return []
            return conv.messages[-n:]