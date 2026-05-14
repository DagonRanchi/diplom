from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


def is_tech_admin(user: User) -> bool:
    return user.role == Role.tech_admin.value


def require_roles(*roles: Role | str, allow_tech: bool = True) -> Callable[[User], User]:
    allowed = {role.value if isinstance(role, Role) else role for role in roles}

    def dependency(user: User = Depends(get_current_user)) -> User:
        if allow_tech and is_tech_admin(user):
            return user
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        return user

    return dependency


def assert_role(user: User, *roles: Role | str, allow_tech: bool = True) -> None:
    allowed = {role.value if isinstance(role, Role) else role for role in roles}
    if allow_tech and is_tech_admin(user):
        return
    if user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
