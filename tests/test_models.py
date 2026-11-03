import unittest

from review_harness.models import (
    abstract_from_inverted_index,
    is_research_work,
    normalize_doi,
    normalize_title,
    paper_from_openalex,
    rolling_two_year_window,
)


class ModelTests(unittest.TestCase):
    def test_normalization(self) -> None:
        self.assertEqual(normalize_doi("https://doi.org/10.1000/ABC"), "10.1000/abc")
        self.assertEqual(normalize_title("UV-Based: Spectrometer!"), "uv based spectrometer")

    def test_research_work_filter(self) -> None:
        self.assertTrue(is_research_work({"type": "article"}))
        self.assertTrue(is_research_work({"type": "preprint"}))
        self.assertFalse(is_research_work({"type": "review"}))
        self.assertFalse(is_research_work({"type": "editorial"}))

    def test_two_year_window_and_leap_day(self) -> None:
        from datetime import date

        self.assertEqual(rolling_two_year_window(date(2026, 11, 3)), ("2024-11-03", "2026-11-03"))
        self.assertEqual(rolling_two_year_window(date(2024, 2, 29)), ("2022-02-28", "2024-02-29"))

    def test_openalex_abstract_and_record(self) -> None:
        work = {
            "id": "https://openalex.org/W123",
            "doi": "https://doi.org/10.1000/example",
            "title": "A UV Computational Spectrometer",
            "publication_date": "2026-01-02",
            "publication_year": 2026,
            "type": "article",
            "abstract_inverted_index": {"A": [0], "compact": [1], "device": [2]},
            "primary_location": {
                "source": {
                    "display_name": "Example Journal",
                    "issn_l": "1234-5678",
                }
            },
            "cited_by_count": 2,
        }
        record = paper_from_openalex(work, "2026-11-03T00:00:00+00:00")
        self.assertEqual(record["paper_id"], "W123")
        self.assertEqual(record["abstract"], "A compact device")
        self.assertEqual(record["doi"], "10.1000/example")

    def test_invalid_year_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            paper_from_openalex({"title": "Missing year"}, "2026-11-03T00:00:00+00:00")

    def test_empty_inverted_index(self) -> None:
        self.assertIsNone(abstract_from_inverted_index(None))


if __name__ == "__main__":
    unittest.main()
