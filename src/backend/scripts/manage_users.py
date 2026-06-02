"""User management CLI for Guard Proxy.

Subcommands:
    create  — add a new user account
    list    — display all users with optional filters
    update  — modify an existing user by ID or email

Usage (local):
    uv run python scripts/manage_users.py create \\
        --email alice@example.com --password '<password>' --full-name "Alice"
    uv run python scripts/manage_users.py list --role admin --active
    uv run python scripts/manage_users.py update alice@example.com --role admin
    uv run python scripts/manage_users.py update 3 --deactivate

Usage (Docker):
    docker-compose ... exec backend /app/.venv/bin/python scripts/manage_users.py <cmd>
    # or via make:
    make users ARGS="list --json"

See `scripts/manage_users.py <cmd> --help` for per-command details.
"""

import argparse
import json as json_module
import os
import sys

# Add src/backend/ to PYTHONPATH so `app.*` imports resolve when this script
# is run directly (mirrors the same pattern used in seed_admin.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.passwords import hash_password  # noqa: E402
from app.schemas.user import UserCreate, UserResponse, UserUpdate  # noqa: E402

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_COL_WIDTHS = {"id": 4, "email": 35, "name": 25, "role": 7, "active": 7}
_TABLE_HEADER = (
    f"{'ID':<{_COL_WIDTHS['id']}} "
    f"{'Email':<{_COL_WIDTHS['email']}} "
    f"{'Name':<{_COL_WIDTHS['name']}} "
    f"{'Role':<{_COL_WIDTHS['role']}} "
    f"{'Active':<{_COL_WIDTHS['active']}} "
    f"Created"
)
_TABLE_SEP = "-" * 90


def _format_validation_error(exc: ValidationError) -> str:
    """Convert a Pydantic ValidationError to a readable one-line string."""
    parts: list[str] = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"]) if err["loc"] else "value"
        parts.append(f"{field}: {err['msg']}")
    return "; ".join(parts)


def _row(r: UserResponse) -> str:
    active_str = "yes" if r.is_active else "no"
    created = r.created_at.strftime("%Y-%m-%d %H:%M")
    return (
        f"{r.id:<{_COL_WIDTHS['id']}} "
        f"{r.email:<{_COL_WIDTHS['email']}} "
        f"{r.full_name:<{_COL_WIDTHS['name']}} "
        f"{r.role:<{_COL_WIDTHS['role']}} "
        f"{active_str:<{_COL_WIDTHS['active']}} "
        f"{created}"
    )


def _print_user(user: User) -> None:
    """Print a single user as a one-row table."""
    r = UserResponse.model_validate(user)
    print(_TABLE_HEADER)
    print(_TABLE_SEP)
    print(_row(r))


def _print_users(users: list[User], *, as_json: bool = False) -> None:
    """Print a list of users as a table (default) or JSON array."""
    if as_json:
        data = [
            UserResponse.model_validate(u).model_dump(mode="json") for u in users
        ]
        print(json_module.dumps(data, indent=2, default=str))
        return

    print(_TABLE_HEADER)
    print(_TABLE_SEP)
    for u in users:
        print(_row(UserResponse.model_validate(u)))
    print(f"\n{len(users)} user(s) found.")


def _resolve_user(db: Session, identifier: str) -> User | None:
    """Find a user by numeric ID (string of digits) or email address."""
    if identifier.isdigit():
        return db.get(User, int(identifier))
    return db.query(User).filter(User.email == identifier).first()


def _has_other_active_admin(db: Session, exclude_id: int) -> bool:
    """Return True when at least one *other* active admin exists."""
    count: int = (
        db.query(User)
        .filter(
            User.role == UserRole.admin,
            User.is_active.is_(True),
            User.id != exclude_id,
        )
        .count()
    )
    return count > 0


# ---------------------------------------------------------------------------
# Subcommand implementations (accept an injected Session for testability;
# main() opens a real SessionLocal and passes it in)
# ---------------------------------------------------------------------------


