"""SQLAlchemy table definitions (the single source of truth for the schema).

Every change here must have a matching Alembic migration in ``alembic/versions``;
``tests/test_schema.py::test_migrations_match_models`` fails if the two drift apart.

Constraint names are written out explicitly so the models and migrations always agree.
"""

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import TSRANGE, ExcludeConstraint, Range
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Allowed values, shared by models, migrations and seed data.
GROUPS = ("LHC", "AUDITORIUM", "SPORTS")
SECTIONS = ("ACADEMIC", "SPORTS")
CATEGORIES = ("PRIVATE", "GOVT", "IIT")
UNITS = ("FULL_DAY", "HALF_DAY", "PER_DAY", "THREE_HOUR")
HALVES = ("FIRST", "SECOND")
# Request lifecycle states from the LLD (§8.1), plus RETURNED (LLD §8.5 note): sent back to
# the requester by Facilities for correction.
REQUEST_STATUSES = (
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
EMAIL_STATUSES = ("PENDING", "SENT", "FAILED")


def in_list(column: str, values: tuple[str, ...]) -> str:
    """SQL text for a CHECK constraint like ``section IN ('ACADEMIC','SPORTS')``."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Facility(TimestampMixin, Base):
    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    # "group" is an SQL keyword, so the column is called facility_group (exposed as "group" in the API).
    facility_group: Mapped[str] = mapped_column(String(20))
    section: Mapped[str] = mapped_column(String(20))
    capacity: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, server_default=true())

    slot_types: Mapped[list["FacilitySlotType"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_facilities_code"),
        CheckConstraint(in_list("facility_group", GROUPS), name="ck_facilities_group_valid"),
        CheckConstraint(in_list("section", SECTIONS), name="ck_facilities_section_valid"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_facilities_capacity_positive"),
        Index("ix_facilities_active_group", "active", "facility_group"),
    )


class FacilitySlotType(Base):
    """Which booking units a facility supports (the Auditorium supports two)."""

    __tablename__ = "facility_slot_types"

    facility_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_type: Mapped[str] = mapped_column(String(20), primary_key=True)

    facility: Mapped[Facility] = relationship(back_populates="slot_types")

    __table_args__ = (
        ForeignKeyConstraint(
            ["facility_id"], ["facilities.id"], name="fk_facility_slot_types_facility_id", ondelete="CASCADE"
        ),
        CheckConstraint(in_list("slot_type", UNITS), name="ck_facility_slot_types_slot_type_valid"),
    )


class Tariff(TimestampMixin, Base):
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(20))
    unit: Mapped[str] = mapped_column(String(20))
    amount: Mapped[int] = mapped_column(Integer)  # whole rupees; 0 means "No charges"
    display_label: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(50))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, server_default=true())

    __table_args__ = (
        ForeignKeyConstraint(["facility_id"], ["facilities.id"], name="fk_tariffs_facility_id"),
        # A tariff can only exist for a unit the facility actually supports.
        ForeignKeyConstraint(
            ["facility_id", "unit"],
            ["facility_slot_types.facility_id", "facility_slot_types.slot_type"],
            name="fk_tariffs_facility_unit",
        ),
        UniqueConstraint("facility_id", "category", "unit", "version", name="uq_tariffs_version"),
        CheckConstraint(in_list("category", CATEGORIES), name="ck_tariffs_category_valid"),
        CheckConstraint("amount >= 0", name="ck_tariffs_amount_non_negative"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from", name="ck_tariffs_effective_range"
        ),
        Index("ix_tariffs_lookup", "facility_id", "category", "unit", "active", "effective_from"),
    )


class SlotWindow(Base):
    __tablename__ = "slot_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(Integer)
    slot_type: Mapped[str] = mapped_column(String(20))
    slot_key: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(100))
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    half: Mapped[str | None] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, server_default=true())

    __table_args__ = (
        ForeignKeyConstraint(["facility_id"], ["facilities.id"], name="fk_slot_windows_facility_id"),
        ForeignKeyConstraint(
            ["facility_id", "slot_type"],
            ["facility_slot_types.facility_id", "facility_slot_types.slot_type"],
            name="fk_slot_windows_facility_slot_type",
        ),
        UniqueConstraint("facility_id", "slot_key", name="uq_slot_windows_facility_slot"),
        CheckConstraint(
            "(start_time IS NULL AND end_time IS NULL) OR (start_time < end_time)",
            name="ck_slot_windows_time_range",
        ),
        CheckConstraint("half IS NULL OR " + in_list("half", HALVES), name="ck_slot_windows_half_valid"),
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Google's stable account id ("sub" claim). Never trust an email sent by the browser.
    google_sub: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(200))
    # NULL until an external user picks GOVT or PRIVATE; IIT is only ever set by the email rule.
    rate_category: Mapped[str | None] = mapped_column(String(20))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("google_sub", name="uq_users_google_sub"),
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        CheckConstraint(
            "rate_category IS NULL OR " + in_list("rate_category", CATEGORIES), name="ck_users_rate_category_valid"
        ),
    )


class UserSession(Base):
    """A signed-in browser. The cookie holds a random token; only its SHA-256 hash is stored."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    token_hash: Mapped[str] = mapped_column(String(64))
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")

    __table_args__ = (
        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_sessions_user_id", ondelete="CASCADE"),
        UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
        Index("ix_sessions_user_id", "user_id"),
    )


class BookingRequest(TimestampMixin, Base):
    """One event request (the parent). Each facility/date/slot is a RequestLine."""

    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref_no: Mapped[str | None] = mapped_column(String(20))  # assigned on submission (Week 3)
    user_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), server_default=text("'DRAFT'"))
    organisation_name_address: Mapped[str] = mapped_column(Text)
    applicant_name: Mapped[str] = mapped_column(String(200))
    contact_email: Mapped[str] = mapped_column(String(320))  # copied from the verified Google email
    office_contact: Mapped[str] = mapped_column(String(30))
    mobile: Mapped[str] = mapped_column(String(30))
    purpose: Mapped[str] = mapped_column(Text)
    participants: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Week 3: fixed at submission so later profile changes don't alter the request.
    rate_category_snapshot: Mapped[str | None] = mapped_column(String(20))
    terms_version: Mapped[str | None] = mapped_column(String(50))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Week 3: Facilities can return a submitted request for correction.
    return_reason: Mapped[str | None] = mapped_column(Text)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Week 4: the cost breakdown, once Estate has entered the electricity estimate.
    cost: Mapped["RequestCost | None"] = relationship(lazy="selectin", cascade="all, delete-orphan")
    # Final release: the Govt./PSU proof document (requests at that rate need one to be submitted).
    document: Mapped["RequestDocument | None"] = relationship(lazy="selectin", cascade="all, delete-orphan")

    lines: Mapped[list["RequestLine"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by=lambda: [RequestLine.booking_date, RequestLine.id],
    )

    __table_args__ = (
        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_requests_user_id"),
        UniqueConstraint("ref_no", name="uq_requests_ref_no"),
        CheckConstraint(in_list("status", REQUEST_STATUSES), name="ck_requests_status_valid"),
        CheckConstraint("participants > 0", name="ck_requests_participants_positive"),
        Index("ix_requests_user_created", "user_id", "created_at"),
        Index("ix_requests_status_updated", "status", "updated_at"),
    )


class RequestLine(TimestampMixin, Base):
    """One facility on one date in one slot, inside a request."""

    __tablename__ = "request_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(Integer)
    facility_id: Mapped[int] = mapped_column(Integer)
    booking_date: Mapped[date] = mapped_column(Date)
    slot_key: Mapped[str] = mapped_column(String(32))

    request: Mapped[BookingRequest] = relationship(back_populates="lines")
    facility: Mapped[Facility] = relationship(lazy="joined", viewonly=True)
    slot: Mapped[SlotWindow] = relationship(lazy="joined", viewonly=True)

    # Week 3: snapshots taken at submission (LLD §5.2, §10.7). NULL while the request is a draft.
    facility_code_snapshot: Mapped[str | None] = mapped_column(String(32))
    facility_name_snapshot: Mapped[str | None] = mapped_column(String(200))
    section_snapshot: Mapped[str | None] = mapped_column(String(20))
    slot_label_snapshot: Mapped[str | None] = mapped_column(String(100))
    rate_category_snapshot: Mapped[str | None] = mapped_column(String(20))
    tariff_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    unit_snapshot: Mapped[str | None] = mapped_column(String(20))
    line_amount_snapshot: Mapped[int | None] = mapped_column(Integer)

    # Week 3: the Academic or Sports section's decision on this line.
    decision: Mapped[str] = mapped_column(String(20), server_default=text("'PENDING'"))
    decision_remark: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(Integer)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    decider: Mapped["User | None"] = relationship(viewonly=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["request_id"], ["requests.id"], name="fk_request_lines_request_id", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["facility_id"], ["facilities.id"], name="fk_request_lines_facility_id"),
        # The slot must be one of that facility's slots (e.g. no half-day slot for a classroom).
        ForeignKeyConstraint(
            ["facility_id", "slot_key"],
            ["slot_windows.facility_id", "slot_windows.slot_key"],
            name="fk_request_lines_facility_slot",
        ),
        UniqueConstraint("request_id", "facility_id", "booking_date", "slot_key", name="uq_request_lines_unique"),
        ForeignKeyConstraint(["tariff_id_snapshot"], ["tariffs.id"], name="fk_request_lines_tariff_snapshot"),
        ForeignKeyConstraint(["decided_by"], ["users.id"], name="fk_request_lines_decided_by"),
        CheckConstraint(in_list("decision", LINE_DECISIONS), name="ck_request_lines_decision_valid"),
        CheckConstraint(
            "decision <> 'REJECTED' OR decision_remark IS NOT NULL", name="ck_request_lines_reject_needs_remark"
        ),
        Index("ix_request_lines_facility_date", "facility_id", "booking_date"),
        Index("ix_request_lines_section_decision", "section_snapshot", "decision"),
    )


