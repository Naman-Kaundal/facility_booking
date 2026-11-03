from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.facility import Category


class MeOut(BaseModel):
    id: int
    email: str
    name: str
    rate_category: Category | None
    is_iit: bool
    # True for an external user who hasn't picked GOVT/PRIVATE yet.
    needs_category: bool
    # Send this back in the X-CSRF-Token header on every POST/PUT/PATCH/DELETE.
    csrf_token: str
    # Week 3: active staff desk roles (FACILITY, ACADEMIC, SPORTS, ESTATE, ADMIN). Empty for requesters.
    roles: list[str] = []


class RateCategoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # IIT is deliberately not accepted here: only the verified email rule can grant it.
    rate_category: Literal["GOVT", "PRIVATE"]


class AuthConfigOut(BaseModel):
    google_enabled: bool
    dev_login_enabled: bool


class DevLoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str = Field(default="", max_length=200)
