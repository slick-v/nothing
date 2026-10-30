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

# DOCUMENTS
class DocumentOut(BaseModel):
    id: int
    filename: str
    page_count: int
    characters: int
    chunks: int

class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    document_id: int
    question: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)

class SearchRequest(AskRequest):
    top_k: int = Field(default=4, ge=1, le=20)


class Source(BaseModel):
    page: int
    score: float   # 1 = same meaning, near 0 = unrelated
    content: str

class AskResponse(BaseModel):
    answer: str
    method: str   # "prompt" now, "rag" later
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    sources: list[Source] = []   # the chunks the answer was based on (RAG only)
