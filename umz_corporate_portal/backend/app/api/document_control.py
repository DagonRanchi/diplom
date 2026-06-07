from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import Application, ApplicationStatus, PaymentType, Role, User
from app.schemas.dto import (
    ApplicationRead,
    BulkEducationDetailsUpdateRequest,
    BulkIdsRequest,
    EducationDetailsRead,
    EducationDetailsUpdate,
)
from app.services.serializers import serialize_application
from app.services.workflow import (
    ensure_folder_path,
    get_or_create_education_details,
    get_visible_application_or_404,
    move_application_to_folder,
    notify_user,
    query_applications_for_user,
)

router = APIRouter(prefix="/document-control", tags=["Document control"])


def ensure_document_operator(user: User) -> None:
    if user.role not in {Role.document_admin.value, Role.tech_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def apply_processing_details_update(
    app: Application,
    payload: EducationDetailsUpdate,
    user: User,
    db: Session,
) -> EducationDetailsRead:
    ensure_document_operator(user)
    details = get_or_create_education_details(db, app)
    data = payload.model_dump(exclude_unset=True)
    if data.get("curator_id"):
        manager = db.get(User, data["curator_id"])
        if not manager or manager.role != Role.department_manager.value or not manager.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Responsible user must be an active department manager")
    for field, value in data.items():
        setattr(details, field, value.value if isinstance(value, PaymentType) else value)
    if app.status == ApplicationStatus.approved_by_hr.value:
        app.status = ApplicationStatus.document_review.value
    return details


def complete_document_case(app: Application, user: User, db: Session) -> Application:
    ensure_document_operator(user)
    details = get_or_create_education_details(db, app)
    missing = []
    if not details.curator_id:
        missing.append("responsible_user_id")
    if not details.group_number:
        missing.append("registry_code")
    if not details.course:
        missing.append("priority")
    if not details.payment_type:
        missing.append("processing_mode")
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"missing_fields": missing})

    details.completed_at = datetime.now(UTC)
    app.status = ApplicationStatus.completed.value
    registry_folder = ensure_folder_path(db, ["Исполненные документы", details.group_number], Role.document_admin.value, user.id)
    move_application_to_folder(db, app.id, registry_folder)
    if details.curator_id:
        notify_user(
            db,
            details.curator_id,
            "Документ назначен подразделению",
            f"{app.full_name}: карточка добавлена в реестр {details.group_number}.",
            "document_assigned",
            app.id,
        )
    return app


@router.get("/applications", response_model=list[ApplicationRead])
def document_control_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    if user.role not in {Role.document_admin.value, Role.tech_admin.value, Role.department_manager.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    apps = query_applications_for_user(db, user).order_by(Application.created_at.desc()).all()
    return [serialize_application(app) for app in apps]


@router.patch("/applications/{application_id}/details", response_model=EducationDetailsRead)
def update_processing_details(
    application_id: int,
    payload: EducationDetailsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EducationDetailsRead:
    app = get_visible_application_or_404(db, application_id, user)
    details = apply_processing_details_update(app, payload, user, db)
    db.commit()
    db.refresh(details)
    return details


@router.patch("/applications/bulk/details", response_model=list[EducationDetailsRead])
def bulk_update_processing_details(
    payload: BulkEducationDetailsUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EducationDetailsRead]:
    result = []
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        result.append(apply_processing_details_update(app, payload.update, user, db))
    db.commit()
    for details in result:
        db.refresh(details)
    return result


@router.post("/applications/{application_id}/save", response_model=ApplicationRead)
def save_document_case(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    app = get_visible_application_or_404(db, application_id, user)
    complete_document_case(app, user, db)
    db.commit()
    db.refresh(app)
    return serialize_application(app)


@router.post("/applications/bulk/save", response_model=list[ApplicationRead])
def bulk_save_document_cases(
    payload: BulkIdsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationRead]:
    result = []
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        result.append(complete_document_case(app, user, db))
    db.commit()
    for app in result:
        db.refresh(app)
    return [serialize_application(app) for app in result]
