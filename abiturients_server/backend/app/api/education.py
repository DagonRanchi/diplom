from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import Application, ApplicationStatus, PaymentType, Role, User
from app.schemas.dto import ApplicationRead, EducationDetailsRead, EducationDetailsUpdate
from app.services.serializers import serialize_application
from app.services.workflow import (
    ensure_folder_path,
    get_or_create_education_details,
    get_visible_application_or_404,
    move_application_to_folder,
    notify_user,
    query_applications_for_user,
)

router = APIRouter(prefix="/education", tags=["Education"])


@router.get("/applications", response_model=list[ApplicationRead])
def education_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    if user.role not in {Role.education_admin.value, Role.tech_admin.value, Role.teacher.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    apps = query_applications_for_user(db, user).order_by(Application.created_at.desc()).all()
    return [serialize_application(app) for app in apps]


@router.patch("/applications/{application_id}/details", response_model=EducationDetailsRead)
def update_education_details(
    application_id: int,
    payload: EducationDetailsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EducationDetailsRead:
    if user.role not in {Role.education_admin.value, Role.tech_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    app = get_visible_application_or_404(db, application_id, user)
    details = get_or_create_education_details(db, app)
    data = payload.model_dump(exclude_unset=True)
    if data.get("curator_id"):
        curator = db.get(User, data["curator_id"])
        if not curator or curator.role != Role.teacher.value or not curator.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Curator must be an active teacher")
    for field, value in data.items():
        setattr(details, field, value.value if isinstance(value, PaymentType) else value)
    if app.status == ApplicationStatus.accepted_by_admissions.value:
        app.status = ApplicationStatus.education_review.value
    db.commit()
    db.refresh(details)
    return details


@router.post("/applications/{application_id}/save", response_model=ApplicationRead)
def save_education_application(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    if user.role not in {Role.education_admin.value, Role.tech_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    app = get_visible_application_or_404(db, application_id, user)
    details = get_or_create_education_details(db, app)
    missing = []
    if not details.curator_id:
        missing.append("curator_id")
    if not details.group_number:
        missing.append("group_number")
    if not details.course:
        missing.append("course")
    if not details.payment_type:
        missing.append("payment_type")
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"missing_fields": missing})

    details.completed_at = datetime.now(UTC)
    app.status = ApplicationStatus.completed.value
    group_folder = ensure_folder_path(db, ["Группы", details.group_number], Role.education_admin.value, user.id)
    move_application_to_folder(db, app.id, group_folder)
    if details.curator_id:
        notify_user(
            db,
            details.curator_id,
            "Назначен студент",
            f"{app.full_name} добавлен(а) в вашу группу {details.group_number}.",
            "student_assigned",
            app.id,
        )
    db.commit()
    db.refresh(app)
    return serialize_application(app)
