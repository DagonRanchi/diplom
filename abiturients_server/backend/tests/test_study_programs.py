import unittest
from datetime import date

from app.services.study_programs import calculate_course_dates, load_study_programs, study_duration_years


class StudyProgramTests(unittest.TestCase):
    def test_configured_durations(self) -> None:
        expected = {
            ("2030103", "9 класс"): 4,
            ("2030103", "11 класс"): 3,
            ("2030103", "ТИПО"): 1,
            ("1810102", "9 класс"): 3,
            ("1810102", "11 класс"): 2,
            ("1810102", "ТИПО"): 1,
            ("1810101", "9 класс"): 2,
            ("2161301", "9 класс"): 2,
            ("2161302", "9 класс"): 2,
            ("2161304", "9 класс"): 4,
            ("2161304", "11 класс"): 3,
            ("2161304", "ТИПО"): 2,
            ("2161303", "9 класс"): 3,
            ("1830101", "9 класс"): 3,
            ("1830101", "11 класс"): 2,
        }
        programs = {program.nobd_code: program for program in load_study_programs()}

        self.assertEqual(len(programs), 8)
        for (code, base_class), duration in expected.items():
            self.assertEqual(
                study_duration_years(programs[code].specialty, base_class),
                duration,
            )

    def test_non_final_course_ends_on_august_31(self) -> None:
        self.assertEqual(
            calculate_course_dates(2026, 1, 4),
            (date(2026, 9, 1), date(2027, 8, 31)),
        )

    def test_final_course_ends_on_june_30(self) -> None:
        self.assertEqual(
            calculate_course_dates(2029, 4, 4),
            (date(2029, 9, 1), date(2030, 6, 30)),
        )


if __name__ == "__main__":
    unittest.main()
