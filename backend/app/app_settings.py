"""Read/write app-wide settings stored in app_setting."""
from sqlalchemy.orm import Session

from .models import AppSetting

REGISTRATION_ENABLED_KEY = "registration_enabled"


def is_registration_enabled(db: Session) -> bool:
    row = db.get(AppSetting, REGISTRATION_ENABLED_KEY)
    if row is None or not isinstance(row.value, dict):
        return True
    return row.value.get("enabled", True) is not False


def set_registration_enabled(db: Session, enabled: bool) -> None:
    row = db.get(AppSetting, REGISTRATION_ENABLED_KEY)
    if row is None:
        db.add(AppSetting(key=REGISTRATION_ENABLED_KEY, value={"enabled": enabled}))
    else:
        row.value = {"enabled": enabled}
