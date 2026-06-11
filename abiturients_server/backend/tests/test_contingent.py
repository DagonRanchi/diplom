import csv
import io
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models import Application, Folder
from app.services.contingent import MINIMAL_HEADERS, build_contingent_export, import_contingent


def contingent_file() -> bytes:
    values = {
        "EI Контингента": "EI-1",
        "ID контингента": "ID-1",
        "ИИН": '="060101500001"',
        "Фамилия": "САРСЕНОВА",
        "Имя": "АЯНА",
        "Отчество": "",
        "Дата рождения": "2006-01-01",
        "Дата прибытия/зачисления [267]": "2025-09-01",
        "Из числа принятых, окончил(-а): [5573]": "основную школу",
        "Срок обучения [6129]": "4 года",
        "Курс обучения [5802]": "1 курс",
        "Код группы [6159]": '="25ПО-11р"',
        "Язык обучения [209]": "русский",
        "Форма обучения [5568]": "очная",
        "Специальность и классификатор (основной) [426]": "4S06130103 Разработчик программного обеспечения",
        "Специальность [speciality_a]": "06130100 Программное обеспечение",
        "Квалификация [qualification_a]": "4S06130103 Разработчик программного обеспечения",
    }
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\r\n")
    writer.writerow(MINIMAL_HEADERS)
    writer.writerow([values.get(header, "") for header in MINIMAL_HEADERS])
    return output.getvalue().encode("utf-16")


class ContingentImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_import_creates_group_and_preserves_export_shape(self) -> None:
        content = contingent_file()
        with Session(self.engine) as db:
            result = import_contingent(db, content, "contingent.csv", 1)
            db.commit()

            app = db.scalar(select(Application))
            root = db.scalar(select(Folder).where(Folder.name == "Группы", Folder.parent_id.is_(None)))
            group_count = db.scalar(select(func.count(Folder.id)).where(Folder.parent_id == root.id))
            exported = list(csv.reader(io.StringIO(build_contingent_export(db).decode("utf-16")), delimiter="\t"))

            self.assertEqual(result.created_count, 1)
            self.assertEqual(app.full_name, "Сарсенова Аяна")
            self.assertEqual(group_count, 1)
            self.assertEqual(len(exported[0]), len(MINIMAL_HEADERS))
            self.assertEqual(len(exported), 2)

            with self.assertRaises(HTTPException) as duplicate:
                import_contingent(db, content, "contingent.csv", 1)
            self.assertEqual(duplicate.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
