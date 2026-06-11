from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AdmissionDetails,
    Application,
    ApplicationStatus,
    Chat,
    ContingentImport,
    ContingentSourceRow,
    EducationDetails,
    PaymentType,
    Role,
)
from app.services.names import build_full_name, normalize_full_name
from app.services.study_programs import find_study_program
from app.services.workflow import ensure_folder_path, get_or_create_admission_details, get_or_create_chat, move_application_to_folder


MINIMAL_HEADERS = [
    "EI Контингента",
    "ID контингента",
    "ИИН",
    "Фамилия",
    "Имя",
    "Отчество",
    "Дата рождения",
    "Адрес постоянной регистрации на русском [6997]",
    "Вид зачисления [type_enrollment]",
    "Дата прибытия/зачисления [267]",
    "Сотовый телефон (номер) [6914]",
    "Электронный адрес (Е-mail) [6915]",
    "Из числа принятых, окончил(-а): [5573]",
    "Тип местности проживания [246]",
    "Срок обучения [6129]",
    "Дата окончания обучения по данной специальности [date_graduation_specialty]",
    "Курс обучения [5802]",
    "Дата начала курса [course_start_date]",
    "Дата окончания курса [course_end_date]",
    "Код группы [6159]",
    "Язык обучения [209]",
    "Форма обучения [5568]",
    "Специальность и классификатор (основной) [426]",
    "Специальность [speciality_a]",
    "Квалификация [qualification_a]",
    "Находится в академическом отпуске [6754]",
    "Успеваемость за семестр [7201]",
    "Сведения об общежитии [5560]",
    "Обучение за счет средств [6662]",
    "Назначена стипендия [447]",
    "Ребенок - сирота [251]",
    "Дети с инвалидностью и/или лица с инвалидностью [253]",
    "Из многодетной семьи [7822]",
    "Дата выбытия [269]",
    "Причина выбытия [5804]",
]

REQUIRED_HEADERS = {
    "EI Контингента",
    "ID контингента",
    "ИИН",
    "Фамилия",
    "Имя",
    "Дата рождения",
    "Код группы [6159]",
    "Курс обучения [5802]",
    "Специальность и классификатор (основной) [426]",
}


def clean_excel_value(value: str | None) -> str:
    cleaned = (value or "").strip()
    if cleaned.startswith('="') and cleaned.endswith('"'):
        return cleaned[2:-1]
    return cleaned


def decode_contingent_file(content: bytes) -> str:
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16")
    return content.decode("utf-8-sig")


def parse_date(value: str | None) -> date | None:
    cleaned = clean_excel_value(value)
    if not cleaned:
        return None
    try:
        return date.fromisoformat(cleaned[:10])
    except ValueError:
        return None


def parse_number(value: str | None) -> int | None:
    match = re.search(r"\d+", clean_excel_value(value))
    return int(match.group()) if match else None


def parse_scholarship_amount(value: str | None) -> int | None:
    values = [int(item) for item in re.findall(r"value=(\d+)", clean_excel_value(value))]
    return max(values) if values else None


def yes(value: str | None) -> bool:
    return clean_excel_value(value).casefold() == "да"


def base_class_from_source(value: str | None) -> str | None:
    normalized = clean_excel_value(value).casefold()
    if "основн" in normalized:
        return "9 класс"
    if "средн" in normalized:
        return "11 класс"
    if "типо" in normalized:
        return "ТИПО"
    return None


def enrollment_type_from_source(value: str | None) -> str:
    normalized = clean_excel_value(value).casefold()
    if "восстанов" in normalized:
        return "reinstated"
    if "перевод" in normalized:
        return "transfer"
    return "general"


def performance_from_source(value: str | None) -> str | None:
    normalized = clean_excel_value(value).casefold()
    return {
        "отлично": "excellent",
        "хорошо": "good",
        "удовлетворительно": "satisfactory",
    }.get(normalized)


def benefit_from_row(values: dict[str, str]) -> str:
    if yes(values.get("Дети с инвалидностью и/или лица с инвалидностью [253]")):
        return "Инвалидность"
    if yes(values.get("Ребенок - сирота [251]")) or yes(
        values.get("Ребенок, оставшийся без попечения родителей [258]")
    ):
        return "Сирота"
    if yes(values.get("Из многодетной семьи [7822]")):
        return "Многодетная"
    return "Льгот нет"


