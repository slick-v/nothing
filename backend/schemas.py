from typing import Literal

from pydantic import BaseModel, Field


MAX_MESSAGE_CHARS = 4000


# MESSAGE


# CHAT
class ChatRequest(BaseModel):
    message: str
    conversation_id: int


class chatResponse(BaseModel):

