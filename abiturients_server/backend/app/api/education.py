from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import AcademicYearTransition, Application, ApplicationStatus, EducationDetails, Folder, Role, User
from app.schemas.dto import (
    AcademicYearTransitionRead,
    ApplicationRead,
    BulkEducationDetailsUpdateRequest,
    BulkIdsRequest,
    EducationDetailsRead,
    EducationDetailsUpdate,
    ExpelRequest,
    FolderRead,
    GroupCreate,
)
from app.services.serializers import serialize_application
from app.services.study_programs import study_duration_years, sync_study_schedule
from app.services.workflow import (
    calculate_scholarship_amount,
    EDUCATION_COMPLETABLE_STATUSES,
    ensure_status_allowed,
    ensure_folder_path,
    folder_by_path,
    get_or_create_education_details,
    get_visible_application_or_404,
    move_application_to_folder,
    notify_user,
    query_applications_for_user,
)

router = APIRouter(prefix="/education", tags=["Education"])


def ensure_education_operator(user: User) -> None:
    if user.role not in {Role.education_admin.value, Role.tech_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def get_group_folder(db: Session, group_name: str) -> Folder | None:
    root = folder_by_path(db, ["Группы"])
    if not root:
        return None
    return db.scalar(
        select(Folder).where(
            Folder.parent_id == root.id,
            Folder.name == group_name.strip(),
        )
    )


def require_group_folder(db: Session, group_name: str) -> Folder:
    folder = get_group_folder(db, group_name)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сначала создайте папку группы, затем выберите её у студента",
        )
    return folder


def apply_education_details_update(
    app: Application,
    payload: EducationDetailsUpdate,
    user: User,
    db: Session,
) -> EducationDetailsRead:
    ensure_education_operator(user)
    details = get_or_create_education_details(db, app)
    data = payload.model_dump(exclude_unset=True)
    if data.get("curator_id"):
        curator = db.get(User, data["curator_id"])
        if not curator or curator.role != Role.teacher.value or not curator.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Curator must be an active teacher")
    if data.get("group_number"):
        data["group_number"] = data["group_number"].strip()
        require_group_folder(db, data["group_number"])
    had_scholarship = details.has_scholarship
    for field, value in data.items():
        setattr(details, field, value.value if hasattr(value, "value") else value)
    if not details.has_scholarship:
        details.scholarship_amount = None
    elif "scholarship_amount" not in data and (
        not had_scholarship or "academic_performance" in data
    ):
        details.scholarship_amount = calculate_scholarship_amount(app, details.academic_performance)
    if details.course:
        sync_study_schedule(app, details)
    if app.status == ApplicationStatus.accepted_by_admissions.value:
        app.status = ApplicationStatus.education_review.value
    return details


def complete_education_application(app: Application, user: User, db: Session) -> Application:
    ensure_education_operator(user)
    ensure_status_allowed(
        app,
        EDUCATION_COMPLETABLE_STATUSES,
        "Студент уже оформлен или заявка недоступна для оформления",
    )
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
    sync_study_schedule(app, details)
    app.status = ApplicationStatus.completed.value
    group_folder = require_group_folder(db, details.group_number)
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
    return app


def start_new_academic_year(
    db: Session,
    user: User,
    start_year: int | None = None,
) -> AcademicYearTransition:
    if user.role != Role.tech_admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    target_year = start_year or datetime.now(UTC).year
    existing = db.scalar(
        select(AcademicYearTransition).where(AcademicYearTransition.start_year == target_year)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Новый курс на {target_year}/{target_year + 1} учебный год уже запущен",
        )

    applications = (
        db.query(Application)
        .join(EducationDetails)
        .options(
            joinedload(Application.admission_details),
            joinedload(Application.education_details),
        )
        .filter(
            Application.status.in_(
                {
                    ApplicationStatus.completed.value,
                    ApplicationStatus.enrolled.value,
                }
            )
        )
        .all()
    )
    promoted_count = 0
    graduated_count = 0
    skipped_count = 0
    graduates_folder = None

    for app in applications:
        details = app.education_details
        if not details or not details.course:
            skipped_count += 1
            continue

        sync_study_schedule(app, details)
        if details.course_start_date and details.course_start_date.year >= target_year:
            skipped_count += 1
            continue

        admission = app.admission_details
        duration_years = study_duration_years(
            admission.specialty if admission else None,
            admission.base_class if admission else None,
        ) or details.study_duration_years
        if duration_years is not None and details.course >= duration_years:
            details.graduated_at = datetime.now(UTC)
            app.status = ApplicationStatus.graduated.value
            if graduates_folder is None:
                graduates_folder = ensure_folder_path(
                    db,
                    ["Учебная часть", "Выпускники"],
                    Role.education_admin.value,
                    user.id,
                )
            move_application_to_folder(db, app.id, graduates_folder)
            graduated_count += 1
            continue

        details.course += 1
        sync_study_schedule(app, details, academic_start_year=target_year)
        promoted_count += 1

    transition = AcademicYearTransition(
        start_year=target_year,
        run_by_user_id=user.id,
        promoted_count=promoted_count,
        graduated_count=graduated_count,
        skipped_count=skipped_count,
    )
    db.add(transition)
    db.flush()
    return transition


