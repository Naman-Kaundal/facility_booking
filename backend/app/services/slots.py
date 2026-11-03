"""Slot overlap rules (LLD §6.2), shared by draft validation now and booking conflicts in Week 3."""

from app.db.models import SlotWindow


def slots_overlap(a: SlotWindow, b: SlotWindow) -> bool:
    """Two slots of the same facility on the same date overlap when their times intersect.

    A slot without times (full day / per day) covers the whole day, so it overlaps every
    other slot. First and second half of the Auditorium don't overlap each other.
    """
    if a.start_time is None or b.start_time is None:
        return True
    return a.start_time < b.end_time and b.start_time < a.end_time
