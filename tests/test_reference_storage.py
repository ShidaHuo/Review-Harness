import tempfile
import unittest
from pathlib import Path

from review_harness.reference_storage import (
    attach_bundled_nature_index_snapshot,
    load_bundled_nature_index,
    nature_index_journal_names,
    nature_index_snapshot_for_topic,
    normalize_publication_name,
)
from review_harness.storage import create_topic_run


class ReferenceStorageTests(unittest.TestCase):
    def test_bundled_nature_index_has_all_177_publications(self) -> None:
        payload = load_bundled_nature_index()
        self.assertEqual(len(payload["publications"]), 177)
        self.assertEqual(payload["stated_journal_count"], 176)
        self.assertEqual(payload["stated_other_venue_count"], 1)
        names = nature_index_journal_names(payload)
        self.assertIn(normalize_publication_name("Advanced Materials"), names)
        self.assertIn(normalize_publication_name("Energy & Environmental Science"), names)
        self.assertNotIn(
            normalize_publication_name("IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)"),
            names,
        )
        self.assertNotIn(
            normalize_publication_name("Monthly Notices of the Royal Astronomical Society"),
            names,
        )

    def test_bundled_snapshot_attaches_to_topic_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            db_path = Path(temporary_directory) / "research.sqlite3"
            run_id = create_topic_run(db_path, "test topic", {
                "topic": {"canonical_zh": "测试"},
                "queries": [{
                    "id": "direct-01",
                    "scope": "direct",
                    "provider": "openalex",
                    "query": "test topic",
                }],
            })
            snapshot_id = attach_bundled_nature_index_snapshot(db_path, run_id)
            snapshot = nature_index_snapshot_for_topic(db_path, run_id)
            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot["id"], snapshot_id)
            self.assertEqual(len(snapshot["publications"]), 177)


if __name__ == "__main__":
    unittest.main()
