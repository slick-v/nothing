import itertools
import json
import logging

import groq
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import SessionLocal, get_db
from app.schemas import ChatRequest, ChatResponse
from app.services.llm import LLM_ERROR, get_reply, stream_reply

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


def load_history(db: Session, conversation_id: int) -> list[dict]:
    """The last N messages of a conversation, oldest first."""
    recent = db.scalars(
        select(models.Message)
        .where(models.Message.conversation_id == conversation_id)
        .order_by(models.Message.id.desc())
        .limit(settings.max_history_messages)
    ).all()
    return [{"role": m.role, "content": m.content} for m in reversed(recent)]


def save_turn(db: Session, conversation_id: int | None, question: str, reply: str, tokens_used: int) -> int:
    """Save the question and the answer together; create the conversation if it's new."""
    if conversation_id is None:
        conversation = models.Conversation(title=question[:50])
        db.add(conversation)
        db.flush()
        conversation_id = conversation.id
    db.add_all([
        models.Message(conversation_id=conversation_id, role="user", content=question),
        models.Message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
            model=settings.model_name,
            tokens_used=tokens_used,
        ),
    ])
    db.commit()
    return conversation_id


def ndjson(event: dict) -> str:
    """One event per line: the browser splits on newlines and parses each line as JSON."""
    return json.dumps(event) + "\n"


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # 1. find the conversation, or start a new one
    if request.conversation_id is None:
        conversation = models.Conversation(title=request.message[:50])
        db.add(conversation)
        db.flush()   # sends the INSERT so conversation.id is filled in (not committed yet)
    else:
        conversation = db.get(models.Conversation, request.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # 2. load the history
    history = load_history(db, conversation.id)

    # 3. ask the LLM
    try:
        reply, tokens_used = get_reply(history + [{"role": "user", "content": request.message}])
    except (groq.APIError, RuntimeError):
        logger.exception("LLM call failed for conversation %s", conversation.id)
        db.rollback()   # nothing is saved, not even a new conversation
        raise HTTPException(status_code=502, detail=LLM_ERROR)

    # 4. save the question and the answer together, only after success
    save_turn(db, conversation.id, request.message, reply, tokens_used)

    return ChatResponse(
        conversation_id=conversation.id,
        reply=reply,
        model=settings.model_name,
        tokens_used=tokens_used,
    )


@router.post("/chat/stream")
def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    # 1. check the conversation and load its history
    history = []
    if request.conversation_id is not None:
        if db.get(models.Conversation, request.conversation_id) is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        history = load_history(db, request.conversation_id)

    events = stream_reply(history + [{"role": "user", "content": request.message}])

    # 2. pull the first piece now, so a Groq error becomes a real 502
    #    instead of a 200 with the error hidden inside the stream
    try:
        first = next(events)
    except groq.APIError:
        logger.exception("LLM stream failed to start")
        raise HTTPException(status_code=502, detail=LLM_ERROR)

    def generate():
        parts = []
        tokens_used = 0
        try:
            for event in itertools.chain([first], events):
                if event["type"] == "delta":
                    parts.append(event["text"])
                    yield ndjson(event)
                else:
                    tokens_used = event["tokens_used"]
        except groq.APIError:
            logger.exception("LLM stream broke mid-reply")
            yield ndjson({"type": "error", "detail": "The reply was cut off. Please try again."})
            return

        reply = "".join(parts)
        if not reply:
            logger.error("LLM stream returned an empty reply (MAX_TOKENS too low?)")
            yield ndjson({"type": "error", "detail": LLM_ERROR})
            return

        # 3. save only once the whole reply has arrived. This runs after the
        #    endpoint has returned, so it opens its own session instead of using `db`
        try:
            with SessionLocal() as save_db:
                conversation_id = save_turn(save_db, request.conversation_id, request.message, reply, tokens_used)
        except Exception:
            logger.exception("Could not save the streamed reply")
            yield ndjson({"type": "error", "detail": "The reply could not be saved."})
            return

        yield ndjson({
            "type": "done",
            "conversation_id": conversation_id,
            "model": settings.model_name,
            "tokens_used": tokens_used,
        })

    return StreamingResponse(generate(), media_type="application/x-ndjson")
