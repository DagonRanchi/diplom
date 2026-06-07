from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import ApplicationStatus, PaymentType, Role

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def validate_iin_birth_date(iin: str, birth_date: date) -> None:
    if not iin.isdigit() or len(iin) != 12:
        raise ValueError("Неверный ИИН")
    if iin[:6] != birth_date.strftime("%y%m%d"):
        raise ValueError("Неверный ИИН")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str = Field(min_length=1)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Role
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: Role | None = None
    is_active: bool | None = None


class SpecialtyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    qualification: str


class AdmissionDetailsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    benefit_group: str | None = None
    residence_address: str | None = None
    base_class: str | None = None
    qualification: str | None = None
    specialty: str | None = None


class AdmissionDetailsUpdate(BaseModel):
    benefit_group: str | None = None
    residence_address: str | None = None
    base_class: str | None = None
    qualification: str | None = None
    specialty: str | None = None


class EducationDetailsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    curator_id: int | None = None
    group_number: str | None = None
    course: int | None = None
    payment_type: str | None = None
    is_state_grant: bool
    completed_at: datetime | None = None


class EducationDetailsUpdate(BaseModel):
    curator_id: int | None = None
    group_number: str | None = Field(default=None, max_length=100)
    course: int | None = Field(default=None, ge=1, le=5)
    payment_type: PaymentType | None = None
    is_state_grant: bool | None = None


class ApplicationCreate(BaseModel):
    iin: str = Field(min_length=12, max_length=12)
    birth_date: date
    full_name: str = Field(min_length=2, max_length=255)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    phone: str = Field(min_length=5, max_length=64)

    @model_validator(mode="after")
    def validate_iin(self) -> "ApplicationCreate":
        validate_iin_birth_date(self.iin, self.birth_date)
        return self


class ApplicationPublicCreated(BaseModel):
    id: int
    public_token: str
    status: str
    chat_id: int


class ApplicationPublicStatus(BaseModel):
    id: int
    full_name: str
    status: str
    created_at: datetime
    updated_at: datetime


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    iin: str
    birth_date: date
    full_name: str
    email: str
    phone: str
    status: str
    created_at: datetime
    updated_at: datetime
    admission_details: AdmissionDetailsRead | None = None
    education_details: EducationDetailsRead | None = None
    folder_id: int | None = None
    chat_id: int | None = None


class ApplicationAdminUpdate(BaseModel):
    iin: str | None = Field(default=None, min_length=12, max_length=12)
    birth_date: date | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN, max_length=255)
    phone: str | None = Field(default=None, min_length=5, max_length=64)
    status: ApplicationStatus | None = None
    admission_details: AdmissionDetailsUpdate | None = None


class TeacherContactUpdate(BaseModel):
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN, max_length=255)
    phone: str | None = Field(default=None, min_length=5, max_length=64)


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class BulkIdsRequest(BaseModel):
    application_ids: list[int] = Field(min_length=1)


class BulkApplicationUpdateRequest(BulkIdsRequest):
    update: ApplicationAdminUpdate


class BulkRejectRequest(BulkIdsRequest):
    reason: str = Field(min_length=3, max_length=2000)


class BulkMoveRequest(BulkIdsRequest):
    target_folder_id: int


class BulkEducationDetailsUpdateRequest(BulkIdsRequest):
    update: EducationDetailsUpdate


class FolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None = None
    owner_scope: str
    role_scope: str | None = None
    created_at: datetime
    updated_at: datetime


class FolderTreeNode(FolderRead):
    children: list["FolderTreeNode"] = Field(default_factory=list)
    item_count: int = 0


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: int | None = None
    owner_scope: str = "all"
    role_scope: str | None = None


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: int | None = None
    owner_scope: str | None = None
    role_scope: str | None = None


class FolderItemCreate(BaseModel):
    application_id: int


class ChatMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    sender_type: str
    sender_user_id: int | None = None
    sender_application_id: int | None = None
    message: str
    created_at: datetime
    is_read: bool


class ChatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    created_at: datetime
    updated_at: datetime
    application: ApplicationRead | None = None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    message: str
    application_id: int | None = None
    is_read: bool
    created_at: datetime


class CollegeInfo(BaseModel):
    name: str
    slogan: str
    description: str
    characteristics: list[str]
    staff: list[dict[str, str]]
    facilities: list[dict[str, str]]
    faq: list[dict[str, str]]
    specialties: list[SpecialtyRead]
