from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import ApplicationStatus, Role, User
from app.services.workflow import get_visible_application_or_404

router = APIRouter(prefix="/admin/applications", tags=["Application documents"])

STATUS_LABELS = {
    ApplicationStatus.completed.value: "Оформлен",
    ApplicationStatus.enrolled.value: "Зачислен",
    ApplicationStatus.expelled.value: "Отчислен",
    ApplicationStatus.graduated.value: "Выпускник",
}

VALUE_LABELS = {
    "general": "На общих основаниях",
    "reinstated": "Как восстановившийся",
    "transfer": "По переводу",
    "urban": "Городская местность",
    "rural": "Сельская местность",
    "russian": "Русский",
    "kazakh": "Казахский",
    "full_time": "Очная",
    "part_time": "Заочная",
    "free": "Бесплатно",
    "paid": "Платно",
    "excellent": "Отлично",
    "good": "Хорошо",
    "satisfactory": "Удовлетворительно",
}


def register_pdf_fonts() -> tuple[str, str]:
    candidates = [
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
    ]
    for regular_path, bold_path in candidates:
        if regular_path.exists() and bold_path.exists():
            if "CETSans" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("CETSans", str(regular_path)))
                pdfmetrics.registerFont(TTFont("CETSans-Bold", str(bold_path)))
            return "CETSans", "CETSans-Bold"
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="На сервере не найден шрифт для формирования PDF",
    )


def display(value: object | None, empty: str = "Не указано") -> str:
    if value is None or value == "":
        return empty
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    return VALUE_LABELS.get(str(value), str(value))


@router.get("/{application_id:int}/pdf")
def download_application_pdf(
    application_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if user.role == Role.assistant.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    app = get_visible_application_or_404(db, application_id, user)
    if app.status not in {
        ApplicationStatus.completed.value,
        ApplicationStatus.enrolled.value,
        ApplicationStatus.expelled.value,
        ApplicationStatus.graduated.value,
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PDF доступен после оформления студента")

    regular_font, bold_font = register_pdf_fonts()
    admission = app.admission_details
    education = app.education_details
    curator_name = education.curator.full_name if education and education.curator else "Не назначен"

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Анкета студента {app.full_name}",
        author="Колледж экономики и техники",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CETTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#123B66"),
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    subtitle_style = ParagraphStyle(
        "CETSubtitle",
        parent=styles["Normal"],
        fontName=regular_font,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#52677D"),
        alignment=TA_CENTER,
        spaceAfter=7 * mm,
    )
    section_style = ParagraphStyle(
        "CETSection",
        parent=styles["Heading2"],
        fontName=bold_font,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#176AA7"),
        spaceBefore=5 * mm,
        spaceAfter=2 * mm,
    )
    cell_style = ParagraphStyle(
        "CETCell",
        parent=styles["Normal"],
        fontName=regular_font,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#182A3A"),
    )
    label_style = ParagraphStyle(
        "CETLabel",
        parent=cell_style,
        fontName=bold_font,
        textColor=colors.HexColor("#38536D"),
    )

    story = [
        Paragraph("КОЛЛЕДЖ ЭКОНОМИКИ И ТЕХНИКИ", title_style),
        Paragraph(
            f"Анкета студента № {app.id} · Статус: {STATUS_LABELS.get(app.status, app.status)}",
            subtitle_style,
        ),
    ]

    def add_section(title: str, rows: list[tuple[str, object | None]]) -> None:
        story.append(Paragraph(title, section_style))
        table_data = [
            [
                Paragraph(escape(label), label_style),
                Paragraph(escape(display(value)), cell_style),
            ]
            for label, value in rows
        ]
        table = Table(table_data, colWidths=[58 * mm, 116 * mm], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF6FC")),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B9D3E8")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5E4F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.extend([table, Spacer(1, 2 * mm)])

    add_section(
        "Личные данные",
        [
            ("ФИО", app.full_name),
            ("ИИН", app.iin),
            ("Дата рождения", app.birth_date.strftime("%d.%m.%Y")),
            ("Телефон", app.phone),
            ("Email", app.email),
            ("Прописка", admission.residence_address if admission else None),
            ("Тип местности", admission.locality_type if admission else None),
        ],
    )
    add_section(
        "Данные поступления",
        [
            ("Вид зачисления", admission.enrollment_type if admission else None),
            ("База поступления", admission.base_class if admission else None),
            ("Льготная группа", admission.benefit_group if admission else None),
            ("Специальность", admission.specialty if admission else None),
            ("Квалификация", admission.qualification if admission else None),
            ("Язык обучения", admission.instruction_language if admission else None),
            ("Форма обучения", admission.study_form if admission else None),
            ("Общежитие", admission.needs_dormitory if admission else None),
        ],
    )
    add_section(
        "Учебные данные",
        [
            ("Группа", education.group_number if education else None),
            ("Курс", education.course if education else None),
            ("Код специальности НОБД", education.nobd_specialty_code if education else None),
            (
                "Срок обучения",
                f"{education.study_duration_years} г."
                if education and education.study_duration_years is not None
                else None,
            ),
            (
                "Начало текущего курса",
                education.course_start_date.strftime("%d.%m.%Y")
                if education and education.course_start_date
                else None,
            ),
            (
                "Окончание текущего курса",
                education.course_end_date.strftime("%d.%m.%Y")
                if education and education.course_end_date
                else None,
            ),
            ("Куратор", curator_name),
            ("Тип оплаты", education.payment_type if education else None),
            ("Госзаказ", education.is_state_grant if education else None),
            ("Успеваемость", education.academic_performance if education else None),
            ("Стипендия", education.has_scholarship if education else None),
            (
                "Размер стипендии",
                f"{education.scholarship_amount:,} ₸".replace(",", " ")
                if education and education.scholarship_amount is not None
                else None,
            ),
            ("Академический отпуск", education.academic_leave if education else None),
        ],
    )
    if app.status == ApplicationStatus.expelled.value and education:
        add_section(
            "Отчисление",
            [
                ("Номер приказа", education.expulsion_order_number),
                (
                    "Дата приказа",
                    education.expulsion_order_date.strftime("%d.%m.%Y")
                    if education.expulsion_order_date
                    else None,
                ),
                ("Причина", education.expulsion_reason),
            ],
        )

    document.build(story)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="student_application_{app.id}.pdf"'},
    )
