import logging
import time

import groq
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.routes.documents import get_document
from app.schemas import AskRequest, AskResponse, SearchRequest, Source
from app.services.llm import LLM_ERROR, answer_from_context
from app.services.rag import search

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ask"])


def require_ready(document: models.Document) -> None:
    if document.status == "processing":
        raise HTTPException(status_code=409, detail="This document is still being processed. Try again in a moment.")
    if document.status == "failed":
        raise HTTPException(status_code=409, detail=document.error)


def call_llm(context: str, question: str, document_id: int) -> tuple[str, int, int]:
    """Both methods go through here, so they get the same prompt, model and error handling."""
    try:
        return answer_from_context(context, question)
    except groq.APIStatusError as e:
        if e.status_code in (413, 429):
            logger.warning("Groq token or rate limit: %s", e.message)
            raise HTTPException(
                status_code=e.status_code,
                detail="This is over your Groq token limit. Wait a minute, or lower MAX_TOKENS.",
            )
        logger.exception("LLM call failed for document %s", document_id)
        raise HTTPException(status_code=502, detail=LLM_ERROR)
    except (groq.APIError, RuntimeError):
        logger.exception("LLM call failed for document %s", document_id)
        raise HTTPException(status_code=502, detail=LLM_ERROR)


def to_sources(hits: list[tuple[models.Chunk, float]]) -> list[Source]:
    return [
        Source(page=chunk.page, section=chunk.section, score=round(score, 3), content=chunk.content)
        for chunk, score in hits
    ]


@router.post("/search", response_model=list[Source])
def search_document(request: SearchRequest, db: Session = Depends(get_db)):
    """Retrieval only, no LLM: check that the right chunks come back."""
    document = get_document(db, request.document_id)
    require_ready(document)
    return to_sources(search(db, document.id, request.question, request.top_k))


@router.post("/ask/prompt", response_model=AskResponse)
def ask_prompt(request: AskRequest, db: Session = Depends(get_db)):
    """Baseline, no RAG: the whole document goes into the prompt on every question."""
    document = get_document(db, request.document_id)

    start = time.perf_counter()
    answer, input_tokens, output_tokens = call_llm(document.content, request.question, document.id)

    return AskResponse(
        answer=answer,
        method="prompt",
        model=settings.model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )


@router.post("/ask/rag", response_model=AskResponse)
def ask_rag(request: AskRequest, db: Session = Depends(get_db)):
    """RAG: only the chunks closest to the question go into the prompt."""
    document = get_document(db, request.document_id)
    require_ready(document)

    start = time.perf_counter()
    hits = search(db, document.id, request.question)

    context = "\n\n".join(f"[Page {chunk.page}] {chunk.section or ''}\n{chunk.content}" for chunk, _ in hits)
    answer, input_tokens, output_tokens = call_llm(context, request.question, document.id)

    return AskResponse(
        answer=answer,
        method="rag",
        model=settings.model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=int((time.perf_counter() - start) * 1000),
        sources=to_sources(hits),
    )
