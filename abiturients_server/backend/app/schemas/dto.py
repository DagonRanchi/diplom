from datetime import date, datetime
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import (
    AcademicPerformance,
    ApplicationStatus,
    EnrollmentType,
    InstructionLanguage,
    LocalityType,
    PaymentType,
    Role,
    StudyForm,
)

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def validate_iin_birth_date(iin: str, birth_date: date) -> None:
    if not iin.isdigit() or len(iin) != 12:
        raise ValueError("Неправильный ИИН")
    if iin[:6] != birth_date.strftime("%y%m%d"):
        raise ValueError("Неправильный ИИН")


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


class ApplicantAccessRequest(BaseModel):
    iin: str = Field(min_length=12, max_length=12)
    phone: str = Field(min_length=5, max_length=64)


class ApplicantAccessResponse(BaseModel):
    application_id: int
    public_token: str
    status: str


class ContestChoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    specialty_id: int
    status: str
    created_at: datetime
    specialty: SpecialtyRead


class ContestProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    benefit_group: str | None = None
    residence_address: str | None = None
    base_class: str | None = None
    enrollment_type: str
    locality_type: str
    instruction_language: str | None = None
    study_form: str
    needs_dormitory: bool
    accepted_specialty_id: int | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    accepted_specialty: SpecialtyRead | None = None


class ContestApplicationUpdate(BaseModel):
    benefit_group: Literal["Льгот нет", "Многодетная", "Сирота", "Инвалидность"] | None = None
    residence_address: str | None = None
    base_class: Literal["9 класс", "11 класс", "ТИПО"] | None = None
    enrollment_type: EnrollmentType | None = None
    locality_type: LocalityType | None = None
    instruction_language: InstructionLanguage | None = None
    study_form: StudyForm | None = None
    needs_dormitory: bool | None = None
    specialty_ids: list[int] | None = Field(default=None, min_length=1, max_length=4)

    @model_validator(mode="after")
    def unique_specialties(self) -> "ContestApplicationUpdate":
        if self.specialty_ids is not None and len(set(self.specialty_ids)) != len(self.specialty_ids):
            raise ValueError("Специальности не должны повторяться")
        return self


class BulkContestChoicesRequest(BaseModel):
    choice_ids: list[int] = Field(min_length=1)


class BulkContestUpdateRequest(BulkContestChoicesRequest):
    update: ContestApplicationUpdate


class ContestEntryRead(BaseModel):
    choice_id: int
    application_id: int
    full_name: str
    iin: str
    base_class: str
    qualification: str
    specialty: str
    created_at: datetime


class AdmissionDetailsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    benefit_group: str | None = None
    residence_address: str | None = None
    base_class: str | None = None
    qualification: str | None = None
    specialty: str | None = None
    enrollment_type: str
    locality_type: str
    instruction_language: str | None = None
    study_form: str
    needs_dormitory: bool


class AdmissionDetailsUpdate(BaseModel):
    benefit_group: Literal["Льгот нет", "Многодетная", "Сирота", "Инвалидность"] | None = None
    residence_address: str | None = None
    base_class: Literal["9 класс", "11 класс", "ТИПО"] | None = None
    qualification: str | None = None
    specialty: str | None = None
    enrollment_type: EnrollmentType | None = None
    locality_type: LocalityType | None = None
    instruction_language: InstructionLanguage | None = None
    study_form: StudyForm | None = None
    needs_dormitory: bool | None = None


class EducationDetailsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    curator_id: int | None = None
    group_number: str | None = None
    course: int | None = None
    payment_type: str | None = None
    is_state_grant: bool
    has_scholarship: bool
    scholarship_amount: int | None = None
    academic_leave: bool
    academic_performance: str | None = None
    completed_at: datetime | None = None
    expulsion_order_number: str | None = None
    expulsion_order_date: date | None = None
    expulsion_reason: str | None = None
    expelled_at: datetime | None = None
    graduated_at: datetime | None = None


class EducationDetailsUpdate(BaseModel):
    curator_id: int | None = None
    group_number: str | None = Field(default=None, max_length=100)
    course: int | None = Field(default=None, ge=1, le=4)
    payment_type: PaymentType | None = None
    is_state_grant: bool | None = None
    has_scholarship: bool | None = None
    scholarship_amount: int | None = Field(default=None, ge=0, le=1_000_000)
    academic_leave: bool | None = None
    academic_performance: AcademicPerformance | None = None


class ExpelRequest(BaseModel):
    order_number: str = Field(min_length=1, max_length=100)
    order_date: date
    reason: str = Field(min_length=3, max_length=2000)


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


class ApplicationTagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime


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
    contest_profile: ContestProfileRead | None = None
    contest_choices: list[ContestChoiceRead] = Field(default_factory=list)
    tags: list[ApplicationTagRead] = Field(default_factory=list)
    contest_visible: bool = False
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


class BulkTagsRequest(BulkIdsRequest):
    tags: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def normalize_tags(self) -> "BulkTagsRequest":
        normalized = []
        for raw_tag in self.tags:
            name = raw_tag.strip().lstrip("#").strip().lower()
            if not name or len(name) > 64 or not re.fullmatch(r"[\w\-]+", name, flags=re.UNICODE):
                raise ValueError("Тег может содержать буквы, цифры, дефис и подчеркивание")
            if name not in normalized:
                normalized.append(name)
        self.tags = normalized
        return self


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
    attachments: list["ChatAttachmentRead"] = Field(default_factory=list)


class ChatAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    content_type: str
    size: int
    created_at: datetime


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
