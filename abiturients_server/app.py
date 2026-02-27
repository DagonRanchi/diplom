import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import DateTime, Integer, String, Text, create_engine, desc
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env")


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite:///./abiturients_local.db")
)
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-before-production")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin12345")
DB_SSLMODE = os.getenv("DB_SSLMODE", "")

PDF_FONT_NAME = "Helvetica"
for font_path in (
    BASE_DIR / "fonts" / "DejaVuSans.ttf",
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
):
    if not font_path.exists():
        continue
    try:
        pdfmetrics.registerFont(TTFont("AbiturientsUnicode", str(font_path)))
        PDF_FONT_NAME = "AbiturientsUnicode"
        break
    except Exception:
        continue

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif DATABASE_URL.startswith("postgresql://") and DB_SSLMODE:
    connect_args = {"sslmode": DB_SSLMODE}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()

app = FastAPI(title="Abiturients Registration", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60 * 60 * 8)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

REGISTRATION_ERRORS = {
    "missing_required": "Заполните обязательные поля",
    "bad_email": "Проверьте email",
}
LOGIN_ERRORS = {
    "invalid_credentials": "Неверный логин или пароль",
}


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(64), nullable=False)
    specialty: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        390000,
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, expected_digest = stored_hash.split("$", 1)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        390000,
    ).hex()
    return hmac.compare_digest(digest, expected_digest)


def ensure_default_admin(db: Session) -> None:
    existing_admin = db.query(AdminUser).filter(AdminUser.username == ADMIN_USERNAME).first()
    if existing_admin:
        return

    db.add(
        AdminUser(
            username=ADMIN_USERNAME,
            password_hash=hash_password(ADMIN_PASSWORD),
        )
    )
    db.commit()


def is_admin_authenticated(request: Request) -> bool:
    return bool(request.session.get("admin_id"))


def wrap_pdf_text(text: str, max_width: float, font_name: str, font_size: int) -> list[str]:
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    wrapped_lines: list[str] = []

    for paragraph in normalized.split("\n"):
        words = paragraph.split()
        if not words:
            wrapped_lines.append("")
            continue

        current_line = words[0]
        for word in words[1:]:
            candidate = f"{current_line} {word}"
            if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                current_line = candidate
                continue

            wrapped_lines.append(current_line)
            current_line = word

        wrapped_lines.append(current_line)

    return wrapped_lines


def draw_pdf_field(
    pdf: canvas.Canvas,
    label: str,
    value: str,
    y: float,
    left_margin: float,
    right_margin: float,
    top_margin: float,
    bottom_margin: float,
) -> float:
    font_size = 11
    line_height = 6 * mm
    max_width = right_margin - left_margin
    lines = wrap_pdf_text(f"{label}: {value}", max_width=max_width, font_name=PDF_FONT_NAME, font_size=font_size)

    pdf.setFont(PDF_FONT_NAME, font_size)
    for line in lines:
        if y <= bottom_margin + line_height:
            pdf.showPage()
            pdf.setFont(PDF_FONT_NAME, font_size)
            y = A4[1] - top_margin

        pdf.drawString(left_margin, y, line)
        y -= line_height

    return y - 1.5 * mm


def build_application_pdf(application: Application) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    left_margin = 18 * mm
    right_margin = A4[0] - (18 * mm)
    top_margin = 18 * mm
    bottom_margin = 18 * mm
    y = A4[1] - top_margin

    pdf.setTitle(f"abiturient_{application.id}")
    pdf.setFont(PDF_FONT_NAME, 16)
    pdf.drawString(left_margin, y, "Лист абитуриента")
    y -= 9 * mm

    if application.created_at:
        if application.created_at.tzinfo:
            created_at = application.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        else:
            created_at = application.created_at.strftime("%Y-%m-%d %H:%M")
    else:
        created_at = "-"

    fields = [
        ("ID заявки", str(application.id)),
        ("Дата подачи", created_at),
        ("ФИО", application.full_name),
        ("Email", application.email),
        ("Телефон", application.phone),
        ("Специальность", application.specialty),
        ("Комментарий", application.notes or "-"),
    ]

    for label, value in fields:
        y = draw_pdf_field(
            pdf=pdf,
            label=label,
            value=value,
            y=y,
            left_margin=left_margin,
            right_margin=right_margin,
            top_margin=top_margin,
            bottom_margin=bottom_margin,
        )

    pdf.save()
    return buffer.getvalue()


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/", response_class=HTMLResponse)
def registration_page(request: Request) -> HTMLResponse:
    error_code = request.query_params.get("error", "")
    context = {
        "request": request,
        "success": request.query_params.get("success") == "1",
        "error": REGISTRATION_ERRORS.get(error_code, ""),
    }
    return templates.TemplateResponse("register.html", context)


@app.post("/apply", response_class=HTMLResponse)
def submit_application(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    specialty: str = Form(...),
    notes: str = Form(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    full_name = full_name.strip()
    email = email.strip()
    phone = phone.strip()
    specialty = specialty.strip()
    notes = notes.strip()

    if not full_name or not email or not phone or not specialty:
        return RedirectResponse(url="/?error=missing_required", status_code=303)
    if "@" not in email:
        return RedirectResponse(url="/?error=bad_email", status_code=303)

    db.add(
        Application(
            full_name=full_name,
            email=email,
            phone=phone,
            specialty=specialty,
            notes=notes or None,
        )
    )
    db.commit()
    return RedirectResponse(url="/?success=1", status_code=303)


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request) -> HTMLResponse:
    if is_admin_authenticated(request):
        return RedirectResponse(url="/admin/applications", status_code=303)
    error_code = request.query_params.get("error", "")
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "error": LOGIN_ERRORS.get(error_code, "")},
    )


@app.post("/admin/login", response_class=HTMLResponse)
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    user = db.query(AdminUser).filter(AdminUser.username == username.strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse(
            url="/admin/login?error=invalid_credentials",
            status_code=303,
        )

    request.session["admin_id"] = user.id
    request.session["admin_username"] = user.username
    return RedirectResponse(url="/admin/applications", status_code=303)


@app.get("/admin/logout")
def admin_logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)


@app.get("/admin/applications", response_class=HTMLResponse)
def admin_applications(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    applications = db.query(Application).order_by(desc(Application.created_at)).all()
    return templates.TemplateResponse(
        "admin_applications.html",
        {
            "request": request,
            "applications": applications,
            "admin_username": request.session.get("admin_username", "admin"),
        },
    )


@app.get("/admin/applications/{application_id}/pdf")
def admin_application_pdf(
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    pdf_bytes = build_application_pdf(application)
    filename = f"abiturient_{application.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
