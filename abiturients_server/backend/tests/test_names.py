import unittest

from app.services.names import build_full_name, normalize_full_name


class NameNormalizationTests(unittest.TestCase):
    def test_normalizes_case_and_hyphenated_names(self) -> None:
        self.assertEqual(
            normalize_full_name("  АБДУЛЛАЕВ   НУР-АЛИ  СЕРИКОВИЧ "),
            "Абдуллаев Нур-Али Серикович",
        )

    def test_builds_name_without_patronymic(self) -> None:
        self.assertEqual(
            build_full_name("САРСЕНОВА", "АЯНА", ""),
            "Сарсенова Аяна",
        )


if __name__ == "__main__":
    unittest.main()
