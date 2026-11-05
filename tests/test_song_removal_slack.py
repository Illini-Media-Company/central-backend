import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import constants

# Slack Bolt otherwise performs a live auth.test while the handler module imports.
constants.ENV = "test"

from util.slackbots import song_removal_request as slack


class FakeKey:
    def id(self):
        return 42


def fake_report(status="pending"):
    return SimpleNamespace(
        key=FakeKey(),
        song_name="<!channel> Song",
        artist_name="Artist",
        song_version="Clean",
        reason="audio_defect",
        details="<@U123> details",
        submitter_name="Employee",
        submitter_email="employee@illinimedia.com",
        submitter_slack_id="U1",
        status=status,
        reviewer_name="Reviewer" if status != "pending" else None,
        reviewer_email=("reviewer@illinimedia.com" if status != "pending" else None),
        reviewer_slack_id="U2" if status != "pending" else None,
        resolution_notes="Handled" if status in ("actioned", "no_action") else None,
        slack_channel_id="C1",
        slack_ts="123.456",
        slack_error=None,
        confirmation_dm_sent_at=None,
        resolution_dm_sent_at=None,
        created_at=datetime(2026, 11, 1),
    )


class SongRemovalSlackTest(unittest.TestCase):
    def test_blocks_use_plain_text_and_status_specific_actions(self):
        pending = slack.build_song_removal_blocks(fake_report("pending"))
        block_text_types = []
        for block in pending:
            if "text" in block and isinstance(block["text"], dict):
                block_text_types.append(block["text"].get("type"))
            for field in block.get("fields", []):
                block_text_types.append(field.get("type"))
        self.assertNotIn("mrkdwn", block_text_types)
        pending_actions = pending[-1]["elements"]
        self.assertEqual(pending_actions[0]["action_id"], "song_removal_claim")

        in_progress = slack.build_song_removal_blocks(fake_report("in_progress"))
        action_ids = {item["action_id"] for item in in_progress[-1]["elements"]}
        self.assertEqual(
            action_ids,
            {
                "song_removal_actioned",
                "song_removal_no_action",
                "song_removal_take_over",
            },
        )
        resolved = slack.build_song_removal_blocks(fake_report("actioned"))
        self.assertNotEqual(resolved[-1].get("type"), "actions")

    @patch.object(slack, "update_song_removal_slack_state")
    def test_missing_channel_is_recorded_without_posting(self, update_state):
        with patch.object(slack, "WPGU_SONG_REMOVAL_REQUESTS_ID", None):
            result = slack.post_report_to_slack(fake_report())
        self.assertFalse(result["ok"])
        update_state.assert_called_once()

    @patch.object(slack, "get_user")
    @patch.object(slack.app.client, "users_info")
    def test_slack_actor_requires_reviewer_group(self, users_info, get_user):
        users_info.return_value = {
            "user": {
                "real_name": "Reviewer",
                "profile": {
                    "email": "reviewer@illinimedia.com",
                    "real_name": "Reviewer",
                },
            }
        }
        get_user.return_value = SimpleNamespace(groups=["unrelated"])
        self.assertIsNone(slack._slack_actor("U2"))
        get_user.return_value = SimpleNamespace(groups=["wpgu-directors"])
        actor = slack._slack_actor("U2")
        self.assertEqual(actor["email"], "reviewer@illinimedia.com")

    @patch.object(slack, "mark_song_removal_dm_sent")
    @patch.object(slack, "dm_channel_by_id", return_value={"ok": True})
    def test_resolution_dm_contains_status_and_notes_once(self, _dm, mark_sent):
        report = fake_report("no_action")
        result = slack.send_resolution_dm(report)
        self.assertTrue(result["ok"])
        sent_text = _dm.call_args.kwargs["text"]
        self.assertIn("No Action", sent_text)
        self.assertIn("Handled", sent_text)
        mark_sent.assert_called_once_with(42, resolution=True)

    @patch.object(slack, "_ephemeral")
    @patch.object(slack, "claim_report")
    @patch.object(slack, "_slack_actor", return_value=None)
    def test_unauthorized_slack_actor_cannot_claim(
        self, _actor, claim_report, ephemeral
    ):
        body = {
            "user": {"id": "U2"},
            "container": {"channel_id": "C1"},
            "actions": [{"value": "42"}],
        }
        slack._process_claim(body)
        claim_report.assert_not_called()
        ephemeral.assert_called_once()

    @patch.object(slack, "_ephemeral")
    @patch.object(slack, "send_resolution_dm")
    @patch.object(slack, "sync_report_to_slack")
    @patch.object(slack, "resolve_report")
    @patch.object(
        slack,
        "_slack_actor",
        return_value={
            "name": "Reviewer",
            "email": "reviewer@illinimedia.com",
            "slack_id": "U2",
        },
    )
    def test_slack_resolution_uses_shared_workflow(
        self, _actor, resolve_report, sync, send_dm, ephemeral
    ):
        report = fake_report("actioned")
        resolve_report.return_value = (report, True)
        body = {"user": {"id": "U2"}}
        metadata = {"report_id": "42", "status": "actioned", "channel_id": "C1"}
        slack._process_resolution(body, metadata, "Removed defective file")
        resolve_report.assert_called_once_with(
            "42",
            {"status": "actioned", "resolution_notes": "Removed defective file"},
            reviewer_email="reviewer@illinimedia.com",
        )
        sync.assert_called_once_with(report)
        send_dm.assert_called_once_with(report)
        ephemeral.assert_called_once()


if __name__ == "__main__":
    unittest.main()
