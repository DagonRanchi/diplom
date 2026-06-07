import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin_applications, auth, chats, document_control, folders, notifications, public, users
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("umz-corporate-portal")

settings = get_settings()

app = FastAPI(
    title="UMZ Corporate Portal API",
    version="1.0.0",
    description="API корпоративного портала УМЗ для электронного документооборота.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    for error in exc.errors():
        if "Неверный ИИН" in str(error.get("msg", "")):
            return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": "Неверный ИИН"})
    logger.info("Validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


app.include_router(auth.router)
app.include_router(public.router)
app.include_router(admin_applications.router)
app.include_router(document_control.router)
app.include_router(folders.router)
app.include_router(chats.router)
app.include_router(users.router)
app.include_router(notifications.router)
