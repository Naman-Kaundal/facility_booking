"""Week 4: cost settings, request cost breakdowns, email log and admin audit log.

Revision ID: 0004_costing_notifications_admin
Revises: 0003_workflow
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_costing_notifications_admin"
down_revision = "0003_workflow"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(12, 2)
PERCENT = sa.Numeric(5, 2)


def upgrade() -> None:
    # --- settings (one row) ---
    settings = op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("gst_pct", PERCENT, nullable=False),
        sa.Column("cleaning_pct", PERCENT, nullable=False),
        sa.Column("security_deposit", sa.Integer(), nullable=False),
        sa.Column("electricity_advance_pct", PERCENT, nullable=False),
        sa.Column("payment_url", sa.String(500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(320), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_app_settings_singleton"),
        sa.CheckConstraint("gst_pct >= 0 AND gst_pct <= 100", name="ck_app_settings_gst_pct_range"),
        sa.CheckConstraint("cleaning_pct >= 0 AND cleaning_pct <= 100", name="ck_app_settings_cleaning_pct_range"),
        sa.CheckConstraint(
            "electricity_advance_pct >= 0 AND electricity_advance_pct <= 100",
            name="ck_app_settings_electricity_advance_pct_range",
        ),
        sa.CheckConstraint("security_deposit >= 0", name="ck_app_settings_deposit_non_negative"),
    )
    # Defaults from the presentation's review/advance wireframe (LLD §9.1). No payment URL yet.
    op.bulk_insert(
        settings,
        [{"id": 1, "gst_pct": 18, "cleaning_pct": 10, "security_deposit": 5000, "electricity_advance_pct": 80}],
    )

    # --- cost breakdown per request ---
    op.create_table(
        "request_costs",
        sa.Column("request_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("booking_subtotal", MONEY, nullable=False),
        sa.Column("gst_pct", PERCENT, nullable=False),
        sa.Column("gst_amount", MONEY, nullable=False),
        sa.Column("cleaning_pct", PERCENT, nullable=False),
        sa.Column("cleaning_amount", MONEY, nullable=False),
        sa.Column("security_deposit", MONEY, nullable=False),
        sa.Column("electricity_estimate", MONEY, nullable=False),
        sa.Column("electricity_advance_pct", PERCENT, nullable=False),
        sa.Column("electricity_advance", MONEY, nullable=False),
        sa.Column("total_estimated_cost", MONEY, nullable=False),
        sa.Column("advance_amount", MONEY, nullable=False),
        sa.Column("estimate_remark", sa.Text(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_by", sa.Integer(), nullable=True),
        sa.Column("payment_url_snapshot", sa.String(500), nullable=True),
        sa.Column("intimated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("intimated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["request_id"], ["requests.id"], name="fk_request_costs_request_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["calculated_by"], ["users.id"], name="fk_request_costs_calculated_by"),
        sa.ForeignKeyConstraint(["intimated_by"], ["users.id"], name="fk_request_costs_intimated_by"),
        sa.CheckConstraint(
            "booking_subtotal >= 0 AND gst_amount >= 0 AND cleaning_amount >= 0 AND security_deposit >= 0 "
            "AND electricity_estimate >= 0 AND electricity_advance >= 0 AND total_estimated_cost >= 0 "
            "AND advance_amount >= 0",
            name="ck_request_costs_amounts_non_negative",
        ),
    )

    # --- email log ---
    op.create_table(
        "email_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("event", sa.String(40), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(200), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["request_id"], ["requests.id"], name="fk_email_logs_request_id", ondelete="SET NULL"
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_email_logs_idempotency_key"),
        sa.CheckConstraint("status IN ('PENDING', 'SENT', 'FAILED')", name="ck_email_logs_status_valid"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_email_logs_attempts_non_negative"),
    )
    op.create_index("ix_email_logs_status_created", "email_logs", ["status", "created_at"])
    op.create_index("ix_email_logs_request_created", "email_logs", ["request_id", "created_at"])

    # --- admin audit ---
    op.create_table(
        "admin_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_email", sa.String(320), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_audit_events_created", "admin_audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_events_created", table_name="admin_audit_events")
    op.drop_table("admin_audit_events")
    op.drop_index("ix_email_logs_request_created", table_name="email_logs")
    op.drop_index("ix_email_logs_status_created", table_name="email_logs")
    op.drop_table("email_logs")
    op.drop_table("request_costs")
    op.drop_table("app_settings")
