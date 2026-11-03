"""Master data: facilities, supported slot types, tariffs and slot windows.

Revision ID: 0001_master_data
Revises:
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_master_data"
down_revision = None
branch_labels = None
depends_on = None

GROUPS = ("LHC", "AUDITORIUM", "SPORTS")
SECTIONS = ("ACADEMIC", "SPORTS")
CATEGORIES = ("PRIVATE", "GOVT", "IIT")
UNITS = ("FULL_DAY", "HALF_DAY", "PER_DAY", "THREE_HOUR")
HALVES = ("FIRST", "SECOND")


def in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "facilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("facility_group", sa.String(20), nullable=False),
        sa.Column("section", sa.String(20), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("code", name="uq_facilities_code"),
        sa.CheckConstraint(in_list("facility_group", GROUPS), name="ck_facilities_group_valid"),
        sa.CheckConstraint(in_list("section", SECTIONS), name="ck_facilities_section_valid"),
        sa.CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_facilities_capacity_positive"),
    )
    op.create_index("ix_facilities_active_group", "facilities", ["active", "facility_group"])

    op.create_table(
        "facility_slot_types",
        sa.Column("facility_id", sa.Integer(), primary_key=True),
        sa.Column("slot_type", sa.String(20), primary_key=True),
        sa.ForeignKeyConstraint(
            ["facility_id"], ["facilities.id"], name="fk_facility_slot_types_facility_id", ondelete="CASCADE"
        ),
        sa.CheckConstraint(in_list("slot_type", UNITS), name="ck_facility_slot_types_slot_type_valid"),
    )

    op.create_table(
        "tariffs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("display_label", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], name="fk_tariffs_facility_id"),
        sa.ForeignKeyConstraint(
            ["facility_id", "unit"],
            ["facility_slot_types.facility_id", "facility_slot_types.slot_type"],
            name="fk_tariffs_facility_unit",
        ),
        sa.UniqueConstraint("facility_id", "category", "unit", "version", name="uq_tariffs_version"),
        sa.CheckConstraint(in_list("category", CATEGORIES), name="ck_tariffs_category_valid"),
        sa.CheckConstraint("amount >= 0", name="ck_tariffs_amount_non_negative"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_tariffs_effective_range"),
    )
    op.create_index(
        "ix_tariffs_lookup", "tariffs", ["facility_id", "category", "unit", "active", "effective_from"]
    )

    op.create_table(
        "slot_windows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), nullable=False),
        sa.Column("slot_type", sa.String(20), nullable=False),
        sa.Column("slot_key", sa.String(32), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("half", sa.String(10), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], name="fk_slot_windows_facility_id"),
        sa.ForeignKeyConstraint(
            ["facility_id", "slot_type"],
            ["facility_slot_types.facility_id", "facility_slot_types.slot_type"],
            name="fk_slot_windows_facility_slot_type",
        ),
        sa.UniqueConstraint("facility_id", "slot_key", name="uq_slot_windows_facility_slot"),
        sa.CheckConstraint(
            "(start_time IS NULL AND end_time IS NULL) OR (start_time < end_time)", name="ck_slot_windows_time_range"
        ),
        sa.CheckConstraint("half IS NULL OR " + in_list("half", HALVES), name="ck_slot_windows_half_valid"),
    )


def downgrade() -> None:
    op.drop_table("slot_windows")
    op.drop_index("ix_tariffs_lookup", table_name="tariffs")
    op.drop_table("tariffs")
    op.drop_table("facility_slot_types")
    op.drop_index("ix_facilities_active_group", table_name="facilities")
    op.drop_table("facilities")
