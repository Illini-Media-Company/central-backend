import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from flask import Flask

from util.monitoring import cron_health


NOW = datetime(2026, 10, 4, 12, 0, tzinfo=ZoneInfo("America/Chicago"))


def heartbeat(**overrides):
    values = {
        "tracking_started_at": NOW - timedelta(days=1),
        "last_started_at": NOW - timedelta(minutes=30),
        "last_completed_at": NOW - timedelta(minutes=29),
        "last_succeeded_at": NOW - timedelta(minutes=29),
        "last_status": "succeeded",
        "last_error": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class CronHealthEvaluationTest(unittest.TestCase):
    @patch.object(cron_health, "ensure_cron_job_heartbeat")
    @patch.object(cron_health, "get_cron_job_heartbeat", return_value=None)
    def test_never_observed_job_uses_then_exhausts_rollout_grace(self, _get, ensure):
        ensure.return_value = heartbeat(
            tracking_started_at=NOW,
            last_started_at=None,
            last_completed_at=None,
            last_succeeded_at=None,
            last_status=None,
        )
        result = cron_health.evaluate_cron_job("job", "Job", 60, 10, now=NOW)
        self.assertEqual(result.status, "degraded")
        self.assertEqual(result.error_type, "not_configured")

        ensure.return_value.tracking_started_at = NOW - timedelta(minutes=61)
        result = cron_health.evaluate_cron_job("job", "Job", 60, 10, now=NOW)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_type, "stale")

    @patch.object(cron_health, "get_cron_job_heartbeat")
    def test_success_failure_stale_and_stuck_states(self, get_heartbeat):
        get_heartbeat.return_value = heartbeat()
        self.assertEqual(
            cron_health.evaluate_cron_job("job", "Job", 60, 10, now=NOW).status,
            "healthy",
        )

        get_heartbeat.return_value = heartbeat(last_status="failed", last_error="boom")
        failed = cron_health.evaluate_cron_job("job", "Job", 60, 10, now=NOW)
        self.assertEqual((failed.status, failed.error_type), ("failed", "job_failed"))

        get_heartbeat.return_value = heartbeat(
            last_started_at=NOW - timedelta(minutes=11), last_status="running"
        )
        stuck = cron_health.evaluate_cron_job("job", "Job", 60, 10, now=NOW)
        self.assertEqual((stuck.status, stuck.error_type), ("failed", "stuck"))

        get_heartbeat.return_value = heartbeat(
            last_started_at=NOW - timedelta(hours=2),
            last_completed_at=NOW - timedelta(hours=2),
            last_succeeded_at=NOW - timedelta(hours=2),
        )
        stale = cron_health.evaluate_cron_job("job", "Job", 60, 10, now=NOW)
        self.assertEqual((stale.status, stale.error_type), ("failed", "stale"))


class CronTrackingDecoratorTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

        @self.app.route("/success")
        @cron_health.track_cron_job("job", "Job")
        def success():
            return {"success": True}, 200

        @self.app.route("/failure")
        @cron_health.track_cron_job("job", "Job")
        def failure():
            return {"success": False, "error": "boom"}, 500

        @self.app.route("/crash")
        @cron_health.track_cron_job("job", "Job")
        def crash():
            raise RuntimeError("crashed")

        self.client = self.app.test_client()

    @patch.object(cron_health, "finish_cron_job")
    @patch.object(cron_health, "begin_cron_job")
    def test_only_genuine_cron_calls_are_tracked(self, begin, finish):
        self.assertEqual(self.client.get("/success").status_code, 200)
        begin.assert_not_called()

        response = self.client.get("/success", headers={"X-Appengine-Cron": "true"})
        self.assertEqual(response.status_code, 200)
        begin.assert_called_once()
        self.assertTrue(finish.call_args.args[2])
        self.assertEqual(finish.call_args.kwargs["http_status"], 200)

    @patch.object(cron_health, "finish_cron_job")
    @patch.object(cron_health, "begin_cron_job")
    def test_failed_response_is_recorded_without_changing_it(self, begin, finish):
        response = self.client.get("/failure", headers={"X-Appengine-Cron": "true"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["error"], "boom")
        self.assertFalse(finish.call_args.args[2])
        self.assertEqual(finish.call_args.kwargs["error_message"], "boom")

    @patch.object(cron_health, "finish_cron_job")
    @patch.object(cron_health, "begin_cron_job", side_effect=RuntimeError("down"))
    def test_heartbeat_storage_failure_does_not_break_job(self, _begin, finish):
        response = self.client.get("/success", headers={"X-Appengine-Cron": "true"})
        self.assertEqual(response.status_code, 200)
        finish.assert_not_called()

    @patch.object(cron_health, "finish_cron_job", side_effect=RuntimeError("down"))
    @patch.object(cron_health, "begin_cron_job")
    def test_finish_storage_failure_does_not_change_response(self, _begin, _finish):
        response = self.client.get("/success", headers={"X-Appengine-Cron": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True})

    @patch.object(cron_health, "finish_cron_job")
    @patch.object(cron_health, "begin_cron_job")
    def test_unhandled_exception_is_recorded_and_reraised(self, _begin, finish):
        with self.app.test_request_context(
            "/crash", headers={"X-Appengine-Cron": "true"}
        ):
            view = self.app.view_functions["crash"]
            with self.assertRaisesRegex(RuntimeError, "crashed"):
                view()
        self.assertFalse(finish.call_args.args[2])
        self.assertEqual(finish.call_args.kwargs["http_status"], 500)


if __name__ == "__main__":
    unittest.main()
