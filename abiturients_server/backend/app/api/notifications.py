from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import Notification, User
from app.schemas.dto import NotificationRead

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Notification:
    item = db.get(Notification, notification_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    item.is_read = True
    db.commit()
    db.refresh(item)
    return item
