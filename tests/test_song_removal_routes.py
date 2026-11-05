import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
from flask_login import LoginManager, UserMixin

import constants

# Slack Bolt otherwise performs a live auth.test while the route module imports.
constants.ENV = "test"

from db.song_removal_request import SongRemovalTransitionConflict
from views import song_removal_request as routes


class FakeKey:
    def id(self):
        return 42


def fake_report():
    return SimpleNamespace(
        key=FakeKey(),
        song_name="Song",
        artist_name="Artist",
        song_version=None,
        song_key="song|artist|",
        reason="audio_defect",
        details="Details",
        submitter_name="Employee",
        submitter_email="employee@illinimedia.com",
        submitter_slack_id="U1",
        status="pending",
        reviewer_name=None,
        reviewer_email=None,
        reviewer_slack_id=None,
        resolution_notes=None,
        created_at=datetime(2026, 11, 1, 12, 0),
        updated_at=datetime(2026, 11, 1, 12, 0),
        resolved_at=None,
        slack_channel_id=None,
        slack_ts=None,
        slack_error="Slack unavailable",
        slack_synced_at=None,
        confirmation_dm_sent_at=None,
        resolution_dm_sent_at=None,
    )


class User(UserMixin):
    def __init__(self):
        self.id = "employee@illinimedia.com"
        self.email = self.id
        self.name = "Employee"
        self.groups = ["imc-staff-webdev"]


class SongRemovalRoutesTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SECRET_KEY="test")
        app.register_blueprint(routes.song_removal_request_routes)
        login_manager = LoginManager(app)
        self.user = User()

        @login_manager.user_loader
        def load_user(_user_id):
            return self.user

        self.client = app.test_client()

    def login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = self.user.id
            session["_fresh"] = True

    def test_options_requires_login(self):
        denied = self.client.get("/wpgu-song-removal-requests/api/options")
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(denied.get_json()["code"], "authentication_required")
        self.login()
        response = self.client.get("/wpgu-song-removal-requests/api/options")
        self.assertEqual(response.status_code, 200)
        self.assertIn("reasons", response.get_json())

    @patch.object(routes, "get_report")
    @patch.object(routes, "send_submission_dm", return_value={"ok": True})
    @patch.object(routes, "post_report_to_slack", return_value={"ok": False})
    @patch.object(routes, "create_report")
    @patch.object(routes, "_employee_slack_id", return_value="U1")
    def test_submission_uses_session_identity_and_survives_slack_failure(
        self, _slack_id, create, _post, _dm, get_report
    ):
        report = fake_report()
        create.return_value = report
        get_report.return_value = report
        self.login()
        response = self.client.post(
            "/wpgu-song-removal-requests/api/reports",
            json={
                "song_name": "Song",
                "artist_name": "Artist",
                "reason": "audio_defect",
                "submitter_email": "spoofed@example.com",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.get_json()["notifications"]["slack_posted"])
        self.assertEqual(response.get_json()["report"]["available_actions"], [])
        self.assertEqual(create.call_args.kwargs["submitter_email"], self.user.email)
        self.assertEqual(create.call_args.kwargs["submitter_name"], self.user.name)

    @patch.object(routes, "group_reports", return_value={"groups": []})
    def test_grouped_list_requires_reviewer_group(self, group_reports):
        self.login()
        self.user.groups = ["unrelated"]
        denied = self.client.get("/wpgu-song-removal-requests/api/reports")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["code"], "forbidden")
        self.user.groups = ["wpgu-directors"]
        allowed = self.client.get(
            "/wpgu-song-removal-requests/api/reports?status=pending&q=song"
        )
        self.assertEqual(allowed.status_code, 200)
        group_reports.assert_called_once_with(
            actor_email=self.user.email,
            status="pending",
            reason=None,
            query="song",
        )

    @patch.object(
        routes,
        "claim_report",
        side_effect=SongRemovalTransitionConflict("Already claimed."),
    )
    @patch.object(routes, "_employee_slack_id", return_value=None)
    def test_transition_conflict_is_structured(self, _slack_id, _claim):
        self.login()
        response = self.client.post(
            "/wpgu-song-removal-requests/api/reports/42/claim", json={}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "invalid_status_transition")

    @patch.object(routes, "get_report")
    @patch.object(routes, "claim_report")
    @patch.object(routes, "_employee_slack_id", return_value=None)
    def test_idempotent_claim_does_not_report_stale_slack_as_synced(
        self, _slack_id, claim_report, get_report
    ):
        report = fake_report()
        report.status = "in_progress"
        report.reviewer_name = self.user.name
        report.reviewer_email = self.user.email
        claim_report.return_value = (report, False)
        get_report.return_value = report
        self.login()

        response = self.client.post(
            "/wpgu-song-removal-requests/api/reports/42/claim", json={}
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["changed"])
        self.assertFalse(response.get_json()["slack_synced"])

    @patch.object(routes, "get_report")
    @patch.object(routes, "send_resolution_dm", return_value={"ok": True})
    @patch.object(routes, "_safe_sync", return_value={"ok": True})
    @patch.object(routes, "resolve_report")
    def test_resolution_updates_slack_and_notifies_submitter_once(
        self, resolve_report, sync, send_dm, get_report
    ):
        report = fake_report()
        report.status = "actioned"
        report.reviewer_name = self.user.name
        report.reviewer_email = self.user.email
        report.resolution_notes = "Removed the defective file."
        resolve_report.return_value = (report, True)
        get_report.return_value = report
        self.login()
        response = self.client.post(
            "/wpgu-song-removal-requests/api/reports/42/resolve",
            json={
                "status": "actioned",
                "resolution_notes": "Removed the defective file.",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["changed"])
        resolve_report.assert_called_once_with(
            "42",
            {
                "status": "actioned",
                "resolution_notes": "Removed the defective file.",
            },
            reviewer_email=self.user.email,
        )
        sync.assert_called_once_with(report)
        send_dm.assert_called_once_with(report)


if __name__ == "__main__":
    unittest.main()
