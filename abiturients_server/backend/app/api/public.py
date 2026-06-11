from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.session import get_db
from app.models import Application, ApplicationStatus, Chat, ChatAttachment, ChatMessage, Role, Specialty
from app.schemas.dto import (
    ApplicantAccessRequest,
    ApplicantAccessResponse,
    ApplicationCreate,
    ApplicationPublicCreated,
    ApplicationPublicStatus,
    ChatMessageCreate,
    ChatMessageRead,
    CollegeInfo,
)
from app.services.chat_files import (
    attachment_content_disposition,
    attachment_path,
    delete_storage_names,
    save_chat_upload,
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


def normalize_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        return f"7{digits[1:]}"
    return digits


def get_public_application(db: Session, application_id: int, token: str | None) -> Application:
    app = db.get(Application, application_id)
    if not app or not token or app.public_token != token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


@router.get("/public/college-info", response_model=CollegeInfo)
def college_info(db: Session = Depends(get_db)) -> CollegeInfo:
    specialties = db.query(Specialty).order_by(Specialty.qualification, Specialty.name).all()
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
    previous = db.scalars(
        select(Application)
        .where(
            Application.iin == payload.iin,
            Application.status.not_in(
                {
                    ApplicationStatus.expelled.value,
                    ApplicationStatus.graduated.value,
                }
            ),
        )
        .order_by(Application.created_at.desc(), Application.id.desc())
    ).first()
    if previous:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="У вас уже есть действующая заявка. Войдите в чат по ИИН и номеру телефона.",
        )
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


@router.post("/applicant/access", response_model=ApplicantAccessResponse)
def applicant_access(payload: ApplicantAccessRequest, db: Session = Depends(get_db)) -> ApplicantAccessResponse:
    applications = db.scalars(
        select(Application)
        .where(Application.iin == payload.iin)
        .order_by(Application.created_at.desc(), Application.id.desc())
    ).all()
    expected_phone = normalize_phone(payload.phone)
    app = next((item for item in applications if normalize_phone(item.phone) == expected_phone), None)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка с таким ИИН и телефоном не найдена")
    return ApplicantAccessResponse(
        application_id=app.id,
        public_token=app.public_token,
        status=app.status,
    )


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
    return (
        db.query(ChatMessage)
        .options(selectinload(ChatMessage.attachments))
        .filter(ChatMessage.chat_id == chat.id)
        .order_by(ChatMessage.created_at)
        .all()
    )


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


@router.post(
    "/applications/{application_id}/chat/attachments",
    response_model=ChatMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def send_public_chat_attachment(
    application_id: int,
    file: UploadFile = File(...),
    message: str = Form(default=""),
    x_application_token: str | None = Header(default=None, alias="X-Application-Token"),
    db: Session = Depends(get_db),
) -> ChatMessage:
    app = get_public_application(db, application_id, x_application_token)
    chat = get_or_create_chat(db, app)
    storage_name, size, content_type, content = await save_chat_upload(file)
    try:
        item = add_chat_message(
            db,
            chat,
            message.strip() or file.filename or "Документ",
            sender_type="applicant",
            sender_application_id=app.id,
        )
        db.add(
            ChatAttachment(
                message_id=item.id,
                storage_name=storage_name,
                original_name=Path(file.filename or "document").name[:255],
                content_type=content_type,
                size=size,
                content=content,
            )
        )
        notify_roles(
            db,
            [Role.admissions_admin, Role.tech_admin, Role.assistant],
            "Новый документ в чате",
            f"{app.full_name} отправил(а) файл {file.filename or 'document'}.",
            "chat_attachment",
            app.id,
        )
        db.commit()
        return (
            db.query(ChatMessage)
            .options(selectinload(ChatMessage.attachments))
            .filter(ChatMessage.id == item.id)
            .one()
        )
    except Exception:
        db.rollback()
        delete_storage_names([storage_name])
        raise


@router.get("/applications/{application_id}/chat/attachments/{attachment_id}")
def download_public_chat_attachment(
    application_id: int,
    attachment_id: int,
    x_application_token: str | None = Header(default=None, alias="X-Application-Token"),
    db: Session = Depends(get_db),
) -> Response:
    app = get_public_application(db, application_id, x_application_token)
    attachment = (
        db.query(ChatAttachment)
        .join(ChatAttachment.message)
        .join(ChatMessage.chat)
        .options(joinedload(ChatAttachment.message).joinedload(ChatMessage.chat))
        .filter(
            ChatAttachment.id == attachment_id,
            Chat.application_id == app.id,
        )
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
    path = attachment_path(attachment)
    content = path.read_bytes() if path.exists() else attachment.content
    return Response(
        content=content,
        media_type=attachment.content_type,
        headers={"Content-Disposition": attachment_content_disposition(attachment.original_name)},
    )
