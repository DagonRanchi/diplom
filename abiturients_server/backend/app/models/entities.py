from __future__ import annotations

import enum
import secrets
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Role(str, enum.Enum):
    admissions_admin = "admissions_admin"
    education_admin = "education_admin"
    tech_admin = "tech_admin"
    teacher = "teacher"
    assistant = "assistant"


class ApplicationStatus(str, enum.Enum):
    new = "new"
    in_admissions_review = "in_admissions_review"
    in_contest = "in_contest"
    archived_by_admissions = "archived_by_admissions"
    rejected = "rejected"
    accepted_by_admissions = "accepted_by_admissions"
    education_review = "education_review"
    enrolled = "enrolled"
    completed = "completed"
    expelled = "expelled"
    graduated = "graduated"


class PaymentType(str, enum.Enum):
    free = "free"
    paid = "paid"


class EnrollmentType(str, enum.Enum):
    general = "general"
    reinstated = "reinstated"
    transfer = "transfer"


class LocalityType(str, enum.Enum):
    urban = "urban"
    rural = "rural"


class InstructionLanguage(str, enum.Enum):
    russian = "russian"
    kazakh = "kazakh"


class StudyForm(str, enum.Enum):
    full_time = "full_time"
    part_time = "part_time"


class AcademicPerformance(str, enum.Enum):
    excellent = "excellent"
    good = "good"
    satisfactory = "satisfactory"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    curated_students: Mapped[list[EducationDetails]] = relationship(back_populates="curator")
    notifications: Mapped[list[Notification]] = relationship(back_populates="user")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_token: Mapped[str] = mapped_column(String(96), nullable=False, unique=True, default=lambda: secrets.token_urlsafe(32))
    iin: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=ApplicationStatus.new.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    admission_details: Mapped[AdmissionDetails | None] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    education_details: Mapped[EducationDetails | None] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    folder_item: Mapped[FolderItem | None] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    chat: Mapped[Chat | None] = relationship(back_populates="application", cascade="all, delete-orphan", uselist=False)
    rejection: Mapped[Rejection | None] = relationship(back_populates="application", uselist=False)
    contest_profile: Mapped[ContestProfile | None] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    contest_choices: Mapped[list[ContestChoice]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    tags: Mapped[list[ApplicationTag]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class AdmissionDetails(Base):
    __tablename__ = "admission_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False)
    benefit_group: Mapped[str | None] = mapped_column(String(255))
    residence_address: Mapped[str | None] = mapped_column(String(500))
    base_class: Mapped[str | None] = mapped_column(String(64))
    qualification: Mapped[str | None] = mapped_column(String(255))
    specialty: Mapped[str | None] = mapped_column(String(255), index=True)
    enrollment_type: Mapped[str] = mapped_column(String(32), nullable=False, default=EnrollmentType.general.value)
    locality_type: Mapped[str] = mapped_column(String(32), nullable=False, default=LocalityType.urban.value)
    instruction_language: Mapped[str | None] = mapped_column(String(32))
    study_form: Mapped[str] = mapped_column(String(32), nullable=False, default=StudyForm.full_time.value)
    needs_dormitory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    application: Mapped[Application] = relationship(back_populates="admission_details")


class EducationDetails(Base):
    __tablename__ = "education_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False)
    curator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    group_number: Mapped[str | None] = mapped_column(String(100), index=True)
    course: Mapped[int | None] = mapped_column(Integer)
    payment_type: Mapped[str | None] = mapped_column(String(32))
    is_state_grant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_scholarship: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scholarship_amount: Mapped[int | None] = mapped_column(Integer)
    academic_leave: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    academic_performance: Mapped[str | None] = mapped_column(String(32))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expulsion_order_number: Mapped[str | None] = mapped_column(String(100))
    expulsion_order_date: Mapped[date | None] = mapped_column(Date)
    expulsion_reason: Mapped[str | None] = mapped_column(Text)
    expelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graduated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    application: Mapped[Application] = relationship(back_populates="education_details")
    curator: Mapped[User | None] = relationship(back_populates="curated_students")


class Rejection(Base):
    __tablename__ = "rejections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"), unique=True)
    iin: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(64), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rejected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    rejected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application | None] = relationship(back_populates="rejection")
    rejected_by: Mapped[User | None] = relationship()


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), index=True)
    owner_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="all")
    role_scope: Mapped[str | None] = mapped_column(String(64), index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    parent: Mapped[Folder | None] = relationship(remote_side="Folder.id", back_populates="children")
    children: Mapped[list[Folder]] = relationship(back_populates="parent", cascade="all, delete-orphan")
    items: Mapped[list[FolderItem]] = relationship(back_populates="folder", cascade="all, delete-orphan")
    creator: Mapped[User | None] = relationship()

    __table_args__ = (UniqueConstraint("name", "parent_id", name="uq_folder_name_parent"),)


class FolderItem(Base):
    __tablename__ = "folder_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder_id: Mapped[int] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    folder: Mapped[Folder] = relationship(back_populates="items")
    application: Mapped[Application] = relationship(back_populates="folder_item")


class ApplicationTag(Base):
    __tablename__ = "application_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship(back_populates="tags")

    __table_args__ = (UniqueConstraint("application_id", "name", name="uq_application_tag_name"),)


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    application: Mapped[Application] = relationship(back_populates="chat")
    messages: Mapped[list[ChatMessage]] = relationship(back_populates="chat", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sender_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    sender_application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    chat: Mapped[Chat] = relationship(back_populates="messages")
    sender_user: Mapped[User | None] = relationship(foreign_keys=[sender_user_id])
    attachments: Mapped[list[ChatAttachment]] = relationship(back_populates="message", cascade="all, delete-orphan")


class ChatAttachment(Base):
    __tablename__ = "chat_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped[ChatMessage] = relationship(back_populates="attachments")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"))
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="notifications")
    application: Mapped[Application | None] = relationship()


class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    qualification: Mapped[str] = mapped_column(String(255), nullable=False)

    contest_profiles: Mapped[list[ContestProfile]] = relationship(back_populates="accepted_specialty")
    contest_choices: Mapped[list[ContestChoice]] = relationship(back_populates="specialty")


class ContestProfile(Base):
    __tablename__ = "contest_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    benefit_group: Mapped[str | None] = mapped_column(String(255))
    residence_address: Mapped[str | None] = mapped_column(String(500))
    base_class: Mapped[str | None] = mapped_column(String(64), index=True)
    enrollment_type: Mapped[str] = mapped_column(String(32), nullable=False, default=EnrollmentType.general.value)
    locality_type: Mapped[str] = mapped_column(String(32), nullable=False, default=LocalityType.urban.value)
    instruction_language: Mapped[str | None] = mapped_column(String(32))
    study_form: Mapped[str] = mapped_column(String(32), nullable=False, default=StudyForm.full_time.value)
    needs_dormitory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accepted_specialty_id: Mapped[int | None] = mapped_column(
        ForeignKey("specialties.id", ondelete="SET NULL"), index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    application: Mapped[Application] = relationship(back_populates="contest_profile")
    accepted_specialty: Mapped[Specialty | None] = relationship(back_populates="contest_profiles")


class ContestChoice(Base):
    __tablename__ = "contest_choices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    specialty_id: Mapped[int] = mapped_column(
        ForeignKey("specialties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship(back_populates="contest_choices")
    specialty: Mapped[Specialty] = relationship(back_populates="contest_choices")

    __table_args__ = (UniqueConstraint("application_id", "specialty_id", name="uq_contest_application_specialty"),)


Index("ix_applications_search", Application.full_name, Application.iin, Application.phone, Application.email)
