"""Facility catalogue assembly: facilities + currently effective tariffs + slot options."""

from collections import defaultdict
from datetime import UTC, datetime, time

from app.core.errors import AppError
from app.db.models import Facility, SlotWindow, Tariff
from app.repositories.facilities import FacilityRepository
from app.schemas.facility import FacilityOut, SlotOptionOut, TariffOut

CATEGORY_ORDER = {"PRIVATE": 0, "GOVT": 1, "IIT": 2}
UNIT_ORDER = {"FULL_DAY": 0, "HALF_DAY": 1, "PER_DAY": 2, "THREE_HOUR": 3}


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _hhmm(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def select_latest_tariffs(tariffs: list[Tariff]) -> list[Tariff]:
    """Keep the most recently effective tariff per (facility, category, unit).

    The repository already filters to tariffs effective now; if an admin has added a
    newer version alongside an older one, the newer effective_from wins.
    """
    latest: dict[tuple, Tariff] = {}
    for tariff in tariffs:
        key = (tariff.facility_id, tariff.category, tariff.unit)
        current = latest.get(key)
        if current is None or _as_utc(tariff.effective_from) > _as_utc(current.effective_from):
            latest[key] = tariff
    return list(latest.values())


class FacilityService:
    def __init__(self, repo: FacilityRepository) -> None:
        self.repo = repo

    def list_catalogue(self, active: bool | None = True, at: datetime | None = None) -> list[FacilityOut]:
        return self._assemble(self.repo.list_facilities(active=active), at or datetime.now(UTC))

    def get_by_code(self, code: str, at: datetime | None = None) -> FacilityOut:
        facility = self.repo.get_by_code(code)
        if facility is None:
            raise AppError("FACILITY_NOT_FOUND", f"No facility with code '{code}'.", status_code=404)
        return self._assemble([facility], at or datetime.now(UTC))[0]

    def _assemble(self, facilities: list[Facility], at: datetime) -> list[FacilityOut]:
        ids = [f.id for f in facilities]
        if not ids:
            return []

        tariffs_by_facility: dict[int, list[Tariff]] = defaultdict(list)
        for tariff in select_latest_tariffs(self.repo.effective_tariffs_for(ids, at)):
            tariffs_by_facility[tariff.facility_id].append(tariff)

        slots_by_facility: dict[int, list[SlotWindow]] = defaultdict(list)
        for window in self.repo.active_slot_windows_for(ids):
            slots_by_facility[window.facility_id].append(window)

        result = []
        for facility in facilities:
            slot_types = sorted((s.slot_type for s in facility.slot_types), key=lambda u: UNIT_ORDER.get(u, 99))
            tariffs = sorted(
                tariffs_by_facility[facility.id],
                key=lambda t: (UNIT_ORDER.get(t.unit, 99), CATEGORY_ORDER.get(t.category, 99)),
            )
            slots = sorted(
                slots_by_facility[facility.id],
                key=lambda w: (UNIT_ORDER.get(w.slot_type, 99), w.start_time or time.min, w.slot_key),
            )
            result.append(
                FacilityOut(
                    id=str(facility.id),
                    code=facility.code,
                    name=facility.name,
                    group=facility.facility_group,
                    section=facility.section,
                    capacity=facility.capacity,
                    slot_types=slot_types,
                    slot_options=[
                        SlotOptionOut(
                            slot_key=w.slot_key,
                            label=w.label,
                            slot_type=w.slot_type,
                            start=_hhmm(w.start_time),
                            end=_hhmm(w.end_time),
                        )
                        for w in slots
                    ],
                    tariffs=[
                        TariffOut(
                            category=t.category,
                            unit=t.unit,
                            amount=t.amount or 0,  # "No charges" is 0, LLD §5.2
                            display_label=t.display_label,
                        )
                        for t in tariffs
                    ],
                    notes=facility.notes,
                    active=facility.active,
                )
            )
        return result
