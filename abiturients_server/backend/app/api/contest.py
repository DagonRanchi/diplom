from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import (
    Application,
    ApplicationStatus,
    ContestChoice,
    ContestProfile,
    Role,
    Specialty,
    User,
)
from app.schemas.dto import (
    ApplicationRead,
    BulkContestChoicesRequest,
    BulkContestUpdateRequest,
    ContestApplicationUpdate,
    ContestEntryRead,
)
from app.services.serializers import serialize_application
from app.services.workflow import (
    ensure_folder_path,
    get_or_create_admission_details,
    get_or_create_education_details,
    move_application_to_folder,
    notify_roles,
)

router = APIRouter(prefix="/contest", tags=["Contest"])

CONTEST_VIEW_ROLES = {
    Role.tech_admin.value,
    Role.admissions_admin.value,
    Role.education_admin.value,
    Role.assistant.value,
}
CONTEST_DECISION_ROLES = {
    Role.tech_admin.value,
    Role.admissions_admin.value,
    Role.education_admin.value,
}
CONTEST_EDIT_ROLES = {
    Role.tech_admin.value,
    Role.admissions_admin.value,
}


def ensure_role(user: User, allowed: set[str]) -> None:
    if user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def get_contest_application(db: Session, application_id: int, user: User) -> Application:
    ensure_role(user, CONTEST_VIEW_ROLES)
    app = (
        db.query(Application)
        .options(
            joinedload(Application.contest_profile).joinedload(ContestProfile.accepted_specialty),
            joinedload(Application.contest_choices).joinedload(ContestChoice.specialty),
            joinedload(Application.admission_details),
            joinedload(Application.education_details),
            joinedload(Application.folder_item),
            joinedload(Application.chat),
        )
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


def get_or_create_profile(db: Session, app: Application) -> ContestProfile:
    if app.contest_profile:
        return app.contest_profile
    profile = ContestProfile(application=app)
    db.add(profile)
    db.flush()
    return profile


def apply_contest_update(
    db: Session,
    app: Application,
    payload: ContestApplicationUpdate,
) -> None:
    profile = get_or_create_profile(db, app)
    data = payload.model_dump(exclude_unset=True)
    specialty_ids = data.pop("specialty_ids", None)
    for field, value in data.items():
        setattr(profile, field, value.value if hasattr(value, "value") else value)

    if specialty_ids is None:
        return
    specialties = db.scalars(select(Specialty).where(Specialty.id.in_(specialty_ids))).all()
    if len(specialties) != len(specialty_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Одна из специальностей не найдена")

    current_by_specialty = {choice.specialty_id: choice for choice in app.contest_choices}
    for choice in list(app.contest_choices):
        if choice.specialty_id not in specialty_ids:
            db.delete(choice)
    for specialty_id in specialty_ids:
        if specialty_id not in current_by_specialty:
            app.contest_choices.append(ContestChoice(specialty_id=specialty_id))
    db.flush()


def get_active_choices(db: Session, choice_ids: list[int]) -> list[ContestChoice]:
    unique_ids = list(dict.fromkeys(choice_ids))
    choices = (
        db.query(ContestChoice)
        .options(
            joinedload(ContestChoice.specialty),
            joinedload(ContestChoice.application).joinedload(Application.contest_profile),
            joinedload(ContestChoice.application).joinedload(Application.contest_choices),
        )
        .filter(ContestChoice.id.in_(unique_ids), ContestChoice.status == "active")
        .all()
    )
    if len(choices) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Одна из конкурсных заявок не найдена")
    if any(choice.application.status != ApplicationStatus.in_contest.value for choice in choices):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Одна из заявок уже не участвует в конкурсе")
    return choices


def accept_choice(db: Session, choice: ContestChoice, user: User) -> Application:
    app = choice.application
    profile = app.contest_profile
    if not profile:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Конкурсные данные не заполнены")
    admission = get_or_create_admission_details(db, app)
    for field in (
        "benefit_group",
        "residence_address",
        "base_class",
        "enrollment_type",
        "locality_type",
        "instruction_language",
        "study_form",
        "needs_dormitory",
    ):
        setattr(admission, field, getattr(profile, field))
    admission.specialty = choice.specialty.name
    admission.qualification = choice.specialty.qualification

    for other_choice in list(app.contest_choices):
        if other_choice.id == choice.id:
            other_choice.status = "accepted"
        else:
            db.delete(other_choice)
    profile.accepted_specialty_id = choice.specialty_id
    profile.completed_at = datetime.now(UTC)
    app.status = ApplicationStatus.accepted_by_admissions.value
    get_or_create_education_details(db, app)
    folder = ensure_folder_path(db, ["Учебная часть", "Требуют оформления"], Role.education_admin.value, user.id)
    move_application_to_folder(db, app.id, folder)
    notify_roles(
        db,
        [Role.education_admin, Role.tech_admin],
        "Заявка принята по конкурсу",
        f"{app.full_name}: {choice.specialty.name}.",
        "contest_accepted",
        app.id,
    )
    return app


def reject_choice(db: Session, choice: ContestChoice, user: User) -> Application:
    app = choice.application
    db.delete(choice)
    db.flush()
    remaining = db.scalar(
        select(ContestChoice.id).where(
            ContestChoice.application_id == app.id,
            ContestChoice.status == "active",
        ).limit(1)
    )
    if remaining is None:
        app.status = ApplicationStatus.new.value
        folder = ensure_folder_path(db, ["Приемная комиссия", "Новые заявки"], Role.admissions_admin.value, user.id)
        move_application_to_folder(db, app.id, folder)
    return app


@router.get("/entries", response_model=list[ContestEntryRead])
def contest_entries(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ContestEntryRead]:
    ensure_role(user, CONTEST_VIEW_ROLES)
    choices = (
        db.query(ContestChoice)
        .join(ContestChoice.application)
        .join(ContestChoice.specialty)
        .join(Application.contest_profile)
        .options(
            joinedload(ContestChoice.application).joinedload(Application.contest_profile),
            joinedload(ContestChoice.specialty),
        )
        .filter(
            ContestChoice.status == "active",
            Application.status == ApplicationStatus.in_contest.value,
        )
        .order_by(
            ContestProfile.base_class,
            Specialty.qualification,
            Specialty.name,
            Application.full_name,
        )
        .all()
    )
    return [
        ContestEntryRead(
            choice_id=choice.id,
            application_id=choice.application_id,
            full_name=choice.application.full_name,
            iin=choice.application.iin,
            base_class=choice.application.contest_profile.base_class or "Не выбрано",
            qualification=choice.specialty.qualification,
            specialty=choice.specialty.name,
            created_at=choice.created_at,
        )
        for choice in choices
    ]


@router.patch("/applications/{application_id}", response_model=ApplicationRead)
def update_contest_application(
    application_id: int,
    payload: ContestApplicationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    ensure_role(user, CONTEST_EDIT_ROLES)
    app = get_contest_application(db, application_id, user)
    if app.status not in {
        ApplicationStatus.new.value,
        ApplicationStatus.in_admissions_review.value,
        ApplicationStatus.in_contest.value,
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Конкурсные данные уже нельзя изменять")
    apply_contest_update(db, app, payload)
    db.commit()
    db.expire_all()
    return serialize_application(get_contest_application(db, app.id, user))


@router.post("/applications/{application_id}/submit", response_model=ApplicationRead)
def submit_to_contest(
    application_id: int,
    payload: ContestApplicationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    ensure_role(user, CONTEST_EDIT_ROLES)
    app = get_contest_application(db, application_id, user)
    if app.status not in {
        ApplicationStatus.new.value,
        ApplicationStatus.in_admissions_review.value,
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заявку уже нельзя отправить на конкурс")
    apply_contest_update(db, app, payload)
    profile = get_or_create_profile(db, app)
    active_choices = db.scalars(
        select(ContestChoice).where(
            ContestChoice.application_id == app.id,
            ContestChoice.status == "active",
        )
    ).all()
    missing = []
    if not profile.base_class:
        missing.append("base_class")
    if not profile.residence_address:
        missing.append("residence_address")
    if not profile.instruction_language:
        missing.append("instruction_language")
    if not active_choices:
        missing.append("specialty_ids")
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"missing_fields": missing})

    profile.submitted_at = datetime.now(UTC)
    profile.completed_at = None
    profile.accepted_specialty_id = None
    app.status = ApplicationStatus.in_contest.value
    folder = ensure_folder_path(db, ["Конкурс"], Role.admissions_admin.value, user.id)
    move_application_to_folder(db, app.id, folder)
    db.commit()
    db.expire_all()
    return serialize_application(get_contest_application(db, app.id, user))


@router.post("/choices/{choice_id}/accept", response_model=ApplicationRead)
def accept_contest_choice(
    choice_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    ensure_role(user, CONTEST_DECISION_ROLES)
    choice = (
        db.query(ContestChoice)
        .options(
            joinedload(ContestChoice.specialty),
            joinedload(ContestChoice.application).joinedload(Application.contest_profile),
        )
        .filter(ContestChoice.id == choice_id, ContestChoice.status == "active")
        .first()
    )
    if not choice or choice.application.status != ApplicationStatus.in_contest.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Конкурсная заявка не найдена")

    app = accept_choice(db, choice, user)
    db.commit()
    db.expire_all()
    return serialize_application(get_contest_application(db, app.id, user))


@router.post("/choices/{choice_id}/reject", response_model=dict)
def reject_contest_choice(
    choice_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    ensure_role(user, CONTEST_DECISION_ROLES)
    choice = db.get(ContestChoice, choice_id)
    if not choice or choice.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Конкурсная заявка не найдена")
    app = db.get(Application, choice.application_id)
    if not app or app.status != ApplicationStatus.in_contest.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заявка уже не участвует в конкурсе")
    application_id = choice.application_id
    reject_choice(db, choice, user)
    db.commit()
    return {"application_id": application_id, "status": app.status}


@router.patch("/bulk/update", response_model=list[ApplicationRead])
def bulk_update_contest(
    payload: BulkContestUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationRead]:
    ensure_role(user, CONTEST_EDIT_ROLES)
    if payload.update.specialty_ids is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Специальности нельзя массово заменять",
        )
    choices = get_active_choices(db, payload.choice_ids)
    applications = list({choice.application.id: choice.application for choice in choices}.values())
    for app in applications:
        apply_contest_update(db, app, payload.update)
    db.commit()
    db.expire_all()
    return [serialize_application(get_contest_application(db, app.id, user)) for app in applications]


@router.post("/bulk/accept", response_model=list[ApplicationRead])
def bulk_accept_contest(
    payload: BulkContestChoicesRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationRead]:
    ensure_role(user, CONTEST_DECISION_ROLES)
    choices = get_active_choices(db, payload.choice_ids)
    application_ids = [choice.application_id for choice in choices]
    if len(set(application_ids)) != len(application_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для одного абитуриента можно принять только одну специальность",
        )
    applications = [accept_choice(db, choice, user) for choice in choices]
    db.commit()
    db.expire_all()
    return [serialize_application(get_contest_application(db, app.id, user)) for app in applications]


@router.post("/bulk/reject", response_model=dict)
def bulk_reject_contest(
    payload: BulkContestChoicesRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    ensure_role(user, CONTEST_DECISION_ROLES)
    choices = get_active_choices(db, payload.choice_ids)
    for choice in choices:
        reject_choice(db, choice, user)
    db.commit()
    return {"rejected": len(choices)}
