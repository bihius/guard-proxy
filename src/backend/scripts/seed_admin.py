"""Seed script — creates the first admin user if none exists.

Usage:
    uv run python scripts/seed_admin.py
    uv run python scripts/seed_admin.py --email admin@example.com --password secret

If --email / --password are not provided, the script reads
ADMIN_EMAIL and ADMIN_PASSWORD from the environment (or .env file).

The script is idempotent: if any admin user already exists in the database
(regardless of email), it exits without making any changes.
"""

import argparse
import os
import sys

from dotenv import load_dotenv

# Ładujemy .env zanim cokolwiek zaimportujemy z app.* —
# w przeciwnym razie os.getenv() nie widzi zmiennych z pliku .env,
# a import app.config crashuje jeśli JWT_SECRET_KEY nie jest w środowisku.
load_dotenv()

# Dodajemy katalog nadrzędny (src/backend/) do PYTHONPATH,
# żeby importy "app.*" działały gdy uruchamiamy skrypt bezpośrednio.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402


def seed_admin(email: str, password: str, full_name: str = "Administrator") -> None:
    """Tworzy pierwszego admina jeśli żaden nie istnieje w bazie.

    Sprawdzamy czy istnieje *jakikolwiek* user z rolą admin — nie tylko
    czy podany email jest zajęty. Dzięki temu skrypt jest idempotentny
    i nie tworzy duplikatów adminów przy ponownym uruchomieniu.
    """
    db = SessionLocal()
    try:
        existing_admin = db.query(User).filter(User.role == UserRole.admin).first()
        if existing_admin is not None:
            print(f"Admin user already exists ({existing_admin.email!r}) — skipping.")
            return

        admin = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Admin user {email!r} created successfully.")
    finally:
        db.close()


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

    seed_admin(args.email, args.password, args.full_name)


if __name__ == "__main__":
    main()
