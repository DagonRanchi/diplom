import re


def normalize_name_part(value: str | None) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    if not value:
        return ""
    return "-".join(
        "'".join(piece[:1].upper() + piece[1:].lower() for piece in part.split("'"))
        for part in value.split("-")
    )


def normalize_full_name(value: str) -> str:
    return " ".join(normalize_name_part(part) for part in value.split() if part.strip())


def build_full_name(last_name: str, first_name: str, patronymic: str | None = None) -> str:
    return " ".join(
        part
        for part in (
            normalize_name_part(last_name),
            normalize_name_part(first_name),
            normalize_name_part(patronymic),
        )
        if part
    )
