from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    AdmissionDetails,
    Application,
    ApplicationStatus,
    Chat,
    ChatMessage,
    EducationDetails,
    PaymentType,
    Role,
    Specialty,
    User,
)
from app.services.workflow import ensure_folder_path, move_application_to_folder

DEFAULT_PASSWORD = "admin12345"

DOCUMENT_TYPE_ITEMS = [
    ("Заявление сотрудника", "Кадровые документы"),
    ("Анкета сотрудника", "Кадровые документы"),
    ("Служебная записка", "Внутренние обращения"),
    ("Запрос на справку", "Канцелярия"),
    ("Приказ по подразделению", "Распорядительные документы"),
    ("Договор на согласование", "Юридические документы"),
    ("Акт выполненных работ", "Производственные документы"),
    ("Заявка в IT", "Техническая поддержка"),
]


def get_or_create_user(db: Session, full_name: str, email: str, role: Role) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        user.full_name = full_name
        user.role = role.value
        user.is_active = True
        return user
    user = User(full_name=full_name, email=email, password_hash=hash_password(DEFAULT_PASSWORD), role=role.value, is_active=True)
    db.add(user)
    db.flush()
    return user


def seed_users(db: Session) -> dict[str, User]:
    return {
        "tech": get_or_create_user(db, "Системный администратор УМЗ", "tech@umz.local", Role.tech_admin),
        "hr": get_or_create_user(db, "Отдел кадров УМЗ", "hr@umz.local", Role.hr_admin),
        "docs": get_or_create_user(db, "Канцелярия УМЗ", "docs@umz.local", Role.document_admin),
        "manager": get_or_create_user(db, "Алексей Ермеков", "manager@umz.local", Role.department_manager),
        "manager2": get_or_create_user(db, "Марина Власова", "manager2@umz.local", Role.department_manager),
        "assistant": get_or_create_user(db, "Оператор портала УМЗ", "operator@umz.local", Role.assistant),
    }


def seed_document_types(db: Session) -> None:
    valid_names = {name for name, _ in DOCUMENT_TYPE_ITEMS}
    for item in db.scalars(select(Specialty)).all():
        if item.name not in valid_names:
            db.delete(item)
    for name, group in DOCUMENT_TYPE_ITEMS:
        current = db.scalar(select(Specialty).where(Specialty.name == name))
        if current:
            current.qualification = group
        else:
            db.add(Specialty(name=name, qualification=group))


def seed_folders(db: Session, tech_user: User) -> None:
    ensure_folder_path(db, ["Входящий поток"], Role.hr_admin.value, tech_user.id)
    ensure_folder_path(db, ["Входящий поток", "Новые анкеты"], Role.hr_admin.value, tech_user.id)
    ensure_folder_path(db, ["Кадровая проверка"], Role.hr_admin.value, tech_user.id)
    ensure_folder_path(db, ["Кадровая проверка", "В работе"], Role.hr_admin.value, tech_user.id)
    ensure_folder_path(db, ["Канцелярия"], Role.document_admin.value, tech_user.id)
    ensure_folder_path(db, ["Канцелярия", "К обработке"], Role.document_admin.value, tech_user.id)
    ensure_folder_path(db, ["Канцелярия", "На согласовании"], Role.document_admin.value, tech_user.id)
    ensure_folder_path(db, ["Подразделения"], Role.document_admin.value, tech_user.id)
    ensure_folder_path(db, ["Подразделения", "Производственный блок"], Role.document_admin.value, tech_user.id)
    ensure_folder_path(db, ["Подразделения", "Бухгалтерия"], Role.document_admin.value, tech_user.id)
    ensure_folder_path(db, ["Подразделения", "IT-служба"], Role.document_admin.value, tech_user.id)
    ensure_folder_path(db, ["Исполненные документы"], Role.document_admin.value, tech_user.id)
    ensure_folder_path(db, ["Исполненные документы", "UMZ-2026-HR"], Role.document_admin.value, tech_user.id)
    ensure_folder_path(db, ["Исполненные документы", "UMZ-2026-PRD"], Role.document_admin.value, tech_user.id)
    ensure_folder_path(db, ["Архив УМЗ"], None, tech_user.id)
    ensure_folder_path(db, ["Отклоненные документы"], None, tech_user.id)


