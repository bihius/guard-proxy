"""Seed script — creates the first admin user if none exists.

Usage:
    uv run python scripts/seed_admin.py
    uv run python scripts/seed_admin.py --email admin@example.com \\
        --password supersecretpw

If --email / --password are not provided, the script reads
ADMIN_EMAIL and ADMIN_PASSWORD from the environment (or `.env` file).

The script is idempotent: if any admin user already exists in the database
(regardless of email), it exits without making any changes.

The password must be at least 12 characters long.
"""

import argparse
import os
import sys

# Add the backend root (src/backend/) to PYTHONPATH so `app.*` imports work when
# running this script directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.passwords import hash_password  # noqa: E402


def seed_admin(email: str, password: str, full_name: str = "Administrator") -> None:
    """Tworzy pierwszego admina jeśli żaden nie istnieje w bazie.

    Sprawdzamy czy istnieje *jakikolwiek* user z rolą admin — nie tylko
    czy podany email jest zajęty. Dzięki temu skrypt jest idempotentny
    i nie tworzy duplikatów adminów przy ponownym uruchomieniu.

    Przed insertem sprawdzamy też czy podany email nie jest już zajęty
    przez innego usera — unikamy IntegrityError na unikalnym kolumnie email.
    """
    db = SessionLocal()
    try:
        existing_admin = db.query(User).filter(User.role == UserRole.admin).first()
        if existing_admin is not None:
            print(f"Admin user already exists ({existing_admin.email!r}) — skipping.")
            return

        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email is not None:
            print(
                f"Error: email {email!r} is already taken by a non-admin user. "
                "Provide a different email or promote that user manually.",
                file=sys.stderr,
            )
            sys.exit(1)

        admin = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            print(
                f"Error: could not create admin user — "
                f"database constraint violation: {exc.orig}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Admin user {email!r} created successfully.")
    finally:
        db.close()


MIN_PASSWORD_LENGTH = 12


def main() -> None:
    parser = argparse.ArgumentParser(description="Create initial admin user")
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument(
        "--full-name", default=os.getenv("ADMIN_FULL_NAME", "Administrator")
    )
    args = parser.parse_args()

    if not args.email or not args.password:
        print(
            "Error: provide --email and --password, "
            "or set ADMIN_EMAIL and ADMIN_PASSWORD in environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    if len(args.password) < MIN_PASSWORD_LENGTH:
        print(
            f"Error: password must be at least {MIN_PASSWORD_LENGTH} characters long.",
            file=sys.stderr,
        )
        sys.exit(1)

    seed_admin(args.email, args.password, args.full_name)


if __name__ == "__main__":
    main()
