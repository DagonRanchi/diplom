from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import Application, ApplicationStatus, Folder, Role, User
from app.schemas.dto import (
    ApplicationAdminUpdate,
    ApplicationRead,
    BulkApplicationUpdateRequest,
    BulkIdsRequest,
    BulkMoveRequest,
    BulkRejectRequest,
    RejectRequest,
    TeacherContactUpdate,
    validate_iin_birth_date,
)
from app.services.serializers import serialize_application
from app.services.workflow import (
    apply_application_filters,
    ensure_folder_path,
    get_or_create_admission_details,
    get_or_create_education_details,
    get_visible_application_or_404,
    move_application_to_folder,
    notify_roles,
    query_applications_for_user,
    reject_application,
)

router = APIRouter(prefix="/admin/applications", tags=["Admin applications"])


def ensure_hr_operator(user: User) -> None:
    if user.role not in {Role.hr_admin.value, Role.tech_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def apply_application_update(app: Application, payload: ApplicationAdminUpdate, user: User, db: Session) -> None:
    data = payload.model_dump(exclude_unset=True)

    if user.role == Role.assistant.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assistant cannot edit applications")

    if user.role == Role.department_manager.value:
        allowed = {"email", "phone"}
        if set(data) - allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department manager can edit only contacts")
        contact = TeacherContactUpdate(**data)
        if contact.email is not None:
            app.email = str(contact.email)
        if contact.phone is not None:
            app.phone = contact.phone
        return

    if user.role not in {Role.tech_admin.value, Role.hr_admin.value, Role.document_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    next_iin = data.get("iin", app.iin)
    next_birth_date = data.get("birth_date", app.birth_date)
    try:
        validate_iin_birth_date(next_iin, next_birth_date)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Неверный ИИН")

    for field in ("iin", "birth_date", "full_name", "email", "phone", "status"):
        if field in data and data[field] is not None:
            setattr(app, field, data[field].value if hasattr(data[field], "value") else data[field])

    if payload.admission_details is not None:
        details = get_or_create_admission_details(db, app)
        details_data = payload.admission_details.model_dump(exclude_unset=True)
        for field, value in details_data.items():
            setattr(details, field, value)


@router.get("", response_model=list[ApplicationRead])
def list_applications(
    search: str | None = None,
    status_value: str | None = Query(default=None, alias="status"),
    specialty: str | None = None,
    group: str | None = None,
    curator_id: int | None = None,
    folder_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationRead]:
    query = query_applications_for_user(db, user)
    query = apply_application_filters(query, search, status_value, specialty, group, curator_id, folder_id)
    apps = query.order_by(Application.created_at.desc()).offset(offset).limit(limit).all()
    return [serialize_application(app) for app in apps]


@router.get("/{application_id:int}", response_model=ApplicationRead)
def get_application(application_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApplicationRead:
    app = get_visible_application_or_404(db, application_id, user)
    return serialize_application(app)


@router.patch("/{application_id:int}", response_model=ApplicationRead)
def update_application(
    application_id: int,
    payload: ApplicationAdminUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    app = get_visible_application_or_404(db, application_id, user)
    apply_application_update(app, payload, user, db)

    db.commit()
    db.refresh(app)
    return serialize_application(app)


@router.patch("/bulk/update", response_model=list[ApplicationRead])
def bulk_update_applications(
    payload: BulkApplicationUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationRead]:
    result = []
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        apply_application_update(app, payload.update, user, db)
        result.append(app)
    db.commit()
    for app in result:
        db.refresh(app)
    return [serialize_application(app) for app in result]


@router.post("/{application_id:int}/archive", response_model=ApplicationRead)
def archive_application(application_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApplicationRead:
    ensure_hr_operator(user)
    app = get_visible_application_or_404(db, application_id, user)
    app.status = ApplicationStatus.archived.value
    folder = ensure_folder_path(db, ["Архив УМЗ"], Role.hr_admin.value, user.id)
    move_application_to_folder(db, app.id, folder)
    db.commit()
    db.refresh(app)
    return serialize_application(app)


@router.post("/{application_id:int}/reject", response_model=ApplicationRead)
def reject_single(
    application_id: int,
    payload: RejectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    ensure_hr_operator(user)
    app = get_visible_application_or_404(db, application_id, user)
    reject_application(db, app, payload.reason, user)
    db.commit()
    db.refresh(app)
    return serialize_application(app)


@router.post("/{application_id:int}/accept", response_model=ApplicationRead)
def accept_application(application_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApplicationRead:
    ensure_hr_operator(user)
    app = get_visible_application_or_404(db, application_id, user)
    app.status = ApplicationStatus.approved_by_hr.value
    get_or_create_education_details(db, app)
    folder = ensure_folder_path(db, ["Канцелярия", "К обработке"], Role.document_admin.value, user.id)
    move_application_to_folder(db, app.id, folder)
    notify_roles(
        db,
        [Role.document_admin, Role.tech_admin],
        "Документ передан в работу",
        f"{app.full_name}: карточка прошла кадровую проверку и ожидает регистрации.",
        "document_handoff",
        app.id,
    )
    db.commit()
    db.refresh(app)
    return serialize_application(app)


@router.post("/bulk/archive", response_model=list[ApplicationRead])
def bulk_archive(payload: BulkIdsRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    ensure_hr_operator(user)
    result = []
    folder = ensure_folder_path(db, ["Архив УМЗ"], Role.hr_admin.value, user.id)
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        app.status = ApplicationStatus.archived.value
        move_application_to_folder(db, app.id, folder)
        result.append(app)
    db.commit()
    return [serialize_application(app) for app in result]


@router.post("/bulk/reject", response_model=list[ApplicationRead])
def bulk_reject(payload: BulkRejectRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    ensure_hr_operator(user)
    result = []
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        reject_application(db, app, payload.reason, user)
        result.append(app)
    db.commit()
    return [serialize_application(app) for app in result]


@router.post("/bulk/accept", response_model=list[ApplicationRead])
def bulk_accept(payload: BulkIdsRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    ensure_hr_operator(user)
    result = []
    folder = ensure_folder_path(db, ["Канцелярия", "К обработке"], Role.document_admin.value, user.id)
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        app.status = ApplicationStatus.approved_by_hr.value
        get_or_create_education_details(db, app)
        move_application_to_folder(db, app.id, folder)
        result.append(app)
    notify_roles(db, [Role.document_admin, Role.tech_admin], "Документы переданы в канцелярию", "HR передал выбранные карточки на регистрацию и исполнение.", "bulk_accepted")
    db.commit()
    return [serialize_application(app) for app in result]


@router.post("/bulk/move", response_model=list[ApplicationRead])
def bulk_move(payload: BulkMoveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    if user.role not in {Role.tech_admin.value, Role.hr_admin.value, Role.document_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    target_folder = db.get(Folder, payload.target_folder_id)
    if not target_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    result = []
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        move_application_to_folder(db, app.id, target_folder)
        result.append(app)
    db.commit()
    return [serialize_application(app) for app in result]