class ReferenceCounter(Base):
    """One row per year, incremented atomically to hand out FB-YYYY-NNN reference numbers."""

    __tablename__ = "reference_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer)


class Reservation(Base):
    """A confirmed booking: one facility for one time range.

    The exclusion constraint makes PostgreSQL itself refuse two reservations of the same
    facility whose time ranges overlap, even if two staff members confirm at the same moment.
    """

    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_line_id: Mapped[int] = mapped_column(Integer)
    facility_id: Mapped[int] = mapped_column(Integer)
    # Institute-local (IST) wall-clock time range, half-open: [start, end).
    during: Mapped[Range[datetime]] = mapped_column(TSRANGE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["request_line_id"], ["request_lines.id"], name="fk_reservations_request_line_id", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["facility_id"], ["facilities.id"], name="fk_reservations_facility_id"),
        UniqueConstraint("request_line_id", name="uq_reservations_request_line"),
        ExcludeConstraint(("facility_id", "="), ("during", "&&"), name="ex_reservations_no_overlap", using="gist"),
    )


class StatusEvent(Base):
    """Append-only audit log: one row per workflow action (LLD §10.8, §15)."""

    __tablename__ = "status_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(Integer)
    request_line_id: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    actor_id: Mapped[int | None] = mapped_column(Integer)
    actor_role: Mapped[str | None] = mapped_column(String(20))
    remark: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actor: Mapped["User | None"] = relationship(lazy="joined", viewonly=True)
    line: Mapped["RequestLine | None"] = relationship(lazy="joined", viewonly=True)

    __table_args__ = (
        ForeignKeyConstraint(["request_id"], ["requests.id"], name="fk_status_events_request_id", ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["request_line_id"], ["request_lines.id"], name="fk_status_events_request_line_id", ondelete="SET NULL"
        ),
        ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_status_events_actor_id"),
        Index("ix_status_events_request_created", "request_id", "created_at"),
    )