def ensure_case(
    db: Session,
    iin: str,
    birth_date: date,
    full_name: str,
    email: str,
    phone: str,
    status: ApplicationStatus,
) -> Application:
    app = db.scalar(select(Application).where(Application.iin == iin, Application.email == email))
    if app:
        app.status = status.value
        return app
    app = Application(iin=iin, birth_date=birth_date, full_name=full_name, email=email, phone=phone, status=status.value)
    db.add(app)
    db.flush()
    db.add(AdmissionDetails(application_id=app.id))
    db.add(Chat(application_id=app.id))
    db.flush()
    return app


def set_document_data(
    app: Application,
    document_type: str,
    department: str,
    position: str,
    registry_number: str,
    topic: str,
) -> None:
    if not app.admission_details:
        return
    app.admission_details.benefit_group = document_type
    app.admission_details.residence_address = department
    app.admission_details.base_class = position
    app.admission_details.qualification = registry_number
    app.admission_details.specialty = topic


def seed_cases(db: Session, users: dict[str, User]) -> None:
    case1 = ensure_case(
        db,
        "900214123456",
        date(1990, 2, 14),
        "Иванов Петр Сергеевич",
        "ivanov.p@umz.local",
        "+7 701 110 24 18",
        ApplicationStatus.new,
    )
    set_document_data(
        case1,
        "Анкета сотрудника",
        "Производственный блок",
        "Мастер смены",
        "UMZ-IN-0001",
        "Обновление персональной анкеты и контактных данных",
    )
    move_application_to_folder(db, case1.id, ensure_folder_path(db, ["Входящий поток", "Новые анкеты"]))

    case2 = ensure_case(
        db,
        "850603654321",
        date(1985, 6, 3),
        "Ахметова Дина Кайратовна",
        "akhmetova.d@umz.local",
        "+7 777 420 16 09",
        ApplicationStatus.hr_review,
    )
    set_document_data(
        case2,
        "Запрос на справку",
        "Бухгалтерия",
        "Экономист",
        "UMZ-HR-0048",
        "Справка о подтверждении места работы",
    )
    move_application_to_folder(db, case2.id, ensure_folder_path(db, ["Кадровая проверка", "В работе"]))

    case3 = ensure_case(
        db,
        "780915111222",
        date(1978, 9, 15),
        "Мельников Андрей Викторович",
        "melnikov.a@umz.local",
        "+7 705 300 19 77",
        ApplicationStatus.completed,
    )
    set_document_data(
        case3,
        "Служебная записка",
        "IT-служба",
        "Инженер АСУ",
        "UMZ-2026-PRD",
        "Согласование доступа к производственной системе",
    )
    if not case3.education_details:
        db.add(
            EducationDetails(
                application_id=case3.id,
                curator_id=users["manager"].id,
                group_number="UMZ-2026-PRD",
                course=2,
                payment_type=PaymentType.standard.value,
                is_state_grant=False,
            )
        )
        db.flush()
    move_application_to_folder(db, case3.id, ensure_folder_path(db, ["Исполненные документы", "UMZ-2026-PRD"]))

    chat = case1.chat
    if chat and not db.scalar(select(ChatMessage).where(ChatMessage.chat_id == chat.id)):
        db.add(
            ChatMessage(
                chat_id=chat.id,
                sender_type="employee",
                sender_application_id=case1.id,
                message="Добрый день. Нужно ли прикреплять копию удостоверения для обновления анкеты?",
            )
        )


def run_seed() -> None:
    db = SessionLocal()
    try:
        users = seed_users(db)
        seed_document_types(db)
        seed_folders(db, users["tech"])
        seed_cases(db, users)
        db.commit()
        print("UMZ portal seed data is ready.")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
