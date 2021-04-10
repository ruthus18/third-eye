import datetime as dt

from .config import settings


def localize_dt(datetime: dt.datetime) -> dt.datetime:
    return settings.TIMEZONE.localize(datetime)  # type: ignore
