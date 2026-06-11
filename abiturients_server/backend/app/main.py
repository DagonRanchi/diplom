import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin_applications, auth, chats, contingent, contest, documents, education, folders, notifications, public, users
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("cet-admissions")

settings = get_settings()

app = FastAPI(
    title="CET Admissions API",
    version="1.0.0",
    description="API системы подачи заявок в Колледж экономики и техники.",
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
        if "Неправильный ИИН" in str(error.get("msg", "")):
            return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": "Неправильный ИИН"})
    logger.info("Validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


app.include_router(auth.router)
app.include_router(public.router)
app.include_router(admin_applications.router)
app.include_router(documents.router)
app.include_router(education.router)
app.include_router(contingent.router)
app.include_router(folders.router)
app.include_router(contest.router)
app.include_router(chats.router)
app.include_router(users.router)
app.include_router(notifications.router)
