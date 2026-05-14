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


def get_or_create_user(db: Session, full_name: str, email: str, role: Role) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(full_name=full_name, email=email, password_hash=hash_password(DEFAULT_PASSWORD), role=role.value, is_active=True)
    db.add(user)
    db.flush()
    return user


def seed_users(db: Session) -> dict[str, User]:
    return {
        "tech": get_or_create_user(db, "Технический администратор", "tech@cet.local", Role.tech_admin),
        "admissions": get_or_create_user(db, "Приемная комиссия", "admissions@cet.local", Role.admissions_admin),
        "education": get_or_create_user(db, "Учебная часть", "education@cet.local", Role.education_admin),
        "teacher": get_or_create_user(db, "Айгерим Муратова", "teacher@cet.local", Role.teacher),
        "teacher2": get_or_create_user(db, "Сергей Иванов", "teacher2@cet.local", Role.teacher),
        "assistant": get_or_create_user(db, "Помощник приемной комиссии", "assistant@cet.local", Role.assistant),
    }


def seed_specialties(db: Session) -> None:
    items = [
        ("Информационные системы", "Техник-программист"),
        ("Вычислительная техника и ПО", "Техник по программному обеспечению"),
        ("Экономика", "Экономист"),
        ("Учет и аудит", "Бухгалтер"),
        ("Техническое обслуживание", "Техник-механик"),
    ]
    for name, qualification in items:
        if not db.scalar(select(Specialty).where(Specialty.name == name)):
            db.add(Specialty(name=name, qualification=qualification))


def seed_folders(db: Session, tech_user: User) -> None:
    ensure_folder_path(db, ["Приемная комиссия"], Role.admissions_admin.value, tech_user.id)
    ensure_folder_path(db, ["Приемная комиссия", "Новые заявки"], Role.admissions_admin.value, tech_user.id)
    ensure_folder_path(db, ["Приемная комиссия", "В обработке"], Role.admissions_admin.value, tech_user.id)
    ensure_folder_path(db, ["Приемная комиссия", "Архив"], Role.admissions_admin.value, tech_user.id)
    ensure_folder_path(db, ["Поступившие"], Role.education_admin.value, tech_user.id)
    ensure_folder_path(db, ["Учебная часть"], Role.education_admin.value, tech_user.id)
    ensure_folder_path(db, ["Учебная часть", "Требуют оформления"], Role.education_admin.value, tech_user.id)
    ensure_folder_path(db, ["Учебная часть", "Оформленные"], Role.education_admin.value, tech_user.id)
    ensure_folder_path(db, ["Группы"], Role.education_admin.value, tech_user.id)
    ensure_folder_path(db, ["Группы", "ИС-1-24"], Role.education_admin.value, tech_user.id)
    ensure_folder_path(db, ["Группы", "ЭК-1-24"], Role.education_admin.value, tech_user.id)
    ensure_folder_path(db, ["Отказанные"], None, tech_user.id)
    ensure_folder_path(db, ["Все студенты"], None, tech_user.id)


def ensure_application(db: Session, iin: str, birth_date: date, full_name: str, email: str, phone: str, status: ApplicationStatus) -> Application:
    app = db.scalar(select(Application).where(Application.iin == iin, Application.email == email))
    if app:
        return app
    app = Application(iin=iin, birth_date=birth_date, full_name=full_name, email=email, phone=phone, status=status.value)
    db.add(app)
    db.flush()
    db.add(AdmissionDetails(application_id=app.id))
    db.add(Chat(application_id=app.id))
    db.flush()
    return app


def seed_applications(db: Session, users: dict[str, User]) -> None:
    app1 = ensure_application(
        db,
        "060424123456",
        date(2006, 4, 24),
        "Алия Нурланова",
        "aliya@example.com",
        "+7 701 111 22 33",
        ApplicationStatus.new,
    )
    app1.admission_details.specialty = "Информационные системы"
    app1.admission_details.qualification = "Техник-программист"
    move_application_to_folder(db, app1.id, ensure_folder_path(db, ["Приемная комиссия", "Новые заявки"]))

    app2 = ensure_application(
        db,
        "071105987654",
        date(2007, 11, 5),
        "Дамир Сейдахмет",
        "damir@example.com",
        "+7 702 444 55 66",
        ApplicationStatus.in_admissions_review,
    )
    app2.admission_details.specialty = "Экономика"
    app2.admission_details.qualification = "Экономист"
    app2.admission_details.base_class = "9 класс"
    move_application_to_folder(db, app2.id, ensure_folder_path(db, ["Приемная комиссия", "В обработке"]))

    app3 = ensure_application(
        db,
        "060901111222",
        date(2006, 9, 1),
        "Мадина Касымова",
        "madina@example.com",
        "+7 775 777 88 99",
        ApplicationStatus.completed,
    )
    if not app3.education_details:
        db.add(
            EducationDetails(
                application_id=app3.id,
                curator_id=users["teacher"].id,
                group_number="ИС-1-24",
                course=1,
                payment_type=PaymentType.free.value,
                is_state_grant=True,
            )
        )
        db.flush()
    move_application_to_folder(db, app3.id, ensure_folder_path(db, ["Группы", "ИС-1-24"]))

    chat = app1.chat
    if chat and not db.scalar(select(ChatMessage).where(ChatMessage.chat_id == chat.id)):
        db.add(ChatMessage(chat_id=chat.id, sender_type="applicant", sender_application_id=app1.id, message="Здравствуйте, какие документы нужны для поступления?"))


def run_seed() -> None:
    db = SessionLocal()
    try:
        users = seed_users(db)
        seed_specialties(db)
        seed_folders(db, users["tech"])
        seed_applications(db, users)
        db.commit()
        print("Seed data is ready.")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
