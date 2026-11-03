"""Week 3 workflow: submission snapshots, line decisions, RETURNED status, reference numbers,
reservations (no overlapping confirmed bookings), audit events and staff roles.

Revision ID: 0003_workflow
Revises: 0002_users_and_requests
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_workflow"
down_revision = "0002_users_and_requests"
branch_labels = None
depends_on = None

OLD_STATUSES = ("DRAFT", "SUBMITTED", "WITH_SECTION", "REJECTED", "WITH_ESTATE", "COSTED", "ADVANCE_INTIMATED")
NEW_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "RETURNED",
    "WITH_SECTION",
    "REJECTED",
    "WITH_ESTATE",
    "COSTED",
    "ADVANCE_INTIMATED",
)
LINE_DECISIONS = ("PENDING", "CONFIRMED", "REJECTED")
STAFF_ROLES = ("FACILITY", "ACADEMIC", "SPORTS", "ESTATE", "ADMIN")


def in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    # Lets a GiST index combine "same facility" (=) with "overlapping time" (&&).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # --- requests ---
    op.drop_constraint("ck_requests_status_valid", "requests", type_="check")
    op.create_check_constraint("ck_requests_status_valid", "requests", in_list("status", NEW_STATUSES))
    op.add_column("requests", sa.Column("rate_category_snapshot", sa.String(20), nullable=True))
    op.add_column("requests", sa.Column("terms_version", sa.String(50), nullable=True))
    op.add_column("requests", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("requests", sa.Column("return_reason", sa.Text(), nullable=True))
    op.add_column("requests", sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True))

    # --- request_lines: snapshots + decisions ---
    for name, type_ in (
        ("facility_code_snapshot", sa.String(32)),
        ("facility_name_snapshot", sa.String(200)),
        ("section_snapshot", sa.String(20)),
        ("slot_label_snapshot", sa.String(100)),
        ("rate_category_snapshot", sa.String(20)),
        ("tariff_id_snapshot", sa.Integer()),
        ("unit_snapshot", sa.String(20)),
        ("line_amount_snapshot", sa.Integer()),
    ):
        op.add_column("request_lines", sa.Column(name, type_, nullable=True))
    op.add_column(
        "request_lines", sa.Column("decision", sa.String(20), server_default=sa.text("'PENDING'"), nullable=False)
    )
    op.add_column("request_lines", sa.Column("decision_remark", sa.Text(), nullable=True))
    op.add_column("request_lines", sa.Column("decided_by", sa.Integer(), nullable=True))
    op.add_column("request_lines", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_request_lines_tariff_snapshot", "request_lines", "tariffs", ["tariff_id_snapshot"], ["id"]
    )
    op.create_foreign_key("fk_request_lines_decided_by", "request_lines", "users", ["decided_by"], ["id"])
    op.create_check_constraint(
        "ck_request_lines_decision_valid", "request_lines", in_list("decision", LINE_DECISIONS)
    )
    op.create_check_constraint(
        "ck_request_lines_reject_needs_remark",
        "request_lines",
        "decision <> 'REJECTED' OR decision_remark IS NOT NULL",
    )
    op.create_index("ix_request_lines_section_decision", "request_lines", ["section_snapshot", "decision"])

    # --- reference numbers ---
    op.create_table(
        "reference_counters",
        sa.Column("year", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
    )

    # --- confirmed bookings ---
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_line_id", sa.Integer(), nullable=False),
        sa.Column("facility_id", sa.Integer(), nullable=False),
        sa.Column("during", postgresql.TSRANGE(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["request_line_id"], ["request_lines.id"], name="fk_reservations_request_line_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], name="fk_reservations_facility_id"),
        sa.UniqueConstraint("request_line_id", name="uq_reservations_request_line"),
        postgresql.ExcludeConstraint(
            ("facility_id", "="), ("during", "&&"), name="ex_reservations_no_overlap", using="gist"
        ),
    )

    # --- audit log ---
    op.create_table(
        "status_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("request_line_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(20), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["request_id"], ["requests.id"], name="fk_status_events_request_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["request_line_id"], ["request_lines.id"], name="fk_status_events_request_line_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_status_events_actor_id"),
    )
    op.create_index("ix_status_events_request_created", "status_events", ["request_id", "created_at"])

    # --- staff roles ---
    op.create_table(
        "staff_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("assigned_by", sa.String(320), nullable=True),
        sa.UniqueConstraint("email", "role", name="uq_staff_roles_email_role"),
        sa.CheckConstraint(in_list("role", STAFF_ROLES), name="ck_staff_roles_role_valid"),
        sa.CheckConstraint("email = lower(email)", name="ck_staff_roles_email_lowercase"),
    )
    op.create_index("ix_staff_roles_role_active", "staff_roles", ["role", "active"])


def downgrade() -> None:
    op.drop_index("ix_staff_roles_role_active", table_name="staff_roles")
    op.drop_table("staff_roles")
    op.drop_index("ix_status_events_request_created", table_name="status_events")
    op.drop_table("status_events")
    op.drop_table("reservations")
    op.drop_table("reference_counters")

    op.drop_index("ix_request_lines_section_decision", table_name="request_lines")
    op.drop_constraint("ck_request_lines_reject_needs_remark", "request_lines", type_="check")
    op.drop_constraint("ck_request_lines_decision_valid", "request_lines", type_="check")
    op.drop_constraint("fk_request_lines_decided_by", "request_lines", type_="foreignkey")
    op.drop_constraint("fk_request_lines_tariff_snapshot", "request_lines", type_="foreignkey")
    for name in (
        "decided_at",
        "decided_by",
        "decision_remark",
        "decision",
        "line_amount_snapshot",
        "unit_snapshot",
        "tariff_id_snapshot",
        "rate_category_snapshot",
        "slot_label_snapshot",
        "section_snapshot",
        "facility_name_snapshot",
        "facility_code_snapshot",
    ):
        op.drop_column("request_lines", name)

    for name in ("returned_at", "return_reason", "terms_accepted_at", "terms_version", "rate_category_snapshot"):
        op.drop_column("requests", name)
    op.execute("UPDATE requests SET status = 'DRAFT' WHERE status = 'RETURNED'")
    op.drop_constraint("ck_requests_status_valid", "requests", type_="check")
    op.create_check_constraint("ck_requests_status_valid", "requests", in_list("status", OLD_STATUSES))
