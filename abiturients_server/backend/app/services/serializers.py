from app.models import Application
from app.schemas.dto import ApplicationRead


def serialize_application(app: Application) -> ApplicationRead:
    payload = ApplicationRead.model_validate(app)
    return payload.model_copy(
        update={
            "folder_id": app.folder_item.folder_id if app.folder_item else None,
            "chat_id": app.chat.id if app.chat else None,
        }
    )
