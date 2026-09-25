from datetime import datetime, timezone


def to_naive_utc(value: datetime) -> datetime:
    """Convert an API filter datetime to the UTC convention used by MySQL."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
