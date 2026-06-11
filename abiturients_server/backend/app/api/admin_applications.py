from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import Application, ApplicationStatus, ApplicationTag, Folder, Role, User
from app.schemas.dto import (
    ApplicationAdminUpdate,
    ApplicationRead,
    BulkApplicationUpdateRequest,
    BulkIdsRequest,
    BulkMoveRequest,
    BulkRejectRequest,
    BulkTagsRequest,
    RejectRequest,
    TeacherContactUpdate,
    validate_iin_birth_date,
)
from app.services.serializers import serialize_application
from app.services.names import normalize_full_name
from app.services.study_programs import sync_study_schedule
from app.services.workflow import (
    apply_application_filters,
    ADMISSIONS_ACTIONABLE_STATUSES,
    calculate_scholarship_amount,
    ensure_status_allowed,
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


def ensure_admissions_operator(user: User) -> None:
    if user.role not in {Role.admissions_admin.value, Role.tech_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def apply_application_update(app: Application, payload: ApplicationAdminUpdate, user: User, db: Session) -> None:
    data = payload.model_dump(exclude_unset=True)

    if user.role == Role.assistant.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assistant cannot edit applications")

    if user.role == Role.teacher.value:
        allowed = {"email", "phone"}
        if set(data) - allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher can edit only contacts")
        contact = TeacherContactUpdate(**data)
        if contact.email is not None:
            app.email = str(contact.email)
        if contact.phone is not None:
            app.phone = contact.phone
        return

    if user.role not in {Role.tech_admin.value, Role.admissions_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    next_iin = data.get("iin", app.iin)
    next_birth_date = data.get("birth_date", app.birth_date)
    try:
        validate_iin_birth_date(next_iin, next_birth_date)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Неправильный ИИН")

    if "status" in data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Статус заявки изменяется только через предусмотренные действия",
        )

    for field in ("iin", "birth_date", "full_name", "email", "phone"):
        if field in data and data[field] is not None:
            value = data[field].value if hasattr(data[field], "value") else data[field]
            setattr(app, field, normalize_full_name(value) if field == "full_name" else value)

    if payload.admission_details is not None:
        details = get_or_create_admission_details(db, app)
        details_data = payload.admission_details.model_dump(exclude_unset=True)
        for field, value in details_data.items():
            setattr(details, field, value.value if hasattr(value, "value") else value)
        if "specialty" in details_data and app.education_details and app.education_details.has_scholarship:
            app.education_details.scholarship_amount = calculate_scholarship_amount(
                app,
                app.education_details.academic_performance,
            )
        if (
            {"specialty", "base_class"} & set(details_data)
            and app.education_details
            and app.education_details.course
        ):
            sync_study_schedule(app, app.education_details)


@router.get("", response_model=list[ApplicationRead])
def list_applications(
    search: str | None = None,
    status_value: str | None = Query(default=None, alias="status"),
    specialty: str | None = None,
    group: str | None = None,
    curator_id: int | None = None,
    folder_id: int | None = None,
    folder_recursive: bool = False,
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationRead]:
    if created_from and created_to and created_from > created_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Начальная дата позже конечной")
    query = query_applications_for_user(db, user)
    query = apply_application_filters(
        query,
        search,
        status_value,
        specialty,
        group,
        curator_id,
        folder_id,
        folder_recursive,
        created_from,
        created_to,
    )
    apps = query.order_by(Application.created_at.desc()).offset(offset).limit(limit).all()
    return [serialize_application(app) for app in apps]


def ensure_tag_operator(user: User) -> None:
    if user.role not in {
        Role.tech_admin.value,
        Role.admissions_admin.value,
        Role.education_admin.value,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


@router.post("/bulk/tags", response_model=dict)
def add_bulk_tags(
    payload: BulkTagsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    ensure_tag_operator(user)
    applications = [get_visible_application_or_404(db, app_id, user) for app_id in payload.application_ids]
    existing = set(
        db.execute(
            select(ApplicationTag.application_id, ApplicationTag.name).where(
                ApplicationTag.application_id.in_(payload.application_ids),
                ApplicationTag.name.in_(payload.tags),
            )
        ).all()
    )
    added = 0
    for app in applications:
        for tag in payload.tags:
            if (app.id, tag) not in existing:
                db.add(ApplicationTag(application_id=app.id, name=tag))
                added += 1
    db.commit()
    return {"updated": len(applications), "added": added}


@router.post("/bulk/tags/remove", response_model=dict)
def remove_bulk_tags(
    payload: BulkTagsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    ensure_tag_operator(user)
    for app_id in payload.application_ids:
        get_visible_application_or_404(db, app_id, user)
    tags = db.scalars(
        select(ApplicationTag).where(
            ApplicationTag.application_id.in_(payload.application_ids),
            ApplicationTag.name.in_(payload.tags),
        )
    ).all()
    updated_applications = len({tag.application_id for tag in tags})
    for tag in tags:
        db.delete(tag)
    db.commit()
    return {"updated": updated_applications, "removed": len(tags)}


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
    ensure_admissions_operator(user)
    app = get_visible_application_or_404(db, application_id, user)
    ensure_status_allowed(app, ADMISSIONS_ACTIONABLE_STATUSES, "Эту заявку уже нельзя архивировать")
    app.status = ApplicationStatus.archived_by_admissions.value
    folder = ensure_folder_path(db, ["Приемная комиссия", "Архив"], Role.admissions_admin.value, user.id)
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
    ensure_admissions_operator(user)
    app = get_visible_application_or_404(db, application_id, user)
    ensure_status_allowed(app, ADMISSIONS_ACTIONABLE_STATUSES, "Эту заявку уже нельзя отклонить")
    reject_application(db, app, payload.reason, user)
    db.commit()
    db.refresh(app)
    return serialize_application(app)


@router.post("/{application_id:int}/accept", response_model=ApplicationRead)
def accept_application(application_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApplicationRead:
    ensure_admissions_operator(user)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Сначала отправьте заявку на конкурс и примите выбранную специальность",
    )


@router.post("/bulk/archive", response_model=list[ApplicationRead])
def bulk_archive(payload: BulkIdsRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    ensure_admissions_operator(user)
    result = []
    folder = ensure_folder_path(db, ["Приемная комиссия", "Архив"], Role.admissions_admin.value, user.id)
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        ensure_status_allowed(app, ADMISSIONS_ACTIONABLE_STATUSES, "Среди выбранных есть заявки, которые нельзя архивировать")
        app.status = ApplicationStatus.archived_by_admissions.value
        move_application_to_folder(db, app.id, folder)
        result.append(app)
    db.commit()
    return [serialize_application(app) for app in result]


@router.post("/bulk/reject", response_model=list[ApplicationRead])
def bulk_reject(payload: BulkRejectRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    ensure_admissions_operator(user)
    result = []
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        ensure_status_allowed(app, ADMISSIONS_ACTIONABLE_STATUSES, "Среди выбранных есть заявки, которые нельзя отклонить")
        reject_application(db, app, payload.reason, user)
        result.append(app)
    db.commit()
    return [serialize_application(app) for app in result]


@router.post("/bulk/accept", response_model=list[ApplicationRead])
def bulk_accept(payload: BulkIdsRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    ensure_admissions_operator(user)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Массовое принятие выполняется по направлениям в разделе «Конкурс»",
    )


@router.post("/bulk/move", response_model=list[ApplicationRead])
def bulk_move(payload: BulkMoveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    if user.role not in {Role.tech_admin.value, Role.admissions_admin.value, Role.education_admin.value}:
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
