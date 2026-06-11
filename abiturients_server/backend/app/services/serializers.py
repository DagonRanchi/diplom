from datetime import UTC, datetime, timedelta

from app.models import Application
from app.schemas.dto import ApplicationRead


def serialize_application(app: Application) -> ApplicationRead:
    payload = ApplicationRead.model_validate(app)
    contest_completed_at = app.contest_profile.completed_at if app.contest_profile else None
    if contest_completed_at is not None and contest_completed_at.tzinfo is None:
        contest_completed_at = contest_completed_at.replace(tzinfo=UTC)
    contest_visible = bool(
        app.contest_profile
        and (
            contest_completed_at is None
            or contest_completed_at + timedelta(hours=48) > datetime.now(UTC)
        )
    )
    return payload.model_copy(
        update={
            "folder_id": app.folder_item.folder_id if app.folder_item else None,
            "chat_id": app.chat.id if app.chat else None,
            "contest_visible": contest_visible,
        }
    )
