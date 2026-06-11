from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Chat, ChatAttachment, ChatMessage

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def upload_root() -> Path:
    root = Path(get_settings().upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


async def save_chat_upload(file: UploadFile) -> tuple[str, int, str, bytes]:
    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Разрешены PDF, изображения, Word и Excel",
        )
    data = await file.read(get_settings().max_chat_file_size + 1)
    if len(data) > get_settings().max_chat_file_size:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Файл больше 10 МБ")
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл пуст")

    suffix = Path(file.filename or "").suffix.lower()[:12]
    storage_name = f"{uuid4().hex}{suffix}"
    (upload_root() / storage_name).write_bytes(data)
    return storage_name, len(data), content_type, data


def attachment_path(attachment: ChatAttachment) -> Path:
    path = (upload_root() / attachment.storage_name).resolve()
    if path.parent != upload_root():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
    return path


def attachment_content_disposition(filename: str) -> str:
    return f"attachment; filename*=UTF-8''{quote(filename)}"


def delete_storage_names(storage_names: list[str]) -> None:
    root = upload_root()
    for storage_name in storage_names:
        path = (root / storage_name).resolve()
        if path.parent == root:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def chat_storage_names(db: Session, chat_id: int) -> list[str]:
    return list(
        db.scalars(
            select(ChatAttachment.storage_name)
            .join(ChatMessage, ChatMessage.id == ChatAttachment.message_id)
            .where(ChatMessage.chat_id == chat_id)
        ).all()
    )


def application_storage_names(db: Session, application_ids: list[int]) -> list[str]:
    if not application_ids:
        return []
    return list(
        db.scalars(
            select(ChatAttachment.storage_name)
            .join(ChatMessage, ChatMessage.id == ChatAttachment.message_id)
            .join(Chat, Chat.id == ChatMessage.chat_id)
            .where(Chat.application_id.in_(application_ids))
        ).all()
    )
