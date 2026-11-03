"""Give or remove a staff role for an email address.

Usage:
    python -m app.db.grant_role someone@iitrpr.ac.in FACILITY
    python -m app.db.grant_role someone@iitrpr.ac.in ACADEMIC --revoke
    python -m app.db.grant_role --list

Roles: FACILITY, ACADEMIC, SPORTS, ESTATE, ADMIN. A person can hold several roles.
The person signs in with Google as usual; the role takes effect on their next page load.
"""

import argparse

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import StaffRole
from app.db.session import create_session_factory
from app.services import roles_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage staff desk roles.")
    parser.add_argument("email", nargs="?", help="Staff member's Google email address")
    parser.add_argument("role", nargs="?", help="FACILITY, ACADEMIC, SPORTS, ESTATE or ADMIN")
    parser.add_argument("--revoke", action="store_true", help="Remove the role instead of granting it")
    parser.add_argument("--list", action="store_true", help="Show all active roles")
    args = parser.parse_args()

    factory = create_session_factory(get_settings())
    try:
        with factory() as db:
            if args.list:
                rows = db.scalars(select(StaffRole).where(StaffRole.active.is_(True)).order_by(StaffRole.email))
                for row in rows:
                    print(f"{row.email:<40} {row.role}")
                return
            if not args.email or not args.role:
                parser.error("give an email and a role, or use --list")
            if args.revoke:
                done = roles_service.revoke(db, args.email, args.role)
                print(f"Removed {args.role.upper()} from {args.email}." if done else "That role wasn't assigned.")
            else:
                roles_service.grant(db, args.email, args.role, assigned_by="grant_role command")
                print(f"Gave {args.role.upper()} to {args.email.lower()}.")
    finally:
        factory.kw["bind"].dispose()


if __name__ == "__main__":
    main()
