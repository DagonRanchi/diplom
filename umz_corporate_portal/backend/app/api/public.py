from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Application, ApplicationStatus, ChatMessage, Role, Specialty
from app.schemas.dto import (
    ApplicationCreate,
    ApplicationPublicCreated,
    ApplicationPublicStatus,
    ChatMessageCreate,
    ChatMessageRead,
    CollegeInfo,
)
from app.services.workflow import (
    add_chat_message,
    ensure_folder_path,
    get_or_create_admission_details,
    get_or_create_chat,
    move_application_to_folder,
    notify_roles,
)

router = APIRouter(tags=["Public"])


def get_public_application(db: Session, application_id: int, token: str | None) -> Application:
    app = db.get(Application, application_id)
    if not app or not token or app.public_token != token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


@router.get("/public/portal-info", response_model=CollegeInfo)
def portal_info(db: Session = Depends(get_db)) -> CollegeInfo:
    specialties = db.query(Specialty).order_by(Specialty.qualification, Specialty.name).all()
    return CollegeInfo(
        name="Корпоративный портал УМЗ",
        slogan="Единый реестр документов, анкет и служебных обращений",
        description=(
            "Веб-портал предназначен для сотрудников корпорации «УМЗ» в Усть-Каменогорске. "
            "Система фиксирует входящие анкеты, заявления и служебные документы, передает их на кадровую проверку, "
            "регистрацию, согласование и исполнение."
        ),
        characteristics=[
            "Табличный реестр с быстрым редактированием записей",
            "Маршруты HR, канцелярии и руководителей подразделений",
            "Папки для массовой сортировки большого объема документов",
            "Чат и уведомления по каждой карточке обращения",
        ],
        staff=[
            {"name": "Отдел кадров", "role": "Проверка анкет, персональных данных и первичных документов"},
            {"name": "Канцелярия", "role": "Регистрация, контроль сроков и передача документов на исполнение"},
            {"name": "Руководители подразделений", "role": "Согласование карточек по своим направлениям"},
        ],
        facilities=[
            {"title": "Реестр НОБД-формата", "text": "Записи редактируются прямо в таблице без перехода между десятками форм."},
            {"title": "Документ-терминал", "text": "Папки, фильтры и массовое перемещение помогают работать с большим архивом."},
            {"title": "Контроль исполнения", "text": "Статусы и ответственные сотрудники видны в одной рабочей области."},
        ],
        faq=[
            {"question": "Как создать карточку?", "answer": "Заполните форму обращения. После отправки система выдаст код доступа к чату."},
            {"question": "Зачем указывать ИИН?", "answer": "ИИН используется для проверки персональной анкеты сотрудника и исключения дублей."},
            {"question": "Где смотреть статус?", "answer": "Статус и переписка доступны в чате по коду доступа карточки."},
        ],
        specialties=specialties,
    )


@router.post("/applications", response_model=ApplicationPublicCreated, status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)) -> ApplicationPublicCreated:
    app = Application(
        iin=payload.iin,
        birth_date=payload.birth_date,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        status=ApplicationStatus.new.value,
    )
    db.add(app)
    db.flush()
    get_or_create_admission_details(db, app)
    chat = get_or_create_chat(db, app)
    folder = ensure_folder_path(db, ["Входящий поток", "Новые анкеты"], Role.hr_admin.value)
    move_application_to_folder(db, app.id, folder)
    notify_roles(
        db,
        [Role.hr_admin, Role.tech_admin],
        "Новая карточка сотрудника",
        f"{app.full_name}: создано обращение для кадровой проверки.",
        "case_created",
        app.id,
    )
    db.commit()
    db.refresh(app)
    return ApplicationPublicCreated(id=app.id, public_token=app.public_token, status=app.status, chat_id=chat.id)


@router.get("/applications/{application_id}/public-status", response_model=ApplicationPublicStatus)
def public_status(
    application_id: int,
    x_application_token: str | None = Header(default=None, alias="X-Application-Token"),
    db: Session = Depends(get_db),
) -> Application:
    return get_public_application(db, application_id, x_application_token)


@router.get("/applications/{application_id}/chat/messages", response_model=list[ChatMessageRead])
def public_chat_messages(
    application_id: int,
    x_application_token: str | None = Header(default=None, alias="X-Application-Token"),
    db: Session = Depends(get_db),
) -> list[ChatMessage]:
    app = get_public_application(db, application_id, x_application_token)
    chat = get_or_create_chat(db, app)
    return db.query(ChatMessage).filter(ChatMessage.chat_id == chat.id).order_by(ChatMessage.created_at).all()


@router.post("/applications/{application_id}/chat/messages", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
def send_public_chat_message(
    application_id: int,
    payload: ChatMessageCreate,
    x_application_token: str | None = Header(default=None, alias="X-Application-Token"),
    db: Session = Depends(get_db),
) -> ChatMessage:
    app = get_public_application(db, application_id, x_application_token)
    chat = get_or_create_chat(db, app)
    message = add_chat_message(
        db,
        chat,
        payload.message,
        sender_type="employee",
        sender_application_id=app.id,
    )
    notify_roles(
        db,
        [Role.hr_admin, Role.document_admin, Role.tech_admin, Role.assistant],
        "Новое сообщение в чате",
        f"{app.full_name}: {payload.message[:120]}",
        "chat_message",
        app.id,
    )
    db.commit()
    db.refresh(message)
    return message
