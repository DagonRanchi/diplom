from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Role, User
from app.schemas.dto import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserRead])
def list_users(
    role: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[User]:
    if user.role not in {Role.tech_admin.value, Role.document_admin.value, Role.hr_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if user.role != Role.tech_admin.value:
        query = query.filter(User.is_active.is_(True))
    return query.order_by(User.full_name).all()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if user.role != Role.tech_admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only tech admin can create users")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    new_user = User(
        full_name=payload.full_name,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        role=payload.role.value,
        is_active=payload.is_active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if user.role != Role.tech_admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only tech admin can update users")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data and data["password"]:
        target.password_hash = hash_password(data.pop("password"))
    for field, value in data.items():
        setattr(target, field, value.value if hasattr(value, "value") else value)
    db.commit()
    db.refresh(target)
    return target


@router.patch("/{user_id}/deactivate", response_model=UserRead)
def deactivate_user(user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if user.role != Role.tech_admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only tech admin can deactivate users")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    target.is_active = False
    db.commit()
    db.refresh(target)
    return target