def group_folder(db: Session, group_name: str):
    root = ensure_folder_path(db, ["Группы"], Role.education_admin.value)
    return ensure_folder_path(db, ["Группы", group_name], Role.education_admin.value, root.created_by)


def import_contingent(
    db: Session,
    content: bytes,
    filename: str,
    created_by_user_id: int,
) -> ContingentImport:
    checksum = hashlib.sha256(content).hexdigest()
    if db.scalar(select(ContingentImport).where(ContingentImport.checksum == checksum)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот файл контингента уже был импортирован",
        )

    try:
        text = decode_contingent_file(content)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV должен быть в UTF-16 или UTF-8") from exc

    reader = csv.reader(io.StringIO(text), delimiter="\t")
    headers = next(reader, None)
    if not headers or not REQUIRED_HEADERS.issubset(set(headers)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Формат CSV контингента не распознан")

    rows = list(reader)
    index = {header: position for position, header in enumerate(headers)}
    normalized_count = 0
    for app in db.scalars(select(Application)).all():
        normalized = normalize_full_name(app.full_name)
        if normalized and normalized != app.full_name:
            app.full_name = normalized
            normalized_count += 1

    record = ContingentImport(
        filename=filename[:255],
        checksum=checksum,
        headers_json=json.dumps(headers, ensure_ascii=False),
        created_by_user_id=created_by_user_id,
        normalized_count=normalized_count,
    )
    db.add(record)
    db.flush()

    source_by_ei = {
        source.external_ei: source
        for source in db.scalars(select(ContingentSourceRow)).all()
    }
    applications_by_iin = {
        app.iin: app
        for app in db.scalars(
            select(Application)
            .where(Application.iin.in_([clean_excel_value(row[index["ИИН"]]) for row in rows]))
            .options(
                joinedload(Application.admission_details),
                joinedload(Application.education_details),
                joinedload(Application.chat),
            )
        ).all()
    }
    groups = {
        clean_excel_value(row[index["Код группы [6159]"]])
        for row in rows
        if clean_excel_value(row[index["Код группы [6159]"]])
    }
    folders = {name: group_folder(db, name) for name in sorted(groups)}

    created_count = 0
    updated_count = 0
    for row_number, raw_row in enumerate(rows, start=2):
        row = list(raw_row) + [""] * max(0, len(headers) - len(raw_row))
        values = {header: clean_excel_value(row[position]) for header, position in index.items()}
        iin = values["ИИН"]
        birth_date = parse_date(values["Дата рождения"])
        external_ei = values["EI Контингента"]
        if not iin or not birth_date or not external_ei:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Строка {row_number}: отсутствует ИИН, дата рождения или EI контингента",
            )

        source = source_by_ei.get(external_ei)
        app = source.application if source else applications_by_iin.get(iin)
        if app is None:
            app = Application(
                iin=iin,
                birth_date=birth_date,
                full_name=build_full_name(values["Фамилия"], values["Имя"], values.get("Отчество")),
                email=values.get("Электронный адрес (Е-mail) [6915]") or f"{iin}@contingent.local",
                phone=values.get("Сотовый телефон (номер) [6914]") or "Не указан",
                status=ApplicationStatus.completed.value,
            )
            enrollment_date = parse_date(values.get("Дата прибытия/зачисления [267]"))
            if enrollment_date:
                app.created_at = datetime.combine(enrollment_date, datetime.min.time(), tzinfo=UTC)
            db.add(app)
            db.flush()
            created_count += 1
        else:
            updated_count += 1

        app.iin = iin
        app.birth_date = birth_date
        app.full_name = build_full_name(values["Фамилия"], values["Имя"], values.get("Отчество"))
        app.email = values.get("Электронный адрес (Е-mail) [6915]") or app.email or f"{iin}@contingent.local"
        app.phone = values.get("Сотовый телефон (номер) [6914]") or app.phone or "Не указан"
        app.status = ApplicationStatus.completed.value

        admission = app.admission_details or get_or_create_admission_details(db, app)
        admission.benefit_group = benefit_from_row(values)
        admission.residence_address = values.get("Адрес постоянной регистрации на русском [6997]") or None
        admission.base_class = base_class_from_source(values.get("Из числа принятых, окончил(-а): [5573]"))
        admission.qualification = values.get("Специальность [speciality_a]") or None
        admission.specialty = values.get("Специальность и классификатор (основной) [426]") or None
        admission.enrollment_type = enrollment_type_from_source(values.get("Вид зачисления [type_enrollment]"))
        admission.locality_type = (
            "rural" if "сельск" in values.get("Тип местности проживания [246]", "").casefold() else "urban"
        )
        admission.instruction_language = (
            "kazakh" if "казах" in values.get("Язык обучения [209]", "").casefold() else "russian"
        )
        admission.study_form = (
            "part_time" if "заоч" in values.get("Форма обучения [5568]", "").casefold() else "full_time"
        )
        admission.needs_dormitory = values.get("Сведения об общежитии [5560]", "").casefold() != "не нуждается"

        details = app.education_details
        if details is None:
            details = EducationDetails(application=app)
            db.add(details)
        details.group_number = values.get("Код группы [6159]") or None
        details.course = parse_number(values.get("Курс обучения [5802]"))
        details.study_duration_years = parse_number(values.get("Срок обучения [6129]"))
        details.course_start_date = parse_date(values.get("Дата начала курса [course_start_date]"))
        details.course_end_date = parse_date(values.get("Дата окончания курса [course_end_date]"))
        program = find_study_program(admission.specialty)
        details.nobd_specialty_code = program.nobd_code if program else None
        funding = values.get("Обучение за счет средств [6662]", "")
        details.payment_type = PaymentType.paid.value if "самофинанс" in funding.casefold() else PaymentType.free.value
        details.is_state_grant = details.payment_type == PaymentType.free.value
        details.has_scholarship = yes(values.get("Назначена стипендия [447]"))
        details.scholarship_amount = parse_scholarship_amount(
            values.get("Информация о начислении и размер стипендии, тенге [470]")
        )
        details.academic_leave = values.get(
            "Находится в академическом отпуске [6754]", ""
        ).casefold() not in {"", "нет"}
        details.academic_performance = performance_from_source(values.get("Успеваемость за семестр [7201]"))
        enrollment_date = parse_date(values.get("Дата прибытия/зачисления [267]"))
        if enrollment_date:
            details.completed_at = datetime.combine(enrollment_date, datetime.min.time(), tzinfo=UTC)

        get_or_create_chat(db, app)
        if details.group_number:
            move_application_to_folder(db, app.id, folders[details.group_number])

        if source is None:
            source = ContingentSourceRow(
                application=app,
                import_id=record.id,
                external_ei=external_ei,
                external_id=values["ID контингента"],
                raw_row_json=json.dumps(row[: len(headers)], ensure_ascii=False),
            )
            db.add(source)
            source_by_ei[external_ei] = source
        else:
            source.import_id = record.id
            source.external_id = values["ID контингента"]
            source.raw_row_json = json.dumps(row[: len(headers)], ensure_ascii=False)

    record.created_count = created_count
    record.updated_count = updated_count
    db.flush()
    return record


