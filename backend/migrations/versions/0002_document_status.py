"""document status

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("status", sa.String(length=20), server_default="ready", nullable=False))
    op.add_column("documents", sa.Column("error", sa.String(length=500), nullable=True))
    op.add_column("documents", sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False))

    # fill in the new columns for documents that already exist
    op.execute("UPDATE documents SET chunk_count = (SELECT count(*) FROM chunks WHERE chunks.document_id = documents.id)")
    op.execute(
        "UPDATE documents SET status = 'failed', error = 'This document has no chunks. Upload it again.' "
        "WHERE chunk_count = 0"
    )


def downgrade() -> None:
    op.drop_column("documents", "chunk_count")
    op.drop_column("documents", "error")
    op.drop_column("documents", "status")