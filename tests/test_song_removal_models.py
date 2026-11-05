import unittest

from google.cloud.ndb.exceptions import BadValueError

from db.song_removal_request import (
    SongRemovalOwnershipError,
    SongRemovalRequest,
    SongRemovalTransitionConflict,
    _apply_claim,
    _apply_resolution,
    _apply_take_over,
    build_song_key,
)


class SongRemovalModelTest(unittest.TestCase):
    def make_report(self, status="pending", reviewer_email=None):
        return SongRemovalRequest(
            song_name="Song",
            artist_name="Artist",
            song_key="song|artist|",
            reason="audio_defect",
            submitter_name="Submitter",
            submitter_email="submitter@illinimedia.com",
            status=status,
            reviewer_email=reviewer_email,
            reviewer_name="Reviewer" if reviewer_email else None,
        )

    def test_song_key_normalizes_case_unicode_and_whitespace(self):
        self.assertEqual(
            build_song_key("  Don’t   Stop ", " THE—BAND ", " Clean  Edit "),
            "don't stop|the-band|clean edit",
        )

    def test_reason_and_status_are_constrained(self):
        with self.assertRaises(BadValueError):
            self.make_report().reason = "unsupported"
        with self.assertRaises(BadValueError):
            self.make_report().status = "deleted"

    def test_claim_is_idempotent_for_same_reviewer(self):
        report = self.make_report()
        changed = _apply_claim(
            report,
            reviewer_name="Reviewer",
            reviewer_email="reviewer@illinimedia.com",
            reviewer_slack_id="U123",
        )
        self.assertTrue(changed)
        self.assertEqual(report.status, "in_progress")
        self.assertFalse(
            _apply_claim(
                report,
                reviewer_name="Reviewer",
                reviewer_email="reviewer@illinimedia.com",
                reviewer_slack_id="U123",
            )
        )
        with self.assertRaises(SongRemovalTransitionConflict):
            _apply_claim(
                report,
                reviewer_name="Other",
                reviewer_email="other@illinimedia.com",
                reviewer_slack_id="U456",
            )

    def test_take_over_changes_owner_only_while_in_progress(self):
        report = self.make_report(
            status="in_progress", reviewer_email="reviewer@illinimedia.com"
        )
        self.assertTrue(
            _apply_take_over(
                report,
                reviewer_name="Other",
                reviewer_email="other@illinimedia.com",
                reviewer_slack_id="U456",
            )
        )
        self.assertEqual(report.reviewer_email, "other@illinimedia.com")
        with self.assertRaises(SongRemovalTransitionConflict):
            _apply_take_over(
                self.make_report(),
                reviewer_name="Other",
                reviewer_email="other@illinimedia.com",
                reviewer_slack_id="U456",
            )

    def test_only_owner_can_resolve_and_resolution_is_terminal(self):
        report = self.make_report(
            status="in_progress", reviewer_email="reviewer@illinimedia.com"
        )
        with self.assertRaises(SongRemovalOwnershipError):
            _apply_resolution(
                report,
                status="actioned",
                resolution_notes="Fixed",
                reviewer_email="other@illinimedia.com",
            )

        self.assertTrue(
            _apply_resolution(
                report,
                status="actioned",
                resolution_notes="Fixed",
                reviewer_email="reviewer@illinimedia.com",
            )
        )
        self.assertIsNotNone(report.resolved_at)
        self.assertFalse(
            _apply_resolution(
                report,
                status="actioned",
                resolution_notes="Fixed",
                reviewer_email="reviewer@illinimedia.com",
            )
        )
        with self.assertRaises(SongRemovalTransitionConflict):
            _apply_resolution(
                report,
                status="no_action",
                resolution_notes="Changed decision",
                reviewer_email="reviewer@illinimedia.com",
            )


if __name__ == "__main__":
    unittest.main()
