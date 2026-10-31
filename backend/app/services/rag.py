import logging
import re
from functools import lru_cache
from threading import Lock
from typing import NamedTuple

from fastembed import TextEmbedding
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal

logger = logging.getLogger(__name__)



EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"   # must produce models.EMBEDDING_DIM numbers
CHUNK_WORDS = 80
CHUNK_OVERLAP = 15   # repeated words, so a sentence cut at the edge survives in the next chunk
TOP_K = 4
MAX_HEADING_CHARS = 80
HEADING = re.compile(r"^\d+(\.\d+)*\.?\s+[A-Z].*[^.,;:?!]$")   # like "1.2 Tolland Depot" or "7. Late submissions"
INDEX_LOCK = Lock()   # embed one document at a time, so uploads can't use up the whole CPU


class Piece(NamedTuple):
    page: int
    section: str | None
    text: str

@lru_cache
def get_model() -> TextEmbedding:
    """Load the embedding model once. The first run downloads it."""
    return TextEmbedding(EMBEDDING_MODEL)



def is_heading(line: str) -> bool:
    return len(line) <= MAX_HEADING_CHARS and HEADING.match(line) is not None


def split_words(page: int, section: str | None, lines: list[str]) -> list[Piece]:
    words = " ".join(lines).split()
    pieces = []
    for start in range(0, len(words), CHUNK_WORDS - CHUNK_OVERLAP):
        pieces.append(Piece(page, section, " ".join(words[start:start + CHUNK_WORDS])))
        if start + CHUNK_WORDS >= len(words):
            break
    return pieces


def chunk_document(content: str) -> list[Piece]:
    """Split text with [Page N] markers into chunks. A new page or heading always starts a new chunk."""
    parts = re.split(r"\[Page (\d+)\]\n", content)
    pieces = []
    section = None   # carries over to the next page until a new heading appears

    for number, page_text in zip(parts[1::2], parts[2::2]):
        page = int(number)
        lines = []
        for line in page_text.splitlines():
            line = line.strip()
            if is_heading(line):
                pieces += split_words(page, section, lines)
                lines = []
                section = line
            else:
                lines.append(line)
        pieces += split_words(page, section, lines)
    return pieces


def embed_chunks(texts: list[str]) -> list[list[float]]:
    return [vector.tolist() for vector in get_model().passage_embed(texts)]


def embed_question(question: str) -> list[float]:
    return next(iter(get_model().query_embed(question))).tolist()


def search(db: Session, document_id: int, question: str, top_k: int = TOP_K) -> list[tuple[models.Chunk, float]]:
    """The chunks closest in meaning to the question, as (chunk, similarity score) pairs."""
    distance = models.Chunk.embedding.cosine_distance(embed_question(question))
    rows = db.execute(
        select(models.Chunk, distance)
        .where(models.Chunk.document_id == document_id)
        .order_by(distance)
        .limit(top_k)
    ).all()
    return [(chunk, 1 - dist) for chunk, dist in rows]



def index_document(document_id: int) -> None:
    """Background job: build a document's chunks and record whether it worked."""
    # short database sessions, so no connection is held during the slow embedding step
    with SessionLocal() as db:
        content = db.get(models.Document, document_id).content

    try:
        with INDEX_LOCK:
            pieces = chunk_document(content)
            if not pieces:
                raise ValueError("no text left to index")
            vectors = embed_chunks([piece.text for piece in pieces])

        with SessionLocal() as db:
            document = db.get(models.Document, document_id)
            document.chunks = [
                models.Chunk(page=piece.page, section=piece.section, content=piece.text, embedding=vector)
                for piece, vector in zip(pieces, vectors)
            ]
            document.chunk_count = len(pieces)
            document.status = "ready"
            db.commit()   # the chunks and the status are saved together
    except Exception:
        logger.exception("Could not index document %s", document_id)
        with SessionLocal() as db:
            document = db.get(models.Document, document_id)
            document.status = "failed"
            document.error = "Could not build chunks for this document. Upload it again."
            db.commit()