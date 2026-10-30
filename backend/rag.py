import re
from functools import lru_cache

from fastembed import TextEmbedding
from sqlalchemy import select
from sqlalchemy.orm import Session

import models



EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"   # must produce models.EMBEDDING_DIM numbers
CHUNK_WORDS = 80
CHUNK_OVERLAP = 15   # repeated words, so a sentence cut at the edge survives in the next chunk
TOP_K = 4


@lru_cache
def get_model() -> TextEmbedding:
    """Load the embedding model once. The first run downloads it."""
    return TextEmbedding(EMBEDDING_MODEL)



def chunk_document(content:str) -> list[tuple[int,str]]:
    """Split text with [Page N] markers into (page number, chunk text) pairs."""


    parts = re.split(r"\[Page (\d+)\]\n", content)
    chunks = []

    for number, page_text in zip(parts[1::2], parts[2::2]):
        words = page_text.split()
        for start in range(0, len(words), CHUNK_WORDS - CHUNK_OVERLAP):
            chunks.append((int(number), " ".join(words[start:start + CHUNK_WORDS])))
            if start + CHUNK_WORDS >= len(words):
                break
    return chunks


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
