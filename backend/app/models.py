from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text,func
from sqlalchemy.orm import Mapped, mapped_column,relationship


from app.db import Base
EMBEDDING_DIM = 384   # how many numbers the embedding model produces per chunk



class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="New Chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan", #deleting chat deleting its message
        order_by="Message.id",
    )



class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"),index=True)

    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(100))
    tokens_used: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")



class Document(Base):

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    page_count: Mapped[int]
    content: Mapped[str] = mapped_column(Text)   # the whole text, with [Page N] markers
    content_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)   # spots duplicate uploads
    status: Mapped[str] = mapped_column(String(20), server_default="ready")   # processing, ready or failed
    error: Mapped[str | None] = mapped_column(String(500))   # why it failed, safe to show the user
    chunk_count: Mapped[int] = mapped_column(server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",   # deleting a document deletes its chunks
    )


class Chunk(Base):
    __tablename__= "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page: Mapped[int]
    section: Mapped[str | None] = mapped_column(String(200))   # the heading this chunk sits under
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))

    document: Mapped[Document] = relationship(back_populates="chunks")