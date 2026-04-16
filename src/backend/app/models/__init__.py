"""SQLAlchemy models imported here so Alembic autogenerate can detect them.

Alembic's env.py does: from app.models import *.
For autogenerate to work, EVERY model must be imported here.
Without this, Alembic generates an empty migration (it does not see tables).
"""

from app.models.log import Log, LogAction, LogSeverity
from app.models.policy import Policy
from app.models.rule_override import RuleAction, RuleOverride
from app.models.user import User, UserRole
from app.models.vhost import VHost

__all__ = [
    "User",
    "UserRole",
    "Policy",
    "VHost",
    "Log",
    "LogAction",
    "LogSeverity",
    "RuleOverride",
    "RuleAction",
]
