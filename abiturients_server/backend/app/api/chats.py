from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import Application, ApplicationStatus, Chat, ChatAttachment, ChatMessage, EducationDetails, Role, User
from app.schemas.dto import ChatMessageCreate, ChatMessageRead, ChatPageRead, ChatRead
from app.services.chat_files import (
    attachment_path,
    attachment_content_disposition,
    chat_storage_names,
    delete_storage_names,
    save_chat_upload,
)
from app.services.workflow import ADMISSIONS_STATUSES, EDUCATION_STATUSES, add_chat_message, can_view_application

router = APIRouter(prefix="/admin/chats", tags=["Admin chats"])


def ensure_chat_reader(user: User) -> None:
    if user.role not in {
        Role.tech_admin.value,
        Role.admissions_admin.value,
        Role.education_admin.value,
        Role.assistant.value,
        Role.teacher.value,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def visible_chats_query(db: Session, user: User):
    ensure_chat_reader(user)
    query = db.query(Chat).join(Chat.application)
    if user.role in {Role.tech_admin.value, Role.assistant.value}:
        return query
    if user.role == Role.admissions_admin.value:
        return query.filter(
            Application.status.in_(ADMISSIONS_STATUSES | {ApplicationStatus.accepted_by_admissions.value})
        )
    if user.role == Role.education_admin.value:
        return query.filter(Application.status.in_(EDUCATION_STATUSES))
    if user.role == Role.teacher.value:
        return query.join(Application.education_details).filter(EducationDetails.curator_id == user.id)
    return query.filter(False)


@router.get("", response_model=list[ChatRead])
def list_chats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Chat]:
    return (
        visible_chats_query(db, user)
        .options(joinedload(Chat.application))
        .order_by(Chat.updated_at.desc())
        .all()
    )


@router.get("/page", response_model=ChatPageRead)
def list_chats_page(
    search: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = visible_chats_query(db, user)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Application.full_name.ilike(like),
                Application.iin.ilike(like),
                Application.phone.ilike(like),
                Application.email.ilike(like),
            )
        )
    total = query.order_by(None).count()
    items = (
        query.options(joinedload(Chat.application))
        .order_by(Chat.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{chat_id:int}", response_model=ChatRead)
def get_chat(chat_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Chat:
    chat = db.query(Chat).options(joinedload(Chat.application)).filter(Chat.id == chat_id).first()
    if not chat or not can_view_application(user, chat.application):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat


@router.get("/{chat_id:int}/messages", response_model=list[ChatMessageRead])
def get_chat_messages(
    chat_id: int,
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessage]:
    chat = get_chat(chat_id, user, db)
    query = (
        db.query(ChatMessage)
        .options(selectinload(ChatMessage.attachments))
        .filter(ChatMessage.chat_id == chat.id)
    )
    if limit is None:
        return query.order_by(ChatMessage.created_at, ChatMessage.id).all()
    messages = (
        query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


@router.post("/{chat_id:int}/messages", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
def send_chat_message(
    chat_id: int,
    payload: ChatMessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatMessage:
    chat = get_chat(chat_id, user, db)
    message = add_chat_message(db, chat, payload.message, sender_type=user.role, sender_user_id=user.id)
    db.commit()
    db.refresh(message)
    return message


@router.post("/{chat_id:int}/attachments", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
async def send_chat_attachment(
    chat_id: int,
    file: UploadFile = File(...),
    message: str = Form(default=""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatMessage:
    if user.role not in {Role.tech_admin.value, Role.admissions_admin.value, Role.assistant.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    chat = get_chat(chat_id, user, db)
    storage_name, size, content_type, content = await save_chat_upload(file)
    try:
        item = add_chat_message(
            db,
            chat,
            message.strip() or file.filename or "Документ",
            sender_type=user.role,
            sender_user_id=user.id,
        )
        db.add(
            ChatAttachment(
                message_id=item.id,
                storage_name=storage_name,
                original_name=Path(file.filename or "document").name[:255],
                content_type=content_type,
                size=size,
                content=content,
            )
        )
        db.commit()
        return (
            db.query(ChatMessage)
            .options(selectinload(ChatMessage.attachments))
            .filter(ChatMessage.id == item.id)
            .one()
        )
    except Exception:
        db.rollback()
        delete_storage_names([storage_name])
        raise


@router.get("/attachments/{attachment_id}")
def download_chat_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if user.role not in {Role.tech_admin.value, Role.admissions_admin.value, Role.assistant.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    attachment = (
        db.query(ChatAttachment)
        .join(ChatAttachment.message)
        .join(ChatMessage.chat)
        .options(joinedload(ChatAttachment.message).joinedload(ChatMessage.chat).joinedload(Chat.application))
        .filter(ChatAttachment.id == attachment_id)
        .first()
    )
    if not attachment or not can_view_application(user, attachment.message.chat.application):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
    path = attachment_path(attachment)
    content = path.read_bytes() if path.exists() else attachment.content
    return Response(
        content=content,
        media_type=attachment.content_type,
        headers={"Content-Disposition": attachment_content_disposition(attachment.original_name)},
    )


@router.delete("/{chat_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if user.role != Role.tech_admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only technical administrator can delete chats")
    chat = db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    storage_names = chat_storage_names(db, chat.id)
    db.delete(chat)
    db.commit()
    delete_storage_names(storage_names)
