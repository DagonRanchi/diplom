from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import Folder, FolderItem, Role, User
from app.schemas.dto import BulkMoveRequest, FolderCreate, FolderItemCreate, FolderRead, FolderTreeNode, FolderUpdate
from app.services.workflow import get_visible_application_or_404, move_application_to_folder

router = APIRouter(prefix="/folders", tags=["Folders"])


def ensure_folder_operator(user: User) -> None:
    if user.role not in {Role.tech_admin.value, Role.admissions_admin.value, Role.education_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def node_from_folder(folder: Folder) -> FolderTreeNode:
    return FolderTreeNode(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        owner_scope=folder.owner_scope,
        role_scope=folder.role_scope,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
        item_count=len(folder.items),
        children=[node_from_folder(child) for child in sorted(folder.children, key=lambda item: item.name)],
    )


@router.get("/tree", response_model=list[FolderTreeNode])
def folder_tree(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[FolderTreeNode]:
    if user.role == Role.assistant.value:
        return []
    folders = (
        db.scalars(
            select(Folder)
            .where(Folder.parent_id.is_(None))
            .options(selectinload(Folder.children).selectinload(Folder.children), selectinload(Folder.items))
            .order_by(Folder.name)
        )
        .unique()
        .all()
    )
    return [node_from_folder(folder) for folder in folders]


@router.post("", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def create_folder(payload: FolderCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Folder:
    ensure_folder_operator(user)
    if payload.parent_id and not db.get(Folder, payload.parent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent folder not found")
    folder = Folder(
        name=payload.name,
        parent_id=payload.parent_id,
        owner_scope=payload.owner_scope,
        role_scope=payload.role_scope,
        created_by=user.id,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.patch("/{folder_id}", response_model=FolderRead)
def update_folder(folder_id: int, payload: FolderUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Folder:
    ensure_folder_operator(user)
    folder = db.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data and data["parent_id"] == folder.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder cannot be parent of itself")
    for field, value in data.items():
        setattr(folder, field, value)
    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    ensure_folder_operator(user)
    folder = db.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    if folder.children or folder.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder must be empty")
    db.delete(folder)
    db.commit()


@router.post("/{folder_id}/items", response_model=FolderRead)
def add_folder_item(
    folder_id: int,
    payload: FolderItemCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Folder:
    ensure_folder_operator(user)
    folder = db.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    get_visible_application_or_404(db, payload.application_id, user)
    move_application_to_folder(db, payload.application_id, folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/{folder_id}/items/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_folder_item(folder_id: int, application_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    ensure_folder_operator(user)
    item = db.scalar(select(FolderItem).where(FolderItem.folder_id == folder_id, FolderItem.application_id == application_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder item not found")
    get_visible_application_or_404(db, application_id, user)
    db.delete(item)
    db.commit()


@router.post("/move-items", response_model=dict)
def move_items(payload: BulkMoveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, int]:
    ensure_folder_operator(user)
    folder = db.get(Folder, payload.target_folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    for app_id in payload.application_ids:
        get_visible_application_or_404(db, app_id, user)
        move_application_to_folder(db, app_id, folder)
    db.commit()
    return {"moved": len(payload.application_ids)}
