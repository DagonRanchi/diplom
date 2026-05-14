from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AdmissionDetails,
    Application,
    ApplicationStatus,
    Chat,
    ChatMessage,
    EducationDetails,
    Folder,
    FolderItem,
    Notification,
    Rejection,
    Role,
    User,
)


ADMISSIONS_STATUSES = {
    ApplicationStatus.new.value,
    ApplicationStatus.in_admissions_review.value,
    ApplicationStatus.archived_by_admissions.value,
    ApplicationStatus.rejected.value,
}
EDUCATION_STATUSES = {
    ApplicationStatus.accepted_by_admissions.value,
    ApplicationStatus.education_review.value,
    ApplicationStatus.enrolled.value,
    ApplicationStatus.completed.value,
}


def query_applications_for_user(db: Session, user: User):
    query = (
        db.query(Application)
        .options(
            joinedload(Application.admission_details),
            joinedload(Application.education_details),
            joinedload(Application.folder_item),
            joinedload(Application.chat),
        )
    )
    if user.role == Role.tech_admin.value:
        return query
    if user.role == Role.admissions_admin.value:
        return query.filter(Application.status.in_(ADMISSIONS_STATUSES | {ApplicationStatus.accepted_by_admissions.value}))
    if user.role == Role.education_admin.value:
        return query.filter(Application.status.in_(EDUCATION_STATUSES))
    if user.role == Role.teacher.value:
        return query.join(EducationDetails).filter(EducationDetails.curator_id == user.id)
    if user.role == Role.assistant.value:
        return query
    return query.filter(False)


def can_view_application(user: User, app: Application) -> bool:
    if user.role in {Role.tech_admin.value, Role.assistant.value}:
        return True
    if user.role == Role.admissions_admin.value:
        return app.status in ADMISSIONS_STATUSES or app.status == ApplicationStatus.accepted_by_admissions.value
    if user.role == Role.education_admin.value:
        return app.status in EDUCATION_STATUSES
    if user.role == Role.teacher.value:
        return bool(app.education_details and app.education_details.curator_id == user.id)
    return False


def get_visible_application_or_404(db: Session, app_id: int, user: User) -> Application:
    app = (
        db.query(Application)
        .options(
            joinedload(Application.admission_details),
            joinedload(Application.education_details),
            joinedload(Application.folder_item),
            joinedload(Application.chat),
        )
        .filter(Application.id == app_id)
        .first()
    )
    if not app or not can_view_application(user, app):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


def get_or_create_admission_details(db: Session, app: Application) -> AdmissionDetails:
    if app.admission_details:
        return app.admission_details
    details = AdmissionDetails(application_id=app.id)
    db.add(details)
    db.flush()
    return details


def get_or_create_education_details(db: Session, app: Application) -> EducationDetails:
    if app.education_details:
        return app.education_details
    details = EducationDetails(application_id=app.id)
    db.add(details)
    db.flush()
    return details


def get_or_create_chat(db: Session, app: Application) -> Chat:
    if app.chat:
        return app.chat
    chat = Chat(application_id=app.id)
    db.add(chat)
    db.flush()
    return chat


def notify_roles(
    db: Session,
    roles: list[Role | str],
    title: str,
    message: str,
    notification_type: str,
    application_id: int | None = None,
) -> None:
    role_values = [role.value if isinstance(role, Role) else role for role in roles]
    users = db.scalars(select(User).where(User.role.in_(role_values), User.is_active.is_(True))).all()
    for user in users:
        db.add(
            Notification(
                user_id=user.id,
                type=notification_type,
                title=title,
                message=message,
                application_id=application_id,
            )
        )


def notify_user(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    application_id: int | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            application_id=application_id,
        )
    )


def folder_by_path(db: Session, names: list[str]) -> Folder | None:
    parent_id = None
    current = None
    for name in names:
        parent_filter = Folder.parent_id.is_(None) if parent_id is None else Folder.parent_id == parent_id
        current = db.scalar(select(Folder).where(Folder.name == name, parent_filter))
        if not current:
            return None
        parent_id = current.id
    return current


def ensure_folder_path(db: Session, names: list[str], role_scope: str | None = None, created_by: int | None = None) -> Folder:
    parent_id = None
    current = None
    for name in names:
        parent_filter = Folder.parent_id.is_(None) if parent_id is None else Folder.parent_id == parent_id
        current = db.scalar(select(Folder).where(Folder.name == name, parent_filter))
        if not current:
            current = Folder(name=name, parent_id=parent_id, role_scope=role_scope, created_by=created_by)
            db.add(current)
            db.flush()
        parent_id = current.id
    return current


def move_application_to_folder(db: Session, application_id: int, folder: Folder) -> None:
    existing = db.scalar(select(FolderItem).where(FolderItem.application_id == application_id))
    if existing:
        existing.folder_id = folder.id
    else:
        db.add(FolderItem(folder_id=folder.id, application_id=application_id))


def reject_application(db: Session, app: Application, reason: str, rejected_by: User) -> None:
    app.status = ApplicationStatus.rejected.value
    existing = db.scalar(select(Rejection).where(Rejection.application_id == app.id))
    if existing:
        existing.reason = reason
        existing.rejected_by_user_id = rejected_by.id
        existing.rejected_at = datetime.now(UTC)
    else:
        db.add(
            Rejection(
                application_id=app.id,
                iin=app.iin,
                full_name=app.full_name,
                email=app.email,
                phone=app.phone,
                birth_date=app.birth_date,
                reason=reason,
                rejected_by_user_id=rejected_by.id,
            )
        )
    rejected_folder = ensure_folder_path(db, ["Отказанные"])
    move_application_to_folder(db, app.id, rejected_folder)


def apply_application_filters(query, search: str | None, status_value: str | None, specialty: str | None, group: str | None, curator_id: int | None, folder_id: int | None):
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
    if status_value:
        query = query.filter(Application.status == status_value)
    if specialty:
        query = query.join(AdmissionDetails, isouter=True).filter(AdmissionDetails.specialty == specialty)
    if group:
        query = query.join(EducationDetails, isouter=True).filter(EducationDetails.group_number == group)
    if curator_id:
        query = query.join(EducationDetails, isouter=True).filter(EducationDetails.curator_id == curator_id)
    if folder_id:
        query = query.join(FolderItem).filter(FolderItem.folder_id == folder_id)
    return query


def add_chat_message(
    db: Session,
    chat: Chat,
    message: str,
    sender_type: str,
    sender_user_id: int | None = None,
    sender_application_id: int | None = None,
) -> ChatMessage:
    item = ChatMessage(
        chat_id=chat.id,
        sender_type=sender_type,
        sender_user_id=sender_user_id,
        sender_application_id=sender_application_id,
        message=message,
    )
    chat.updated_at = datetime.now(UTC)
    db.add(item)
    db.flush()
    return item