def expel_education_application(app: Application, payload: ExpelRequest, user: User, db: Session) -> Application:
    ensure_education_operator(user)
    ensure_status_allowed(
        app,
        {ApplicationStatus.completed.value, ApplicationStatus.enrolled.value},
        "Отчислить можно только оформленного студента",
    )
    details = get_or_create_education_details(db, app)
    details.expulsion_order_number = payload.order_number.strip()
    details.expulsion_order_date = payload.order_date
    details.expulsion_reason = payload.reason.strip()
    details.expelled_at = datetime.now(UTC)
    app.status = ApplicationStatus.expelled.value
    folder = ensure_folder_path(db, ["Учебная часть", "Отчисленные"], Role.education_admin.value, user.id)
    move_application_to_folder(db, app.id, folder)
    return app


def graduate_education_application(app: Application, user: User, db: Session) -> Application:
    ensure_education_operator(user)
    ensure_status_allowed(
        app,
        {ApplicationStatus.completed.value, ApplicationStatus.enrolled.value},
        "Выпустить можно только оформленного студента",
    )
    details = get_or_create_education_details(db, app)
    details.graduated_at = datetime.now(UTC)
    app.status = ApplicationStatus.graduated.value
    folder = ensure_folder_path(db, ["Учебная часть", "Выпускники"], Role.education_admin.value, user.id)
    move_application_to_folder(db, app.id, folder)
    return app


@router.get("/groups", response_model=list[FolderRead])
def list_groups(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Folder]:
    ensure_education_operator(user)
    root = folder_by_path(db, ["Группы"])
    if not root:
        return []
    return list(
        db.scalars(
            select(Folder)
            .where(Folder.parent_id == root.id)
            .order_by(Folder.name)
        ).all()
    )


@router.post("/groups", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Folder:
    ensure_education_operator(user)
    name = payload.name.strip()
    root = ensure_folder_path(db, ["Группы"], Role.education_admin.value, user.id)
    if db.scalar(select(Folder).where(Folder.parent_id == root.id, Folder.name == name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такая группа уже существует")
    group = Folder(
        name=name,
        parent_id=root.id,
        owner_scope="all",
        role_scope=Role.education_admin.value,
        created_by=user.id,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get("/applications", response_model=list[ApplicationRead])
def education_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApplicationRead]:
    if user.role not in {Role.education_admin.value, Role.tech_admin.value, Role.teacher.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    apps = query_applications_for_user(db, user).order_by(Application.created_at.desc()).all()
    return [serialize_application(app) for app in apps]


@router.patch("/applications/bulk/details", response_model=list[EducationDetailsRead])
def bulk_update_education_details(
    payload: BulkEducationDetailsUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EducationDetailsRead]:
    result = []
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        result.append(apply_education_details_update(app, payload.update, user, db))
    db.commit()
    for details in result:
        db.refresh(details)
    return result


@router.patch("/applications/{application_id}/details", response_model=EducationDetailsRead)
def update_education_details(
    application_id: int,
    payload: EducationDetailsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EducationDetailsRead:
    app = get_visible_application_or_404(db, application_id, user)
    details = apply_education_details_update(app, payload, user, db)
    db.commit()
    db.refresh(details)
    return details


@router.post("/applications/bulk/save", response_model=list[ApplicationRead])
def bulk_save_education_applications(
    payload: BulkIdsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationRead]:
    result = []
    for app_id in payload.application_ids:
        app = get_visible_application_or_404(db, app_id, user)
        result.append(complete_education_application(app, user, db))
    db.commit()
    for app in result:
        db.refresh(app)
    return [serialize_application(app) for app in result]


@router.post("/applications/{application_id}/save", response_model=ApplicationRead)
def save_education_application(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    app = get_visible_application_or_404(db, application_id, user)
    complete_education_application(app, user, db)
    db.commit()
    db.refresh(app)
    return serialize_application(app)


@router.post("/applications/{application_id}/expel", response_model=ApplicationRead)
def expel_application(
    application_id: int,
    payload: ExpelRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    app = get_visible_application_or_404(db, application_id, user)
    expel_education_application(app, payload, user, db)
    db.commit()
    db.refresh(app)
    return serialize_application(app)


@router.post("/applications/{application_id}/graduate", response_model=ApplicationRead)
def graduate_application(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    app = get_visible_application_or_404(db, application_id, user)
    graduate_education_application(app, user, db)
    db.commit()
    db.refresh(app)
    return serialize_application(app)


@router.get("/academic-year/latest", response_model=AcademicYearTransitionRead | None)
def latest_academic_year_transition(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcademicYearTransition | None:
    if user.role != Role.tech_admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return db.scalar(
        select(AcademicYearTransition).order_by(AcademicYearTransition.start_year.desc()).limit(1)
    )


@router.post("/academic-year/start", response_model=AcademicYearTransitionRead)
def start_academic_year(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcademicYearTransition:
    try:
        transition = start_new_academic_year(db, user)
        db.commit()
        db.refresh(transition)
        return transition
    except IntegrityError:
        db.rollback()
        current_year = datetime.now(UTC).year
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Новый курс на {current_year}/{current_year + 1} учебный год уже запущен",
        )
