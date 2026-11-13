"""Final release: Govt./PSU proof documents attached to booking requests.

Revision ID: 0005_request_documents
Revises: 0004_costing_notifications_admin
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_request_documents"
down_revision = "0004_costing_notifications_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "request_documents",
        sa.Column("request_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["request_id"], ["requests.id"], name="fk_request_documents_request_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name="fk_request_documents_uploaded_by", ondelete="SET NULL"
        ),
        sa.UniqueConstraint("stored_name", name="uq_request_documents_stored_name"),
        sa.CheckConstraint("size_bytes > 0", name="ck_request_documents_size_positive"),
    )


def downgrade() -> None:
    op.drop_table("request_documents")
