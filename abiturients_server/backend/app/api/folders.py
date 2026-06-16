from collections import defaultdict
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import Application, EducationDetails, Folder, FolderItem, Role, User
from app.schemas.dto import BulkMoveRequest, FolderCreate, FolderItemCreate, FolderRead, FolderTreeNode, FolderUpdate
from app.services.chat_files import application_storage_names, delete_storage_names
from app.services.workflow import get_visible_application_or_404, move_application_to_folder

router = APIRouter(prefix="/folders", tags=["Folders"])


def ensure_folder_operator(user: User) -> None:
    if user.role not in {Role.tech_admin.value, Role.admissions_admin.value, Role.education_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def ensure_tech_admin(user: User) -> None:
    if user.role != Role.tech_admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only technical administrator can delete students")


def ensure_group_manager(user: User) -> None:
    if user.role not in {Role.education_admin.value, Role.tech_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Группами управляет учебная часть")


def is_groups_root(folder: Folder | None) -> bool:
    return bool(folder and folder.name == "Группы" and folder.parent_id is None)


def folder_item_totals(db: Session) -> dict[int, int]:
    rows = db.execute(select(Folder.id, Folder.parent_id)).all()
    direct_counts = dict(
        db.execute(
            select(FolderItem.folder_id, func.count(FolderItem.id))
            .group_by(FolderItem.folder_id)
        ).all()
    )
    children_by_parent: dict[int | None, list[int]] = defaultdict(list)
    for folder_id, parent_id in rows:
        children_by_parent[parent_id].append(folder_id)

    @lru_cache(maxsize=None)
    def total_for(folder_id: int) -> int:
        return int(direct_counts.get(folder_id, 0)) + sum(total_for(child_id) for child_id in children_by_parent[folder_id])

    return {folder_id: total_for(folder_id) for folder_id, _ in rows}


def build_folder_tree(folders: list[Folder], item_counts: dict[int, int], parent_id: int | None = None) -> list[FolderTreeNode]:
    children_by_parent: dict[int | None, list[Folder]] = defaultdict(list)
    for folder in folders:
        children_by_parent[folder.parent_id].append(folder)

    def build(current_parent_id: int | None) -> list[FolderTreeNode]:
        nodes = []
        for folder in sorted(children_by_parent[current_parent_id], key=lambda item: item.name):
            nodes.append(node_from_folder(folder, item_counts, build(folder.id)))
        return nodes

    return build(parent_id)


def node_from_folder(folder: Folder, item_counts: dict[int, int], children: list[FolderTreeNode] | None = None) -> FolderTreeNode:
    return FolderTreeNode(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        owner_scope=folder.owner_scope,
        role_scope=folder.role_scope,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
        item_count=item_counts.get(folder.id, 0),
        children=children or [],
    )


def group_name_for_folder(folder: Folder) -> str | None:
    if is_groups_root(folder.parent):
        return folder.name
    return None


def sync_application_group(db: Session, application_id: int, folder: Folder) -> None:
    group_name = group_name_for_folder(folder)
    if not group_name:
        return
    details = db.scalar(select(EducationDetails).where(EducationDetails.application_id == application_id))
    if details:
        details.group_number = group_name


@router.get("/tree", response_model=list[FolderTreeNode])
def folder_tree(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[FolderTreeNode]:
    if user.role == Role.assistant.value:
        return []
    folders = list(db.scalars(select(Folder)).all())
    return build_folder_tree(folders, folder_item_totals(db))


@router.post("", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def create_folder(payload: FolderCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Folder:
    ensure_folder_operator(user)
    parent = db.get(Folder, payload.parent_id) if payload.parent_id else None
    if payload.parent_id and not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent folder not found")
    if is_groups_root(parent) or (payload.parent_id is None and payload.name.strip() == "Группы"):
        ensure_group_manager(user)
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
    target_parent = db.get(Folder, data["parent_id"]) if data.get("parent_id") else None
    resulting_parent_id = data.get("parent_id", folder.parent_id)
    creating_groups_root = data.get("name", folder.name).strip() == "Группы" and resulting_parent_id is None
    if is_groups_root(folder) or group_name_for_folder(folder) or is_groups_root(target_parent) or creating_groups_root:
        ensure_group_manager(user)
    old_name = folder.name
    is_group_folder = bool(folder.parent and folder.parent.name == "Группы" and folder.parent.parent_id is None)
    for field, value in data.items():
        setattr(folder, field, value)
    if is_group_folder and "name" in data and data["name"] != old_name:
        db.query(EducationDetails).filter(EducationDetails.group_number == old_name).update(
            {EducationDetails.group_number: data["name"]},
            synchronize_session=False,
        )
    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    ensure_folder_operator(user)
    folder = db.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    if is_groups_root(folder) or group_name_for_folder(folder):
        ensure_group_manager(user)
    group_name = group_name_for_folder(folder)
    if group_name and db.scalar(
        select(EducationDetails.id).where(EducationDetails.group_number == group_name).limit(1)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Группа назначена студентам и не может быть удалена")
    if folder.children or folder.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder must be empty")
    db.delete(folder)
    db.commit()


@router.delete("/{folder_id}/students", response_model=dict)
def delete_folder_students(
    folder_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    ensure_tech_admin(user)
    folder = db.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    if group_name_for_folder(folder):
        ensure_group_manager(user)

    ids = list(db.scalars(select(FolderItem.application_id).where(FolderItem.folder_id == folder_id)).all())
    storage_names = application_storage_names(db, ids)
    result = db.execute(
        delete(Application)
        .where(Application.id.in_(ids))
        .execution_options(synchronize_session=False)
    )
    db.commit()
    delete_storage_names(storage_names)
    return {"deleted": result.rowcount or 0}


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
    if group_name_for_folder(folder):
        ensure_group_manager(user)
    get_visible_application_or_404(db, payload.application_id, user)
    move_application_to_folder(db, payload.application_id, folder)
    sync_application_group(db, payload.application_id, folder)
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
    if group_name_for_folder(folder):
        ensure_group_manager(user)
    for app_id in payload.application_ids:
        get_visible_application_or_404(db, app_id, user)
        move_application_to_folder(db, app_id, folder)
        sync_application_group(db, app_id, folder)
    db.commit()
    return {"moved": len(payload.application_ids)}
