from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.models import Application, EducationDetails


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "nobd_specialties.json"


@dataclass(frozen=True)
class StudyProgram:
    nobd_code: str
    specialty: str
    durations: dict[str, int]


@lru_cache(maxsize=1)
def load_study_programs() -> tuple[StudyProgram, ...]:
    with DATA_PATH.open(encoding="utf-8") as source:
        items = json.load(source)
    return tuple(
        StudyProgram(
            nobd_code=str(item["nobd_code"]),
            specialty=item["specialty"],
            durations={str(base): int(years) for base, years in item["durations"].items()},
        )
        for item in items
    )


def normalize_base_class(base_class: str | None) -> str | None:
    if not base_class:
        return None
    normalized = base_class.strip().casefold()
    if normalized == "типо":
        return "ТИПО"
    if normalized in {"9 класс", "11 класс"}:
        return normalized
    return base_class.strip()


def find_study_program(specialty: str | None) -> StudyProgram | None:
    if not specialty:
        return None
    normalized = specialty.strip().casefold()
    return next(
        (program for program in load_study_programs() if program.specialty.casefold() == normalized),
        None,
    )


def study_duration_years(specialty: str | None, base_class: str | None) -> int | None:
    program = find_study_program(specialty)
    normalized_base = normalize_base_class(base_class)
    if not program or not normalized_base:
        return None
    return program.durations.get(normalized_base)


def calculate_course_dates(
    academic_start_year: int,
    course: int,
    duration_years: int | None,
) -> tuple[date, date]:
    start_date = date(academic_start_year, 9, 1)
    is_final_course = duration_years is not None and course >= duration_years
    end_date = (
        date(academic_start_year + 1, 6, 30)
        if is_final_course
        else date(academic_start_year + 1, 8, 31)
    )
    return start_date, end_date


def sync_study_schedule(
    app: Application,
    details: EducationDetails,
    academic_start_year: int | None = None,
) -> None:
    admission = app.admission_details
    specialty = admission.specialty if admission else None
    base_class = admission.base_class if admission else None
    program = find_study_program(specialty)
    duration_years = study_duration_years(specialty, base_class)
    course = details.course or 1

    details.nobd_specialty_code = program.nobd_code if program else None
    details.study_duration_years = duration_years

    if academic_start_year is None:
        application_year = app.created_at.year if app.created_at else date.today().year
        academic_start_year = application_year + course - 1

    details.course_start_date, details.course_end_date = calculate_course_dates(
        academic_start_year,
        course,
        duration_years,
    )