class StaffRole(Base):
    """Gives a staff email a desk role.

    Keyed by email (not user id) so roles can be assigned before the person's first sign-in;
    it is matched against the verified Google email of the signed-in user.
    """

    __tablename__ = "staff_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_by: Mapped[str | None] = mapped_column(String(320))

    __table_args__ = (
        UniqueConstraint("email", "role", name="uq_staff_roles_email_role"),
        CheckConstraint(in_list("role", STAFF_ROLES), name="ck_staff_roles_role_valid"),
        CheckConstraint("email = lower(email)", name="ck_staff_roles_email_lowercase"),
        Index("ix_staff_roles_role_active", "role", "active"),
    )


# ---------------------------------------------------------------------------------------------
# Week 4: settings, costing, email log, admin audit
# ---------------------------------------------------------------------------------------------

MONEY = Numeric(12, 2)
PERCENT = Numeric(5, 2)


class AppSettings(Base):
    """Institute-wide cost settings and the payment link (LLD §9.1, §10.10). Exactly one row (id = 1).

    Changing these affects requests costed afterwards; costed requests keep their own snapshot.
    """

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    gst_pct: Mapped[Decimal] = mapped_column(PERCENT)
    cleaning_pct: Mapped[Decimal] = mapped_column(PERCENT)
    security_deposit: Mapped[int] = mapped_column(Integer)  # whole rupees, per request
    electricity_advance_pct: Mapped[Decimal] = mapped_column(PERCENT)
    # The institute's payment page. NULL until an admin configures it (never invented by the app).
    payment_url: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[str | None] = mapped_column(String(320))

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_app_settings_singleton"),
        CheckConstraint("gst_pct >= 0 AND gst_pct <= 100", name="ck_app_settings_gst_pct_range"),
        CheckConstraint("cleaning_pct >= 0 AND cleaning_pct <= 100", name="ck_app_settings_cleaning_pct_range"),
        CheckConstraint(
            "electricity_advance_pct >= 0 AND electricity_advance_pct <= 100",
            name="ck_app_settings_electricity_advance_pct_range",
        ),
        CheckConstraint("security_deposit >= 0", name="ck_app_settings_deposit_non_negative"),
    )


