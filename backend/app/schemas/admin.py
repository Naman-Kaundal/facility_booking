"""Admin API models (LLD §11.5). Admin-only; every endpoint requires an active ADMIN role."""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.facility import Category, Group, Section, Unit

_INPUT = ConfigDict(extra="forbid", str_strip_whitespace=True)
Percent = Decimal
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
StaffRoleName = Literal["FACILITY", "ACADEMIC", "SPORTS", "ESTATE", "ADMIN"]


# ----- settings -----


class SettingsOut(BaseModel):
    gst_pct: float
    cleaning_pct: float
    security_deposit: int
    electricity_advance_pct: float
    payment_url: str | None
    updated_at: datetime | None
    updated_by: str | None


class SettingsPatch(BaseModel):
    model_config = _INPUT

    gst_pct: Percent | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    cleaning_pct: Percent | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    security_deposit: int | None = Field(default=None, ge=0, le=10_000_000)
    electricity_advance_pct: Percent | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    # Empty string clears the link. Must be the institute's real payment page (the app never invents one).
    payment_url: str | None = Field(default=None, max_length=500)

    @field_validator("payment_url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        if not re.match(r"^https?://[^\s/$.?#][^\s]*$", value):
            raise ValueError("Enter a full web address starting with https://")
        return value

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one setting to change.")
        return self


# ----- staff roles -----


class StaffRoleOut(BaseModel):
    id: int
    email: str
    role: StaffRoleName
    active: bool
    assigned_at: datetime
    assigned_by: str | None


class StaffRoleIn(BaseModel):
    model_config = _INPUT

    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: StaffRoleName


class StaffRolePatch(BaseModel):
    model_config = _INPUT

    active: bool


# ----- facilities, tariffs, slot windows -----


class AdminTariffOut(BaseModel):
    id: int
    category: Category
    unit: Unit
    amount: int
    display_label: str
    version: str
    effective_from: datetime
    effective_to: datetime | None
    active: bool
    current: bool  # the tariff in effect today


class AdminSlotOut(BaseModel):
    id: int
    slot_key: str
    slot_type: Unit
    label: str
    start: str | None
    end: str | None
    active: bool


class AdminFacilityOut(BaseModel):
    id: int
    code: str
    name: str
    group: Group
    section: Section
    capacity: int | None
    notes: str | None
    active: bool
    sort_order: int
    slot_types: list[Unit]
    slots: list[AdminSlotOut]
    tariffs: list[AdminTariffOut]


class FacilityPatch(BaseModel):
    model_config = _INPUT

    name: str | None = Field(default=None, min_length=1, max_length=200)
    capacity: int | None = Field(default=None, gt=0, le=100_000)
    notes: str | None = Field(default=None, max_length=2000)
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to change.")
        return self


class TariffIn(BaseModel):
    """A new rate. It applies to bookings on or after ``effective_from``; submitted requests keep theirs."""

    model_config = _INPUT

    facility_id: int = Field(gt=0)
    category: Category
    unit: Unit
    amount: int = Field(ge=0, le=10_000_000)
    effective_from: date


class TariffPatch(BaseModel):
    model_config = _INPUT

    active: bool


class SlotWindowPatch(BaseModel):
    model_config = _INPUT

    label: str | None = Field(default=None, min_length=1, max_length=100)
    start: str | None = None
    end: str | None = None
    active: bool | None = None

    @field_validator("start", "end")
    @classmethod
    def _hhmm(cls, value: str | None) -> str | None:
        if value is not None and not HHMM.match(value):
            raise ValueError("Use 24-hour time like 09:00.")
        return value

    @model_validator(mode="after")
    def _check(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to change.")
        if ("start" in self.model_fields_set) != ("end" in self.model_fields_set):
            raise ValueError("Give both the start and end time.")
        if self.start and self.end and self.start >= self.end:
            raise ValueError("The start time must be before the end time.")
        return self


# ----- emails and audit -----


class EmailLogOut(BaseModel):
    id: int
    request_id: int | None
    event: str
    recipient: str
    subject: str
    status: Literal["PENDING", "SENT", "FAILED"]
    attempt_count: int
    last_error: str | None
    created_at: datetime
    last_attempt_at: datetime | None
    sent_at: datetime | None


class EmailLogListOut(BaseModel):
    items: list[EmailLogOut]
    total: int
    max_attempts: int


class RetryOut(BaseModel):
    sent: int
    failed: int
    skipped: int


class AdminAuditOut(BaseModel):
    id: int
    actor_email: str
    action: str
    entity: str
    entity_id: str | None
    details: str | None
    created_at: datetime