def split_full_name(full_name: str) -> tuple[str, str, str]:
    parts = normalize_full_name(full_name).split()
    return (
        parts[0] if parts else "",
        parts[1] if len(parts) > 1 else "",
        " ".join(parts[2:]) if len(parts) > 2 else "",
    )


def source_value(value: object | None) -> str:
    if value is None or value == "":
        return ""
    return str(value)


def iso_datetime(value: date | datetime | None) -> str:
    if value is None:
        return ""
    date_value = value.date() if isinstance(value, datetime) else value
    return f'="{date_value.isoformat()}T00:00:00"'


def build_contingent_export(db: Session) -> bytes:
    latest_import = db.scalar(select(ContingentImport).order_by(ContingentImport.id.desc()).limit(1))
    headers = json.loads(latest_import.headers_json) if latest_import else MINIMAL_HEADERS
    index = {header: position for position, header in enumerate(headers)}
    applications = db.scalars(
        select(Application)
        .where(
            Application.status.in_(
                {
                    ApplicationStatus.completed.value,
                    ApplicationStatus.enrolled.value,
                    ApplicationStatus.expelled.value,
                    ApplicationStatus.graduated.value,
                }
            )
        )
        .options(
            joinedload(Application.admission_details),
            joinedload(Application.education_details),
            joinedload(Application.contingent_source),
        )
        .order_by(Application.full_name)
    ).unique().all()

    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\r\n")
    writer.writerow(headers)

    def set_value(row: list[str], header: str, value: object | None) -> None:
        position = index.get(header)
        if position is not None:
            row[position] = source_value(value)

    for app in applications:
        if app.contingent_source:
            row = json.loads(app.contingent_source.raw_row_json)
            row += [""] * max(0, len(headers) - len(row))
            row = row[: len(headers)]
        else:
            row = [""] * len(headers)
        admission = app.admission_details
        education = app.education_details
        last_name, first_name, patronymic = split_full_name(app.full_name)

        set_value(row, "ИИН", f'="{app.iin}"')
        set_value(row, "Фамилия", last_name)
        set_value(row, "Имя", first_name)
        set_value(row, "Отчество", patronymic)
        set_value(row, "Дата рождения", app.birth_date.isoformat())
        set_value(row, "Сотовый телефон (номер) [6914]", f'="{app.phone}"' if app.phone else "")
        set_value(row, "Электронный адрес (Е-mail) [6915]", app.email)
        set_value(row, "Адрес постоянной регистрации на русском [6997]", admission.residence_address if admission else None)
        set_value(
            row,
            "Вид зачисления [type_enrollment]",
            {
                "general": "на общих основаниях",
                "reinstated": "как восстановившийся",
                "transfer": "по переводу из другого колледжа",
            }.get(admission.enrollment_type if admission else "", ""),
        )
        set_value(
            row,
            "Из числа принятых, окончил(-а): [5573]",
            {"9 класс": "основную школу", "11 класс": "среднюю школу", "ТИПО": "организацию ТиПО"}.get(
                admission.base_class if admission else "", ""
            ),
        )
        set_value(
            row,
            "Тип местности проживания [246]",
            "сельская местность" if admission and admission.locality_type == "rural" else "городская местность",
        )
        set_value(row, "Специальность и классификатор (основной) [426]", admission.specialty if admission else None)
        set_value(row, "Специальность [speciality_a]", admission.qualification if admission else None)
        set_value(row, "Квалификация [qualification_a]", admission.specialty if admission else None)
        set_value(
            row,
            "Язык обучения [209]",
            "казахский" if admission and admission.instruction_language == "kazakh" else "русский",
        )
        set_value(
            row,
            "Форма обучения [5568]",
            "заочная" if admission and admission.study_form == "part_time" else "очная",
        )
        set_value(
            row,
            "Сведения об общежитии [5560]",
            "обеспечен" if admission and admission.needs_dormitory else "не нуждается",
        )
        set_value(row, "Срок обучения [6129]", f"{education.study_duration_years} года" if education and education.study_duration_years else "")
        set_value(row, "Курс обучения [5802]", f"{education.course} курс" if education and education.course else "")
        set_value(row, "Дата начала курса [course_start_date]", iso_datetime(education.course_start_date if education else None))
        set_value(row, "Дата окончания курса [course_end_date]", iso_datetime(education.course_end_date if education else None))
        set_value(row, "Код группы [6159]", f'="{education.group_number}"' if education and education.group_number else "")
        set_value(
            row,
            "Находится в академическом отпуске [6754]",
            "по состоянию здоровья" if education and education.academic_leave else "нет",
        )
        set_value(
            row,
            "Успеваемость за семестр [7201]",
            {
                "excellent": "отлично",
                "good": "хорошо",
                "satisfactory": "удовлетворительно",
            }.get(education.academic_performance if education else "", ""),
        )
        set_value(
            row,
            "Обучение за счет средств [6662]",
            "самофинансирование" if education and education.payment_type == PaymentType.paid.value else "МБ",
        )
        set_value(row, "Назначена стипендия [447]", "Да" if education and education.has_scholarship else "Нет")
        set_value(row, "Ребенок - сирота [251]", "Да" if admission and admission.benefit_group == "Сирота" else "Нет")
        set_value(
            row,
            "Дети с инвалидностью и/или лица с инвалидностью [253]",
            "Да" if admission and admission.benefit_group == "Инвалидность" else "Нет",
        )
        set_value(
            row,
            "Из многодетной семьи [7822]",
            "Да" if admission and admission.benefit_group == "Многодетная" else "Нет",
        )
        if app.status == ApplicationStatus.expelled.value:
            set_value(row, "Дата выбытия [269]", iso_datetime(education.expelled_at if education else None))
            set_value(row, "Причина выбытия [5804]", education.expulsion_reason if education else None)
        elif app.status == ApplicationStatus.graduated.value:
            set_value(row, "Дата выбытия [269]", iso_datetime(education.graduated_at if education else None))
            set_value(row, "Причина выбытия [5804]", "выпуск")
        writer.writerow(row)

    return output.getvalue().encode("utf-16")
