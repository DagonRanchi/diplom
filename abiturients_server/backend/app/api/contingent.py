from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.db.session import get_db
from app.models import ContingentImport, Role, User
from app.schemas.dto import ContingentImportRead
from app.services.contingent import build_contingent_export, import_contingent


router = APIRouter(prefix="/education/contingent", tags=["Education contingent"])
MAX_CONTINGENT_FILE_SIZE = 15 * 1024 * 1024


def ensure_contingent_operator(user: User) -> None:
    if user.role not in {Role.education_admin.value, Role.tech_admin.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


@router.get("/latest", response_model=ContingentImportRead | None)
def latest_import(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContingentImport | None:
    ensure_contingent_operator(user)
    return db.scalar(select(ContingentImport).order_by(ContingentImport.id.desc()).limit(1))


@router.post("/import", response_model=ContingentImportRead)
async def import_contingent_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContingentImport:
    if user.role != Role.tech_admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Импорт доступен техническому администратору")
    content = await file.read(MAX_CONTINGENT_FILE_SIZE + 1)
    if len(content) > MAX_CONTINGENT_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CSV превышает 15 МБ")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV пуст")
    try:
        result = import_contingent(db, content, file.filename or "contingent.csv", user.id)
        db.commit()
        db.refresh(result)
        return result
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Файл или строки уже импортированы") from exc


@router.get("/export")
def export_contingent(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    ensure_contingent_operator(user)
    return Response(
        content=build_contingent_export(db),
        media_type="text/tab-separated-values; charset=utf-16",
        headers={"Content-Disposition": 'attachment; filename="contingent_export.csv"'},
    )
