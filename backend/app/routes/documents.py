import hashlib

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, defer

from app import models
from app.db import get_db
from app.schemas import DocumentOut
from app.services.pdf import PdfError, extract_text
from app.services.rag import index_document

MAX_PDF_BYTES = 10 * 1024 * 1024   # 10 MB

router = APIRouter(prefix="/documents", tags=["documents"])


def to_document_out(document: models.Document, characters: int | None = None) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        filename=document.filename,
        page_count=document.page_count,
        characters=len(document.content) if characters is None else characters,
        chunks=document.chunk_count,
        status=document.status,
        error=document.error,
    )


def find_by_hash(db: Session, content_hash: str) -> models.Document | None:
    return db.scalar(select(models.Document).where(models.Document.content_hash == content_hash))


def get_document(db: Session, document_id: int) -> models.Document:
    document = db.get(models.Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post("", response_model=DocumentOut, status_code=202)
def upload_document(
    background_tasks: BackgroundTasks,
    response: Response,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Save the PDF and answer right away. Chunks are built in the background."""
    data = file.file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF is too big. The limit is 10 MB.")

    content_hash = hashlib.sha256(data).hexdigest()
    existing = find_by_hash(db, content_hash)
    if existing is not None:
        if existing.status != "failed":
            response.status_code = 200   # 200 = you already have this one, 202 = new job started
            return to_document_out(existing)
        # same file after a failure: try again with the same row
        existing.status = "processing"
        existing.error = None
        db.commit()
        background_tasks.add_task(index_document, existing.id)
        return to_document_out(existing)

    try:
        content, page_count = extract_text(data)
    except PdfError as e:
        raise HTTPException(status_code=422, detail=str(e))

    document = models.Document(
        filename=file.filename or "unnamed.pdf",
        page_count=page_count,
        content=content,
        content_hash=content_hash,
        status="processing",
    )
    db.add(document)
    try:
        db.commit()
    except IntegrityError:   # the same file was uploaded at the same moment
        db.rollback()
        response.status_code = 200
        return to_document_out(find_by_hash(db, content_hash))

    background_tasks.add_task(index_document, document.id)
    return to_document_out(document)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Newest first. The full text isn't loaded, so this stays fast with many documents."""
    rows = db.execute(
        select(models.Document, func.length(models.Document.content))
        .options(defer(models.Document.content))
        .order_by(models.Document.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [to_document_out(document, characters) for document, characters in rows]


@router.get("/{document_id}", response_model=DocumentOut)
def read_document(document_id: int, db: Session = Depends(get_db)):
    """The page calls this every few seconds to see if the chunks are ready."""
    return to_document_out(get_document(db, document_id))


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = get_document(db, document_id)
    if document.status == "processing":
        raise HTTPException(status_code=409, detail="This document is still being processed. Try again in a moment.")
    db.execute(delete(models.Document).where(models.Document.id == document_id))   # Postgres deletes its chunks too
    db.commit()