class RequestCost(Base):
    """The cost breakdown of one request (LLD §9.3), calculated by the backend only.

    Every input (rates, percentages, deposit, electricity) is copied here, so changing the
    settings or tariffs later never changes a request that has already been costed.
    """

    __tablename__ = "request_costs"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    booking_subtotal: Mapped[Decimal] = mapped_column(MONEY)
    gst_pct: Mapped[Decimal] = mapped_column(PERCENT)
    gst_amount: Mapped[Decimal] = mapped_column(MONEY)
    cleaning_pct: Mapped[Decimal] = mapped_column(PERCENT)
    cleaning_amount: Mapped[Decimal] = mapped_column(MONEY)
    security_deposit: Mapped[Decimal] = mapped_column(MONEY)
    electricity_estimate: Mapped[Decimal] = mapped_column(MONEY)
    electricity_advance_pct: Mapped[Decimal] = mapped_column(PERCENT)
    electricity_advance: Mapped[Decimal] = mapped_column(MONEY)
    total_estimated_cost: Mapped[Decimal] = mapped_column(MONEY)
    advance_amount: Mapped[Decimal] = mapped_column(MONEY)
    estimate_remark: Mapped[str | None] = mapped_column(Text)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    calculated_by: Mapped[int | None] = mapped_column(Integer)
    # Filled when Facilities sends the advance intimation.
    payment_url_snapshot: Mapped[str | None] = mapped_column(String(500))
    intimated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intimated_by: Mapped[int | None] = mapped_column(Integer)

    calculator: Mapped["User | None"] = relationship(
        foreign_keys="RequestCost.calculated_by", viewonly=True, lazy="joined"
    )

    __table_args__ = (
        ForeignKeyConstraint(["request_id"], ["requests.id"], name="fk_request_costs_request_id", ondelete="CASCADE"),
        ForeignKeyConstraint(["calculated_by"], ["users.id"], name="fk_request_costs_calculated_by"),
        ForeignKeyConstraint(["intimated_by"], ["users.id"], name="fk_request_costs_intimated_by"),
        CheckConstraint(
            "booking_subtotal >= 0 AND gst_amount >= 0 AND cleaning_amount >= 0 AND security_deposit >= 0 "
            "AND electricity_estimate >= 0 AND electricity_advance >= 0 AND total_estimated_cost >= 0 "
            "AND advance_amount >= 0",
            name="ck_request_costs_amounts_non_negative",
        ),
    )


class EmailLog(Base):
    """Every email the app tries to send (LLD §10.9, §14): written before sending, then updated.

    ``idempotency_key`` stops the same notification being queued twice for one workflow event.
    """

    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int | None] = mapped_column(Integer)
    event: Mapped[str] = mapped_column(String(40))
    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300))
    body_text: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), server_default=text("'PENDING'"))
    attempt_count: Mapped[int] = mapped_column(Integer, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(["request_id"], ["requests.id"], name="fk_email_logs_request_id", ondelete="SET NULL"),
        UniqueConstraint("idempotency_key", name="uq_email_logs_idempotency_key"),
        CheckConstraint(in_list("status", EMAIL_STATUSES), name="ck_email_logs_status_valid"),
        CheckConstraint("attempt_count >= 0", name="ck_email_logs_attempts_non_negative"),
        Index("ix_email_logs_status_created", "status", "created_at"),
        Index("ix_email_logs_request_created", "request_id", "created_at"),
    )


class AdminAuditEvent(Base):
    """Append-only log of admin changes to master data, settings and roles (LLD §15)."""

    __tablename__ = "admin_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_email: Mapped[str] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_admin_audit_events_created", "created_at"),)


# ---------------------------------------------------------------------------------------------
# Final release: Govt./PSU proof documents
# ---------------------------------------------------------------------------------------------


class RequestDocument(Base):
    """The proof document attached to a request booked at the Govt./PSU rate.

    One per request: uploading again replaces it. The file itself is on disk (see
    ``document_storage``); this row holds its details. Facilities checks it when reviewing the
    request and returns the request for correction if the proof isn't acceptable.
    """

    __tablename__ = "request_documents"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(64))
    content_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[int | None] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["request_id"], ["requests.id"], name="fk_request_documents_request_id", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name="fk_request_documents_uploaded_by", ondelete="SET NULL"
        ),
        UniqueConstraint("stored_name", name="uq_request_documents_stored_name"),
        CheckConstraint("size_bytes > 0", name="ck_request_documents_size_positive"),
    )
