from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text,func
from sqlalchemy.orm import Mapped, mapped_column,relationship


from db import Base



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
    Conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"),index=True)

    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(100))
    tokens_used: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())

    Conversation: Mapped[Conversation] = relationship(back_populates="messages")