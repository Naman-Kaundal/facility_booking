"""Users, sign-in sessions, booking requests (drafts) and request lines.

Revision ID: 0002_users_and_requests
Revises: 0001_master_data
Create Date: 2026-10-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_users_and_requests"
down_revision = "0001_master_data"
branch_labels = None
depends_on = None

CATEGORIES = ("PRIVATE", "GOVT", "IIT")
REQUEST_STATUSES = ("DRAFT", "SUBMITTED", "WITH_SECTION", "REJECTED", "WITH_ESTATE", "COSTED", "ADVANCE_INTIMATED")


def in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("google_sub", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("rate_category", sa.String(20), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("google_sub", name="uq_users_google_sub"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        sa.CheckConstraint(
            "rate_category IS NULL OR " + in_list("rate_category", CATEGORIES), name="ck_users_rate_category_valid"
        ),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_sessions_user_id", ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ref_no", sa.String(20), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column("organisation_name_address", sa.Text(), nullable=False),
        sa.Column("applicant_name", sa.String(200), nullable=False),
        sa.Column("contact_email", sa.String(320), nullable=False),
        sa.Column("office_contact", sa.String(30), nullable=False),
        sa.Column("mobile", sa.String(30), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("participants", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_requests_user_id"),
        sa.UniqueConstraint("ref_no", name="uq_requests_ref_no"),
        sa.CheckConstraint(in_list("status", REQUEST_STATUSES), name="ck_requests_status_valid"),
        sa.CheckConstraint("participants > 0", name="ck_requests_participants_positive"),
    )
    op.create_index("ix_requests_user_created", "requests", ["user_id", "created_at"])
    op.create_index("ix_requests_status_updated", "requests", ["status", "updated_at"])

    op.create_table(
        "request_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("facility_id", sa.Integer(), nullable=False),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("slot_key", sa.String(32), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["request_id"], ["requests.id"], name="fk_request_lines_request_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], name="fk_request_lines_facility_id"),
        sa.ForeignKeyConstraint(
            ["facility_id", "slot_key"],
            ["slot_windows.facility_id", "slot_windows.slot_key"],
            name="fk_request_lines_facility_slot",
        ),
        sa.UniqueConstraint(
            "request_id", "facility_id", "booking_date", "slot_key", name="uq_request_lines_unique"
        ),
    )
    op.create_index("ix_request_lines_facility_date", "request_lines", ["facility_id", "booking_date"])


def downgrade() -> None:
    op.drop_index("ix_request_lines_facility_date", table_name="request_lines")
    op.drop_table("request_lines")
    op.drop_index("ix_requests_status_updated", table_name="requests")
    op.drop_index("ix_requests_user_created", table_name="requests")
    op.drop_table("requests")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
