from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import Chat, ChatMessage, Role, User
from app.schemas.dto import ChatMessageCreate, ChatMessageRead, ChatRead
from app.services.workflow import add_chat_message, can_view_application

router = APIRouter(prefix="/admin/chats", tags=["Admin chats"])


@router.get("", response_model=list[ChatRead])
def list_chats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Chat]:
    if user.role not in {
        Role.tech_admin.value,
        Role.admissions_admin.value,
        Role.education_admin.value,
        Role.assistant.value,
        Role.teacher.value,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    chats = db.query(Chat).options(joinedload(Chat.application)).order_by(Chat.updated_at.desc()).all()
    return [chat for chat in chats if can_view_application(user, chat.application)]


@router.get("/{chat_id}", response_model=ChatRead)
def get_chat(chat_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Chat:
    chat = db.query(Chat).options(joinedload(Chat.application)).filter(Chat.id == chat_id).first()
    if not chat or not can_view_application(user, chat.application):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat


@router.get("/{chat_id}/messages", response_model=list[ChatMessageRead])
def get_chat_messages(chat_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChatMessage]:
    chat = get_chat(chat_id, user, db)
    return db.query(ChatMessage).filter(ChatMessage.chat_id == chat.id).order_by(ChatMessage.created_at).all()


@router.post("/{chat_id}/messages", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
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
