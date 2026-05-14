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


@router.get("/public/college-info", response_model=CollegeInfo)
def college_info(db: Session = Depends(get_db)) -> CollegeInfo:
    specialties = db.query(Specialty).order_by(Specialty.name).all()
    return CollegeInfo(
        name="Колледж экономики и техники",
        slogan="Современное образование для практической профессии",
        description=(
            "Колледж экономики и техники готовит специалистов для IT, экономики, учета, сервиса и технических "
            "направлений. Система приема помогает абитуриенту быстро подать заявку и оставаться на связи с комиссией."
        ),
        characteristics=[
            "Практико-ориентированные образовательные программы",
            "Наставники из числа преподавателей и администрации",
            "Удобная цифровая подача документов",
            "Поддержка абитуриента на всех этапах поступления",
        ],
        staff=[
            {"name": "Приемная комиссия", "role": "Консультации, обработка заявок и первичный отбор"},
            {"name": "Учебная часть", "role": "Оформление студентов, группы, кураторы и учебный процесс"},
            {"name": "Технический отдел", "role": "Поддержка цифровых сервисов колледжа"},
        ],
        facilities=[
            {"title": "Компьютерные аудитории", "text": "Рабочие места для программирования, проектной работы и практики."},
            {"title": "Учебные кабинеты", "text": "Светлые аудитории для лекций, семинаров и командной работы."},
            {"title": "Материально-техническая база", "text": "Оборудование и цифровые сервисы для современных специальностей."},
        ],
        faq=[
            {"question": "Как подать заявку?", "answer": "Заполните форму на сайте. После отправки откроется чат по заявке."},
            {"question": "Что делать при ошибке ИИН?", "answer": "Проверьте 12 цифр ИИН и дату рождения."},
            {"question": "Как узнать статус?", "answer": "Статус и сообщения доступны в чате заявки."},
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
    folder = ensure_folder_path(db, ["Приемная комиссия", "Новые заявки"], Role.admissions_admin.value)
    move_application_to_folder(db, app.id, folder)
    notify_roles(
        db,
        [Role.admissions_admin, Role.tech_admin],
        "Новая заявка",
        f"{app.full_name} отправил(а) заявку на поступление.",
        "application_created",
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
        sender_type="applicant",
        sender_application_id=app.id,
    )
    notify_roles(
        db,
        [Role.admissions_admin, Role.tech_admin, Role.assistant],
        "Новое сообщение в чате",
        f"{app.full_name}: {payload.message[:120]}",
        "chat_message",
        app.id,
    )
    db.commit()
    db.refresh(message)
    return message
