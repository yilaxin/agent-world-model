from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_world_model.human_review import (
    apply_approved_reviews,
    build_review_queue,
    read_review_csv,
    validated_human_labels,
    write_review_csv,
)
from tests.test_phase2_schema import sample_record


class HumanReviewTests(unittest.TestCase):
    def test_queue_round_trip_and_explicit_approval(self) -> None:
        record = sample_record()
        rows = build_review_queue([record])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["review_status"], "pending")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            write_review_csv(path, rows)
            loaded = read_review_csv(path)
        self.assertEqual(loaded[0]["example_id"], rows[0]["example_id"])

        loaded[0]["review_status"] = "approved"
        loaded[0]["reviewer"] = "reviewer-a"
        reviewed, audit = apply_approved_reviews([record], loaded)
        self.assertEqual(audit["matched_records"], 1)
        self.assertEqual(reviewed[0]["label_source"], "human_verified")
        self.assertEqual(reviewed[0]["metadata"]["human_review"]["reviewer"], "reviewer-a")

    def test_invalid_labels_are_rejected(self) -> None:
        row = build_review_queue([sample_record()])[0]
        row["review_status"] = "approved"
        row["reviewer"] = "reviewer-a"
        row["terminal"] = "maybe"
        with self.assertRaises(ValueError):
            validated_human_labels(row)

    def test_evidence_review_never_claims_human_signoff(self) -> None:
        record = sample_record()
        row = build_review_queue([record])[0]
        row["review_status"] = "evidence_approved"
        row["reviewer"] = "codex-evidence-review-v1"
        reviewed, audit = apply_approved_reviews([record], [row])
        self.assertEqual(audit["evidence_approved_rows"], 1)
        self.assertEqual(audit["human_approved_rows"], 0)
        self.assertEqual(reviewed[0]["label_source"], "evidence_verified")
        self.assertFalse(reviewed[0]["metadata"]["evidence_review"]["human_signoff"])
        self.assertNotIn("human_review", reviewed[0]["metadata"])

    def test_pending_rows_never_override_labels(self) -> None:
        rows = build_review_queue([sample_record()])
        reviewed, audit = apply_approved_reviews([sample_record()], rows)
        self.assertEqual(reviewed, [])
        self.assertEqual(audit["approved_rows"], 0)


if __name__ == "__main__":
    unittest.main()
