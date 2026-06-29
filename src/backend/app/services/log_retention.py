"""Log retention — delete persisted log events older than the configured threshold."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.log import Log


def purge_logs_older_than(db: Session, retention_days: int) -> int:
    """Delete log rows whose event_at is older than retention_days.

    Returns the number of rows removed.
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=retention_days)
    deleted = (
        db.query(Log)
        .filter(Log.event_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
