import itertools
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
import groq

from fastapi import BackgroundTasks,Depends,FastAPI, File,HTTPException,UploadFile
from fastapi.responses import FileResponse, JSONResponse,StreamingResponse
from sqlalchemy import select,text,update
from sqlalchemy.orm import Session

import models #noqa registers the tables on base before create_all
from config import settings
from db import Base, SessionLocal,engine, get_db
from llm import answer_from_context,get_reply, stream_reply
from pdf import PdfError, extract_text
# from rag import chunk_document, embed_chunks, get_model, search
from rag import get_model, index_document, search
from schemas import AskRequest,AskResponse,ChatResponse,ChatRequest,DocumentOut,SearchRequest,Source


logger = logging.getLogger(__name__)
# what users see; the real error only goes to the server logs
LLM_ERROR = "The AI service isn't available right now. Please try again in a moment."
FRONTEND_PAGE = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
MAX_PDF_BYTES = 10 * 1024 * 1024   # 10 MB


@asynccontextmanager
async def lifespan(app: FastAPI):
    # a job that was running when the server stopped will never finish, so say so
    with SessionLocal() as db:
        db.execute(
            update(models.Document)
            .where(models.Document.status == "processing")
            .values(status="failed", error="The server restarted during processing. Upload it again.")
        )
        db.commit()
    get_model()   # load now, so the first question isn't slowed down
    yield


app = FastAPI(title="API", lifespan=lifespan)



@app.get("/health")
def health(db: Session = Depends(get_db)):
    """200 only when database answers too"""
    try: 
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unreachable")
        return JSONResponse(status_code=503, content={"status": "error", "database":"down"})
    # return {"st}
    return {"status": "ok!", "database":"ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db:Session = Depends(get_db)):

    # 1. find the conversation, or start a new one
    if request.conversation_id is None:
        conversation = models.Conversation(title=request.message[:50])
        db.add(conversation)
        db.flush()   # sends the INSERT so conversation.id is filled in (not committed yet)
    else:
        conversation = db.get(models.Conversation, request.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # 2. load the last N messages as history, oldest first
    recent = db.scalars(
        select(models.Message)
        .where(models.Message.conversation_id == conversation.id)
        .order_by(models.Message.id.desc())
        .limit(settings.max_history_messages)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]

    # 3. ask the LLM
    try:
        reply, tokens_used = get_reply(history + [{"role": "user", "content": request.message}])
    except (groq.APIError, RuntimeError):
        logger.exception("LLM call failed for conversation %s", conversation.id)
        db.rollback()   # nothing is saved, not even a new conversation
        raise HTTPException(status_code=502, detail=LLM_ERROR)


    # 4. save the question and the answer together, only after success
    db.add_all([
        models.Message(conversation_id=conversation.id, role="user", content=request.message),
        models.Message(
            conversation_id=conversation.id,
            role="assistant",
            content=reply,
            model=settings.model_name,
            tokens_used=tokens_used,
        ),
    ])
    db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        reply=reply,
        model=settings.model_name,
        tokens_used=tokens_used,
    )


@app.get("/", include_in_schema=False)
def home():
    """The comparison page (served from here, so no CORS setup is needed)."""
    return FileResponse(FRONTEND_PAGE)


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


@app.post("/chat/stream")
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

def to_document_out(document: models.Document) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        filename=document.filename,
        page_count=document.page_count,
        characters=len(document.content),
        chunks=document.chunk_count,
        status=document.status,
        error=document.error,
    )


@app.post("/documents", response_model=DocumentOut, status_code=202)
def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Save the PDF and answer right away. Chunks are built in the background."""
    data = file.file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF is too big. The limit is 10 MB.")

    try:
        content, page_count = extract_text(data)
    except PdfError as e:
        raise HTTPException(status_code=422, detail=str(e))

    document = models.Document(
        filename=file.filename or "unnamed.pdf",
        page_count=page_count,
        content=content,
        status="processing",
    )
    db.add(document)
    db.commit()

    background_tasks.add_task(index_document, document.id)
    return to_document_out(document)


def get_document(db: Session, document_id: int) -> models.Document:
    document = db.get(models.Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.get("/documents/{document_id}", response_model=DocumentOut)
def read_document(document_id: int, db: Session = Depends(get_db)):
    """The page calls this every few seconds to see if the chunks are ready."""
    return to_document_out(get_document(db, document_id))


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



    
@app.post("/ask/prompt", response_model=AskResponse)
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

def to_sources(hits: list[tuple[models.Chunk, float]]) -> list[Source]:
    return [Source(page=chunk.page, score=round(score, 3), content=chunk.content) for chunk, score in hits]


@app.post("/search", response_model=list[Source])
def search_document(request: SearchRequest, db: Session = Depends(get_db)):
    """Retrieval only, no LLM: check that the right chunks come back."""
    document = get_document(db, request.document_id)
    require_ready(document)
    return to_sources(search(db, document.id, request.question, request.top_k))



@app.post("/ask/rag", response_model=AskResponse)
def ask_rag(request: AskRequest, db: Session = Depends(get_db)):
    """RAG: only the chunks closest to the question go into the prompt."""
    # document = get_document(db, request.document_id)

    # start = time.perf_counter()
    # hits = search(db, document.id, request.question)
    # if not hits:
    #     raise HTTPException(status_code=409, detail="This document has no chunks. Upload it again.")

    document = get_document(db, request.document_id)
    require_ready(document)

    start = time.perf_counter()
    hits = search(db, document.id, request.question)
    
    context = "\n\n".join(f"[Page {chunk.page}]\n{chunk.content}" for chunk, _ in hits)
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