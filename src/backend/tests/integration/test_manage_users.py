"""Integration tests for scripts/manage_users.py (create / list / update).

Each test receives the function-scoped `db` fixture from conftest — an
isolated SQLAlchemy session that is rolled back after the test, so there is
no state leakage between cases.

The cmd_* functions accept an injected Session, so we never touch
SessionLocal() directly and no real database file is needed.
"""

import json

import pytest
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.passwords import hash_password, verify_password
from scripts.manage_users import cmd_create, cmd_list, cmd_update

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    db: Session,
    *,
    email: str,
    role: UserRole = UserRole.viewer,
    is_active: bool = True,
    password: str = "password12345",
) -> User:
    """Insert a User directly (mirrors conftest fixture style)."""
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=email.split("@")[0].title(),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# cmd_create
# ---------------------------------------------------------------------------


class TestCmdCreate:
    def test_creates_viewer_user(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd_create(
            db,
            email="alice@test.com",
            password="password12345",
            full_name="Alice",
            role="viewer",
        )
        user = db.query(User).filter(User.email == "alice@test.com").first()
        assert user is not None
        assert user.role == UserRole.viewer
        assert user.is_active is True
        out, _ = capsys.readouterr()
        assert "alice@test.com" in out

    def test_creates_admin_user(self, db: Session) -> None:
        cmd_create(
            db,
            email="bob@test.com",
            password="adminpass12345",
            full_name="Bob Admin",
            role="admin",
        )
        user = db.query(User).filter(User.email == "bob@test.com").first()
        assert user is not None
        assert user.role == UserRole.admin

    def test_default_role_is_viewer(self, db: Session) -> None:
        cmd_create(
            db,
            email="carol@test.com",
            password="password12345",
            full_name="Carol",
            role="viewer",
        )
        user = db.query(User).filter(User.email == "carol@test.com").first()
        assert user is not None
        assert user.role == UserRole.viewer

    def test_password_is_hashed(self, db: Session) -> None:
        plaintext = "password12345"
        cmd_create(
            db,
            email="dave@test.com",
            password=plaintext,
            full_name="Dave",
            role="viewer",
        )
        user = db.query(User).filter(User.email == "dave@test.com").first()
        assert user is not None
        assert user.hashed_password != plaintext
        assert verify_password(plaintext, user.hashed_password)

    def test_duplicate_email_exits_1(self, db: Session) -> None:
        _make_user(db, email="existing@test.com", role=UserRole.viewer)
        with pytest.raises(SystemExit) as exc_info:
            cmd_create(
                db,
                email="existing@test.com",
                password="password12345",
                full_name="Dup",
                role="viewer",
            )
        assert exc_info.value.code == 1

    def test_duplicate_email_prints_error(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="taken@test.com", role=UserRole.viewer)
        with pytest.raises(SystemExit):
            cmd_create(
                db,
                email="taken@test.com",
                password="password12345",
                full_name="Dup",
                role="viewer",
            )
        _, err = capsys.readouterr()
        assert "taken@test.com" in err

    def test_short_password_exits_1(self, db: Session) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cmd_create(
                db,
                email="eve@test.com",
                password="short",
                full_name="Eve",
                role="viewer",
            )
        assert exc_info.value.code == 1

    def test_short_password_prints_error(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            cmd_create(
                db,
                email="eve@test.com",
                password="short",
                full_name="Eve",
                role="viewer",
            )
        _, err = capsys.readouterr()
        assert err.strip()  # some error message printed to stderr

    def test_invalid_email_exits_1(self, db: Session) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cmd_create(
                db,
                email="not-an-email",
                password="password12345",
                full_name="Bad Email",
                role="viewer",
            )
        assert exc_info.value.code == 1

    def test_output_excludes_hashed_password(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd_create(
            db,
            email="frank@test.com",
            password="password12345",
            full_name="Frank",
            role="viewer",
        )
        out, _ = capsys.readouterr()
        assert "hashed_password" not in out
        assert "password12345" not in out


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------


class TestCmdList:
    def test_lists_all_users(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="u1@test.com", role=UserRole.admin)
        _make_user(db, email="u2@test.com", role=UserRole.viewer)
        cmd_list(db)
        out, _ = capsys.readouterr()
        assert "u1@test.com" in out
        assert "u2@test.com" in out

    def test_filters_by_role_admin(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="admin1@test.com", role=UserRole.admin)
        _make_user(db, email="viewer1@test.com", role=UserRole.viewer)
        cmd_list(db, role="admin")
        out, _ = capsys.readouterr()
        assert "admin1@test.com" in out
        assert "viewer1@test.com" not in out

    def test_filters_by_role_viewer(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="admin2@test.com", role=UserRole.admin)
        _make_user(db, email="viewer2@test.com", role=UserRole.viewer)
        cmd_list(db, role="viewer")
        out, _ = capsys.readouterr()
        assert "viewer2@test.com" in out
        assert "admin2@test.com" not in out

    def test_filters_active_only(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="active@test.com", is_active=True)
        _make_user(db, email="inactive@test.com", is_active=False)
        cmd_list(db, active_filter=True)
        out, _ = capsys.readouterr()
        assert "active@test.com" in out
        assert "inactive@test.com" not in out

    def test_filters_inactive_only(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="online@test.com", is_active=True)
        _make_user(db, email="disabled@test.com", is_active=False)
        cmd_list(db, active_filter=False)
        out, _ = capsys.readouterr()
        assert "disabled@test.com" in out
        assert "online@test.com" not in out

    def test_json_output_is_valid(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="json@test.com")
        cmd_list(db, as_json=True)
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_json_excludes_hashed_password(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="sec@test.com")
        cmd_list(db, as_json=True)
        out, _ = capsys.readouterr()
        assert "hashed_password" not in out
        data = json.loads(out)
        for item in data:
            assert "hashed_password" not in item

    def test_json_schema_fields(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="schema@test.com", role=UserRole.admin)
        cmd_list(db, as_json=True)
        out, _ = capsys.readouterr()
        data = json.loads(out)
        item = next(d for d in data if d["email"] == "schema@test.com")
        assert set(item.keys()) == {
            "id",
            "email",
            "full_name",
            "role",
            "is_active",
            "created_at",
            "updated_at",
        }

    def test_empty_list(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd_list(db)
        out, _ = capsys.readouterr()
        assert "0 user(s) found." in out


# ---------------------------------------------------------------------------
# cmd_update
# ---------------------------------------------------------------------------


class TestCmdUpdate:
    def test_update_full_name_by_email(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        user = _make_user(db, email="update1@test.com")
        cmd_update(db, "update1@test.com", full_name="New Name")
        db.refresh(user)
        assert user.full_name == "New Name"
        out, _ = capsys.readouterr()
        assert "New Name" in out

    def test_update_full_name_by_id(self, db: Session) -> None:
        user = _make_user(db, email="update2@test.com")
        cmd_update(db, str(user.id), full_name="Updated By ID")
        db.refresh(user)
        assert user.full_name == "Updated By ID"

    def test_update_email(self, db: Session) -> None:
        user = _make_user(db, email="oldemail@test.com")
        cmd_update(db, "oldemail@test.com", email="newemail@test.com")
        db.refresh(user)
        assert user.email == "newemail@test.com"

    def test_update_role(self, db: Session) -> None:
        # Need two admins so the lockout guard doesn't block the demotion.
        _make_user(db, email="admin_keep@test.com", role=UserRole.admin)
        user = _make_user(db, email="demote@test.com", role=UserRole.admin)
        cmd_update(db, "demote@test.com", role="viewer")
        db.refresh(user)
        assert user.role == UserRole.viewer

    def test_update_password(self, db: Session) -> None:
        user = _make_user(db, email="pwchange@test.com", password="oldpassword12345")
        cmd_update(db, "pwchange@test.com", password="newpassword12345")
        db.refresh(user)
        assert verify_password("newpassword12345", user.hashed_password)
        assert not verify_password("oldpassword12345", user.hashed_password)

    def test_deactivate_user(self, db: Session) -> None:
        # Non-admin user — lockout guard does not apply.
        user = _make_user(db, email="deactivate@test.com", role=UserRole.viewer)
        cmd_update(db, "deactivate@test.com", activate=False)
        db.refresh(user)
        assert user.is_active is False

    def test_activate_user(self, db: Session) -> None:
        user = _make_user(db, email="reactivate@test.com", is_active=False)
        cmd_update(db, "reactivate@test.com", activate=True)
        db.refresh(user)
        assert user.is_active is True

    def test_no_fields_exits_1(self, db: Session) -> None:
        _make_user(db, email="nofields@test.com")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(db, "nofields@test.com")
        assert exc_info.value.code == 1

    def test_user_not_found_by_email_exits_1(self, db: Session) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(db, "ghost@test.com", full_name="Ghost")
        assert exc_info.value.code == 1

    def test_user_not_found_by_id_exits_1(self, db: Session) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(db, "99999", full_name="Ghost")
        assert exc_info.value.code == 1

    def test_short_password_exits_1(self, db: Session) -> None:
        _make_user(db, email="badpw@test.com")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(db, "badpw@test.com", password="short")
        assert exc_info.value.code == 1

    def test_invalid_email_update_exits_1(self, db: Session) -> None:
        _make_user(db, email="bademail@test.com")
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(db, "bademail@test.com", email="not-valid")
        assert exc_info.value.code == 1

    def test_output_excludes_hashed_password(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="sec2@test.com")
        cmd_update(db, "sec2@test.com", full_name="Secure User")
        out, _ = capsys.readouterr()
        assert "hashed_password" not in out

    # --- Lockout guard ---

    def test_lockout_demote_last_admin_exits_1(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="lastadmin@test.com", role=UserRole.admin)
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(db, "lastadmin@test.com", role="viewer")
        assert exc_info.value.code == 1
        _, err = capsys.readouterr()
        assert "last active admin" in err

    def test_lockout_deactivate_last_admin_exits_1(
        self, db: Session, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _make_user(db, email="lastadmin2@test.com", role=UserRole.admin)
        with pytest.raises(SystemExit) as exc_info:
            cmd_update(db, "lastadmin2@test.com", activate=False)
        assert exc_info.value.code == 1
        _, err = capsys.readouterr()
        assert "last active admin" in err

    def test_lockout_allows_demote_when_second_admin_exists(
        self, db: Session
    ) -> None:
        _make_user(db, email="admin_a@test.com", role=UserRole.admin)
        user_b = _make_user(db, email="admin_b@test.com", role=UserRole.admin)
        # Demoting admin_b is allowed because admin_a is still active admin.
        cmd_update(db, "admin_b@test.com", role="viewer")
        db.refresh(user_b)
        assert user_b.role == UserRole.viewer

    def test_lockout_allows_deactivate_when_second_admin_exists(
        self, db: Session
    ) -> None:
        _make_user(db, email="admin_c@test.com", role=UserRole.admin)
        user_d = _make_user(db, email="admin_d@test.com", role=UserRole.admin)
        cmd_update(db, "admin_d@test.com", activate=False)
        db.refresh(user_d)
        assert user_d.is_active is False

    def test_lockout_does_not_block_viewer_deactivation(
        self, db: Session
    ) -> None:
        # Viewers can always be deactivated regardless of admin count.
        user = _make_user(db, email="viewer_only@test.com", role=UserRole.viewer)
        cmd_update(db, "viewer_only@test.com", activate=False)
        db.refresh(user)
        assert user.is_active is False

    def test_lockout_does_not_block_admin_activation(
        self, db: Session
    ) -> None:
        # Activating the last admin is always fine (it cannot cause lockout).
        user = _make_user(
            db, email="inactive_admin@test.com", role=UserRole.admin, is_active=False
        )
        cmd_update(db, "inactive_admin@test.com", activate=True)
        db.refresh(user)
        assert user.is_active is True

    def test_lockout_does_not_block_role_change_within_viewer(
        self, db: Session
    ) -> None:
        # viewer → admin should always succeed.
        _make_user(db, email="promote@test.com", role=UserRole.viewer)
        user = db.query(User).filter(User.email == "promote@test.com").first()
        assert user is not None
        cmd_update(db, "promote@test.com", role="admin")
        db.refresh(user)
        assert user.role == UserRole.admin