def cmd_create(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    role: str,
) -> None:
    """Create a new user account."""
    # Validate via Pydantic (email format, password length, role value).
    try:
        validated = UserCreate(
            email=email,
            password=password,
            full_name=full_name,
            role=UserRole(role),
        )
    except ValueError as exc:
        print(f"Error: role: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValidationError as exc:
        print(f"Error: {_format_validation_error(exc)}", file=sys.stderr)
        sys.exit(1)

    # Pre-check uniqueness to give a friendlier error than IntegrityError.
    if db.query(User).filter(User.email == str(validated.email)).first() is not None:
        print(
            f"Error: email {str(validated.email)!r} is already taken.",
            file=sys.stderr,
        )
        sys.exit(1)

    user = User(
        email=str(validated.email),
        hashed_password=hash_password(validated.password),
        full_name=validated.full_name,
        role=validated.role,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        print(
            f"Error: could not create user — "
            f"database constraint violation: {exc.orig}",
            file=sys.stderr,
        )
        sys.exit(1)

    db.refresh(user)
    print(f"User {str(validated.email)!r} created successfully.")
    _print_user(user)


def cmd_list(
    db: Session,
    *,
    role: str | None = None,
    active_filter: bool | None = None,
    as_json: bool = False,
) -> None:
    """List users with optional filters."""
    query = db.query(User)
    if role is not None:
        try:
            query = query.filter(User.role == UserRole(role))
        except ValueError as exc:
            print(f"Error: role: {exc}", file=sys.stderr)
            sys.exit(1)
    if active_filter is not None:
        query = query.filter(User.is_active == active_filter)
    users: list[User] = query.order_by(User.id).all()
    _print_users(users, as_json=as_json)


def cmd_update(
    db: Session,
    identifier: str,
    *,
    email: str | None = None,
    full_name: str | None = None,
    role: str | None = None,
    password: str | None = None,
    activate: bool | None = None,
) -> None:
    """Update an existing user by ID or email.

    ``activate=True``  → set is_active=True
    ``activate=False`` → set is_active=False (deactivate)
    ``activate=None``  → leave is_active unchanged
    """
    user = _resolve_user(db, identifier)
    if user is None:
        print(f"Error: user {identifier!r} not found.", file=sys.stderr)
        sys.exit(1)

    # Build a dict of only the fields the caller wants to change.
    updates: dict[str, object] = {}
    if email is not None:
        updates["email"] = email
    if full_name is not None:
        updates["full_name"] = full_name
    if role is not None:
        updates["role"] = role
    if password is not None:
        updates["password"] = password
    if activate is not None:
        updates["is_active"] = activate

    if not updates:
        print(
            "Error: specify at least one field to update "
            "(--email, --full-name, --role, --password, --activate, --deactivate).",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate provided fields via Pydantic (email format, password length, etc.).
    try:
        validated = UserUpdate(**updates)
    except ValidationError as exc:
        print(f"Error: {_format_validation_error(exc)}", file=sys.stderr)
        sys.exit(1)

    # Lockout guard: refuse any change that would leave zero active admins.
    would_demote = (
        validated.role is not None
        and validated.role != UserRole.admin
        and user.role == UserRole.admin
    )
    would_deactivate = (
        validated.is_active is False
        and user.is_active
        and user.role == UserRole.admin
    )
    if (would_demote or would_deactivate) and not _has_other_active_admin(
        db, user.id
    ):
        action = "demote" if would_demote else "deactivate"
        print(
            f"Error: cannot {action} {user.email!r} — "
            "they are the last active admin. "
            "Promote or activate another admin first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Apply the validated changes.
    if validated.email is not None:
        user.email = str(validated.email)
    if validated.full_name is not None:
        user.full_name = validated.full_name
    if validated.role is not None:
        user.role = validated.role
    if validated.password is not None:
        user.hashed_password = hash_password(validated.password)
    if validated.is_active is not None:
        user.is_active = validated.is_active

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        print(
            f"Error: could not update user — "
            f"database constraint violation: {exc.orig}",
            file=sys.stderr,
        )
        sys.exit(1)

    db.refresh(user)
    print(f"User {user.email!r} updated successfully.")
    _print_user(user)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manage_users.py",
        description="Guard Proxy — user management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s create --email alice@example.com "
            "--password '<password>' --full-name 'Alice'\n"
            "  %(prog)s list --role admin --active\n"
            "  %(prog)s list --json\n"
            "  %(prog)s update alice@example.com --role viewer\n"
            "  %(prog)s update 3 --deactivate\n"
            "  %(prog)s update 1 --password newpassword12345\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ── create ──────────────────────────────────────────────────────────────
    p_create = sub.add_parser("create", help="Create a new user account")
    p_create.add_argument("--email", required=True, help="Email address (unique)")
    p_create.add_argument("--password", required=True, help="Password (min 12 chars)")
    p_create.add_argument("--full-name", required=True, help="Full display name")
    p_create.add_argument(
        "--role",
        choices=[r.value for r in UserRole],
        default=UserRole.viewer.value,
        help="Role (default: viewer)",
    )

    # ── list ─────────────────────────────────────────────────────────────────
    p_list = sub.add_parser("list", help="List users")
    p_list.add_argument(
        "--role",
        choices=[r.value for r in UserRole],
        help="Filter by role",
    )
    p_list.set_defaults(active_filter=None)
    active_grp = p_list.add_mutually_exclusive_group()
    active_grp.add_argument(
        "--active",
        dest="active_filter",
        action="store_true",
        help="Show only active users",
    )
    active_grp.add_argument(
        "--inactive",
        dest="active_filter",
        action="store_false",
        help="Show only inactive users",
    )
    p_list.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output as a JSON array",
    )

    # ── update ───────────────────────────────────────────────────────────────
    p_update = sub.add_parser(
        "update",
        help="Update an existing user (by ID or email)",
    )
    p_update.add_argument(
        "identifier",
        help="User ID (numeric) or email address",
    )
    p_update.add_argument("--email", help="New email address")
    p_update.add_argument("--full-name", help="New full name")
    p_update.add_argument(
        "--role",
        choices=[r.value for r in UserRole],
        help="New role",
    )
    p_update.add_argument("--password", help="New password (min 12 chars)")
    p_update.set_defaults(activate=None)
    activate_grp = p_update.add_mutually_exclusive_group()
    activate_grp.add_argument(
        "--activate",
        dest="activate",
        action="store_true",
        help="Activate the account",
    )
    activate_grp.add_argument(
        "--deactivate",
        dest="activate",
        action="store_false",
        help="Deactivate the account",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.command == "create":
            cmd_create(
                db,
                email=args.email,
                password=args.password,
                full_name=args.full_name,
                role=args.role,
            )
        elif args.command == "list":
            cmd_list(
                db,
                role=args.role,
                active_filter=args.active_filter,
                as_json=args.as_json,
            )
        elif args.command == "update":
            cmd_update(
                db,
                args.identifier,
                email=args.email,
                full_name=args.full_name,
                role=args.role,
                password=args.password,
                activate=args.activate,
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
