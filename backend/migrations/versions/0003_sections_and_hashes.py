"""chunk sections and document hashes

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("section", sa.String(length=200), nullable=True))
    op.add_column("documents", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_documents_content_hash"), "documents", ["content_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_content_hash"), table_name="documents")
    op.drop_column("documents", "content_hash")
    op.drop_column("chunks", "section")