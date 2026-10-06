import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from google.cloud import ndb
from google.cloud.ndb.exceptions import BadValueError

from constants import MONITORING_ERROR_MESSAGE_MAX_LENGTH
from db import monitoring


class MonitoringModelValidationTest(unittest.TestCase):
    def setUp(self):
        self.context = monitoring.client.context()
        self.context.__enter__()
        self.run_key = ndb.Key(monitoring.Run, "run_test")

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def test_attempts_are_limited_to_two(self):
        with self.assertRaises(ValueError):
            monitoring.CheckResult(
                run=self.run_key,
                check_id="test",
                status="healthy",
                attempts=3,
            )

    def test_negative_duration_and_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            monitoring.CheckResult(
                run=self.run_key,
                check_id="test",
                status="healthy",
                response_time_ms=-1,
            )
        with self.assertRaises(ValueError):
            monitoring.Run(trigger="manual", tier="critical", total=-1)
        with self.assertRaises(ValueError):
            monitoring.CronJobHeartbeat(
                display_name="Job",
                tracking_started_at=datetime.now(),
                last_duration_ms=-1,
            )

    def test_cron_heartbeat_status_is_constrained(self):
        with self.assertRaises(BadValueError):
            monitoring.CronJobHeartbeat(
                display_name="Job",
                tracking_started_at=datetime.now(),
                last_status="unknown",
            )

    def test_error_messages_are_truncated(self):
        result = monitoring.CheckResult(
            run=self.run_key,
            check_id="test",
            status="failed",
            error_message="x" * (MONITORING_ERROR_MESSAGE_MAX_LENGTH + 25),
        )
        self.assertEqual(len(result.error_message), MONITORING_ERROR_MESSAGE_MAX_LENGTH)

    def test_update_helper_rejects_unknown_and_read_only_fields(self):
        run = monitoring.Run(trigger="manual", tier="critical")
        with self.assertRaises(ValueError):
            monitoring._apply_updates(
                run, {"start_time": datetime.now()}, {"start_time"}
            )
        with self.assertRaises(ValueError):
            monitoring._apply_updates(run, {"unknown": True}, set())


class MonitoringHelperValidationTest(unittest.TestCase):
    def test_query_limits_are_bounded_before_datastore_access(self):
        for invalid in (0, 101, -1, True, "20"):
            with self.assertRaises(ValueError):
                monitoring.get_recent_runs(invalid)
            with self.assertRaises(ValueError):
                monitoring.get_results_for_check("check", invalid)

    def test_retention_and_stuck_thresholds_must_be_positive(self):
        with self.assertRaises(ValueError):
            monitoring.delete_old_check_results(0)
        with self.assertRaises(ValueError):
            monitoring.delete_old_monitoring_data(-1)
        with self.assertRaises(ValueError):
            monitoring.get_stuck_runs(0)

    @patch.object(monitoring, "client")
    @patch.object(monitoring.ndb, "Key")
    def test_create_result_requires_an_existing_run(self, key_class, client):
        client.context.return_value.__enter__.return_value = None
        key_class.return_value.get.return_value = None
        with self.assertRaisesRegex(ValueError, "does not exist"):
            monitoring.create_check_result("missing", "check", "healthy")

    def test_since_requires_datetime(self):
        with self.assertRaises(ValueError):
            monitoring.get_results_for_check_since("check", "yesterday")

    def test_monitoring_lease_arguments_are_validated_before_datastore_access(self):
        with self.assertRaises(ValueError):
            monitoring.acquire_monitoring_lease("", 15)
        for invalid in (0, -1, True, "15"):
            with self.assertRaises(ValueError):
                monitoring.acquire_monitoring_lease("owner", invalid)
        with self.assertRaises(ValueError):
            monitoring.release_monitoring_lease("")

    @patch.object(monitoring, "get_results_for_check")
    def test_active_alert_scans_the_current_failure_streak(self, get_results):
        get_results.return_value = [
            type("Result", (), {"status": "failed", "alert_sent": False})(),
            type("Result", (), {"status": "failed", "alert_sent": True})(),
        ]
        self.assertTrue(monitoring.has_active_alert_for_check("check"))

        get_results.return_value = [
            type("Result", (), {"status": "healthy", "alert_sent": False})(),
            type("Result", (), {"status": "failed", "alert_sent": True})(),
        ]
        self.assertFalse(monitoring.has_active_alert_for_check("check"))
        get_results.assert_called_with("check", limit=None)

    @patch.object(monitoring, "get_dashboard_snapshot")
    @patch.object(monitoring, "get_results_for_check")
    def test_active_alert_survives_result_retention(self, get_results, get_snapshot):
        get_results.return_value = [
            type("Result", (), {"status": "failed", "alert_sent": False})()
        ]
        get_snapshot.return_value = type(
            "Snapshot",
            (),
            {"checks": [{"check_id": "check", "alert_active": True}]},
        )()

        self.assertTrue(monitoring.has_active_alert_for_check("check"))

    def test_stuck_cutoff_uses_requested_age(self):
        now = datetime(2026, 10, 4, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
        with patch.object(monitoring, "client") as client, patch.object(
            monitoring.Run, "query"
        ) as query:
            client.context.return_value.__enter__.return_value = None
            query.return_value.fetch.return_value = []
            self.assertEqual(monitoring.get_stuck_runs(15, now=now), [])
            query.assert_called_once()


if __name__ == "__main__":
    unittest.main()
