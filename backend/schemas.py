from typing import Literal

from pydantic import BaseModel, ConfigDict,Field


MAX_MESSAGE_CHARS = 4000


# CHAT
class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    reply:str
    model:str
    tokens_used: int

