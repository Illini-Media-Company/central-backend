import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from util import song_removal_request as service


class FakeKey:
    def __init__(self, value):
        self.value = value

    def id(self):
        return self.value


def make_report(
    uid,
    *,
    song="Song",
    artist="Artist",
    version=None,
    reason="audio_defect",
    status="pending",
    created_at=None,
    reviewer_email=None,
):
    return SimpleNamespace(
        key=FakeKey(uid),
        song_name=song,
        artist_name=artist,
        song_version=version,
        song_key=service.build_song_key(song, artist, version),
        reason=reason,
        details="Details",
        submitter_name="Submitter",
        submitter_email="submitter@illinimedia.com",
        submitter_slack_id="U1",
        status=status,
        reviewer_name="Reviewer" if reviewer_email else None,
        reviewer_email=reviewer_email,
        reviewer_slack_id="U2" if reviewer_email else None,
        resolution_notes=None,
        created_at=created_at or datetime(2026, 11, 1, 12, 0),
        updated_at=created_at or datetime(2026, 11, 1, 12, 0),
        resolved_at=None,
        slack_channel_id=None,
        slack_ts=None,
        slack_error=None,
        slack_synced_at=None,
    )


class SongRemovalServiceTest(unittest.TestCase):
    def test_submission_validation_and_other_details(self):
        clean = service.validate_submission(
            {
                "song_name": " Song ",
                "artist_name": " Artist ",
                "reason": "audio_defect",
            }
        )
        self.assertEqual(clean["song_name"], "Song")
        with self.assertRaisesRegex(service.SongRemovalValidationError, "Details"):
            service.validate_submission(
                {"song_name": "Song", "artist_name": "Artist", "reason": "other"}
            )

    def test_resolution_requires_valid_status_and_notes(self):
        with self.assertRaises(service.SongRemovalValidationError):
            service.validate_resolution({"status": "pending", "resolution_notes": "x"})
        with self.assertRaises(service.SongRemovalValidationError):
            service.validate_resolution({"status": "actioned", "resolution_notes": ""})

    @patch.object(service, "get_all_song_removal_requests")
    def test_grouped_response_has_total_and_matching_counts(self, get_all):
        newest = datetime(2026, 11, 2, 12, 0)
        get_all.return_value = [
            make_report(1, status="pending", created_at=newest),
            make_report(
                2,
                song=" song ",
                artist="ARTIST",
                status="actioned",
                created_at=newest - timedelta(days=1),
            ),
            make_report(3, song="Other", artist="Artist", created_at=newest),
        ]
        result = service.group_reports(
            actor_email="reviewer@illinimedia.com", status="pending"
        )
        self.assertEqual(result["total_report_count"], 3)
        self.assertEqual(result["matching_report_count"], 2)
        song_group = next(
            group for group in result["groups"] if group["song_key"] == "song|artist|"
        )
        self.assertEqual(song_group["report_count"], 2)
        self.assertEqual(song_group["matching_report_count"], 1)

    def test_available_actions_follow_owner_and_slack_state(self):
        report = make_report(
            1,
            status="in_progress",
            reviewer_email="reviewer@illinimedia.com",
        )
        self.assertEqual(
            service.available_actions(report, "reviewer@illinimedia.com"),
            ["resolve", "retry_slack"],
        )
        self.assertEqual(
            service.available_actions(report, "other@illinimedia.com"),
            ["take_over", "retry_slack"],
        )


if __name__ == "__main__":
    unittest.main()
