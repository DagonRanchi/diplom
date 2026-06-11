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
from app.services.study_programs import sync_study_schedule

DEFAULT_PASSWORD = "admin12345"
SPECIALTY_ITEMS = [
    ("4S04110102 Бухгалтер", "04110100 Учет и аудит"),
    ("3W04110101 Бухгалтер-кассир", "04110100 Учет и аудит"),
    ("4S04140103 Маркетолог", "04140100 Маркетинг"),
    ("4S06130103 Разработчик программного обеспечения", "06130100 Программное обеспечение"),
    ("4S06130105 Техник информационных систем", "06130100 Программное обеспечение"),
    ("3W06120101 Оператор компьютерного аппаратного обеспечения", "06120100 Вычислительная техника и информационные сети"),
    ("3W07161301 Слесарь по ремонту автомобилей", "07161300 Техническое обслуживание, ремонт и эксплуатация автомобильного транспорта"),
    ("3W07161302 Электрик по ремонту автомобильного электрооборудования", "07161300 Техническое обслуживание, ремонт и эксплуатация автомобильного транспорта"),
    ("4S07161304 Техник-механик", "07161300 Техническое обслуживание, ремонт и эксплуатация автомобильного транспорта"),
    ("3W07161303 Мастер по ремонту автомобильного транспорта", "07161300 Техническое обслуживание, ремонт и эксплуатация автомобильного транспорта"),
    ("4S04120103 Менеджер по банковским операциям", "04120100 Банковское и страховое дело"),
    ("4S04130101 Менеджер", "04130100 Менеджмент"),
]


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
    valid_names = {name for name, _ in SPECIALTY_ITEMS}
    for specialty in db.scalars(select(Specialty)).all():
        if specialty.name not in valid_names:
            db.delete(specialty)
    for name, qualification in SPECIALTY_ITEMS:
        specialty = db.scalar(select(Specialty).where(Specialty.name == name))
        if specialty:
            specialty.qualification = qualification
        else:
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
    ensure_folder_path(db, ["Учебная часть", "Отчисленные"], Role.education_admin.value, tech_user.id)
    ensure_folder_path(db, ["Учебная часть", "Выпускники"], Role.education_admin.value, tech_user.id)
    ensure_folder_path(db, ["Конкурс"], Role.admissions_admin.value, tech_user.id)
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
    app1.admission_details.specialty = "4S06130103 Разработчик программного обеспечения"
    app1.admission_details.qualification = "06130100 Программное обеспечение"
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
    app2.admission_details.specialty = "4S04130101 Менеджер"
    app2.admission_details.qualification = "04130100 Менеджмент"
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
    app3.admission_details.specialty = "4S04110102 Бухгалтер"
    app3.admission_details.qualification = "04110100 Учет и аудит"
    app3.admission_details.base_class = "9 класс"
    if not app3.education_details:
        app3.education_details = EducationDetails(
            curator_id=users["teacher"].id,
            group_number="ИС-1-24",
            course=1,
            payment_type=PaymentType.free.value,
            is_state_grant=True,
        )
        db.add(app3.education_details)
        db.flush()
    sync_study_schedule(app3, app3.education_details)
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
        for app in db.scalars(select(Application)).all():
            if app.education_details and app.education_details.course:
                sync_study_schedule(app, app.education_details)
        db.commit()
        print("Seed data is ready.")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
