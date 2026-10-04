import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from util import monitoring

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=ZoneInfo("America/Chicago"))


def result(
    status, alert_sent=False, tier="critical", hours_ago=0, check_id="datastore"
):
    return SimpleNamespace(
        check_id=check_id,
        check_name="Datastore",
        status=status,
        alert_sent=alert_sent,
        tier=tier,
        checked_at=NOW - timedelta(hours=hours_ago),
        response_time_ms=120,
    )


class ComputeStatusTest(unittest.TestCase):
    def test_failed_when_not_ok(self):
        self.assertEqual(monitoring.compute_status(False, 10, 500), "failed")

    def test_failed_wins_over_latency(self):
        self.assertEqual(monitoring.compute_status(False, 900, 500), "failed")

    def test_degraded_when_over_threshold(self):
        self.assertEqual(monitoring.compute_status(True, 501, 500), "degraded")

    def test_healthy_at_exact_threshold(self):
        self.assertEqual(monitoring.compute_status(True, 500, 500), "healthy")

    def test_healthy_with_no_threshold(self):
        self.assertEqual(monitoring.compute_status(True, 99999, None), "healthy")

    def test_healthy_with_no_response_time(self):
        self.assertEqual(monitoring.compute_status(True, None, 500), "healthy")


class SaveResultTest(unittest.TestCase):
    @patch("util.monitoring.create_check_result")
    def test_snapshots_definition_fields(self, create):
        definition = {
            "id": "song_requests_api",
            "name": "Song Requests API",
            "params": {"target": "/api/song-requests"},
            "tier": "full",
            "severity": "minor",
            "latency_threshold_ms": 1000,
        }
        outcome = {"status": "failed", "error_type": "timeout", "error_message": "x"}

        monitoring.save_result("run_1", definition, outcome)

        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["run_id"], "run_1")
        self.assertEqual(kwargs["check_id"], "song_requests_api")
        self.assertEqual(kwargs["check_name"], "Song Requests API")
        self.assertEqual(kwargs["target"], "/api/song-requests")
        self.assertEqual(kwargs["tier"], "full")
        self.assertEqual(kwargs["severity"], "minor")
        self.assertEqual(kwargs["latency_threshold_ms"], 1000)
        self.assertEqual(kwargs["attempts"], 1)

    @patch("util.monitoring.create_check_result")
    def test_no_target_without_params(self, create):
        monitoring.save_result("run_1", {"id": "datastore"}, {"status": "healthy"})
        self.assertIsNone(create.call_args.kwargs["target"])


class FinishRunTest(unittest.TestCase):
    @patch("util.monitoring.update_run")
    @patch("util.monitoring.get_results_for_run")
    def test_counts_are_correct(self, get_results, update):
        get_results.return_value = [
            result("healthy"),
            result("healthy"),
            result("degraded"),
            result("failed"),
        ]

        monitoring.finish_run("run_1")

        kwargs = update.call_args.kwargs
        self.assertEqual(update.call_args.args, ("run_1",))
        self.assertEqual(kwargs["run_status"], "completed")
        self.assertIsNotNone(kwargs["end_time"])
        self.assertEqual(
            (kwargs["total"], kwargs["healthy"], kwargs["degraded"], kwargs["failed"]),
            (4, 2, 1, 1),
        )

    @patch("util.monitoring.update_run")
    @patch("util.monitoring.get_results_for_run", return_value=[])
    def test_empty_run(self, get_results, update):
        monitoring.finish_run("run_1")
        self.assertEqual(update.call_args.kwargs["total"], 0)


class AlertActiveTest(unittest.TestCase):
    def test_first_failure_not_alerted_yet(self):
        self.assertFalse(monitoring.next_alert_active(result("failed"), False))

    def test_failure_alerted_now(self):
        self.assertTrue(
            monitoring.next_alert_active(result("failed", alert_sent=True), False)
        )

    def test_long_streak_stays_active(self):
        # Previous runs alerted; this failed result was not re-alerted
        self.assertTrue(monitoring.next_alert_active(result("failed"), True))

    def test_recovery_clears(self):
        self.assertFalse(monitoring.next_alert_active(result("healthy"), True))
        self.assertFalse(monitoring.next_alert_active(result("degraded"), True))

    def test_one_alert_across_100_failures(self):
        active, alerts = False, 0
        for _ in range(100):
            latest = result("failed")
            if not active:
                alerts += 1
                latest.alert_sent = True
            active = monitoring.next_alert_active(latest, active)
        self.assertEqual(alerts, 1)

    @patch("util.monitoring.get_dashboard_snapshot")
    def test_is_alert_active_reads_snapshot(self, get_snapshot):
        get_snapshot.return_value = SimpleNamespace(
            checks=[{"check_id": "datastore", "alert_active": True}]
        )
        self.assertTrue(monitoring.is_alert_active("datastore"))
        self.assertFalse(monitoring.is_alert_active("slack"))

    @patch("util.monitoring.get_dashboard_snapshot", return_value=None)
    def test_is_alert_active_no_snapshot(self, get_snapshot):
        self.assertFalse(monitoring.is_alert_active("datastore"))


class HourlyCountsTest(unittest.TestCase):
    def counts_from(self, results):
        counts = {}
        for r in results:
            counts = monitoring.add_to_hourly_counts(counts, r, NOW)
        return counts

    def test_degraded_counts_as_up(self):
        counts = self.counts_from(
            [result("healthy"), result("degraded"), result("failed"), result("failed")]
        )
        self.assertEqual(monitoring.window_rates(counts, NOW, 24), (0.5, 0.5))

    def test_no_results_is_none(self):
        self.assertEqual(monitoring.window_rates({}, NOW, 24), (None, None))

    def test_full_tier_ignored(self):
        counts = self.counts_from([result("failed", tier="full")])
        self.assertEqual(counts, {})

    def test_windows(self):
        counts = self.counts_from(
            [
                result("healthy", hours_ago=1),
                result("failed", hours_ago=2),
                result("failed", hours_ago=48),  # outside 24h, inside 7d
            ]
        )
        self.assertEqual(monitoring.window_rates(counts, NOW, 24)[0], 0.5)
        self.assertEqual(
            monitoring.window_rates(counts, NOW, 24 * 7)[0], round(1 / 3, 4)
        )

    def test_hours_older_than_7_days_dropped(self):
        counts = self.counts_from([result("failed", hours_ago=24 * 8)])
        counts = monitoring.add_to_hourly_counts(counts, result("healthy"), NOW)
        self.assertEqual(len(counts), 1)

    def test_does_not_mutate_input(self):
        before = self.counts_from([result("healthy")])
        frozen = {k: dict(v) for k, v in before.items()}
        monitoring.add_to_hourly_counts(before, result("failed"), NOW)
        self.assertEqual(before, frozen)

    def test_snapshot_entry(self):
        entry = monitoring.build_snapshot_entry(result("healthy"), None, NOW)
        self.assertEqual(entry["uptime_24h"], 1.0)
        self.assertFalse(entry["alert_active"])
        self.assertIsInstance(entry["last_checked_at"], str)


class UpdateSnapshotTest(unittest.TestCase):
    @patch("util.monitoring.modify_dashboard_snapshot")
    @patch("util.monitoring.get_results_for_run")
    @patch("util.monitoring.get_run")
    def test_keeps_checks_not_in_this_run(self, get_run, get_results, modify):
        get_run.return_value = SimpleNamespace(uid="run_2", end_time=NOW)
        get_results.return_value = [result("healthy")]

        monitoring.update_snapshot("run_2")

        build_checks = modify.call_args.args[0]
        self.assertEqual(modify.call_args.kwargs["last_run_id"], "run_2")
        checks = {
            c["check_id"]: c
            for c in build_checks(
                [
                    {"check_id": "datastore", "status": "failed", "alert_active": True},
                    {"check_id": "full_only_check", "status": "healthy"},
                ]
            )
        }
        self.assertEqual(checks["datastore"]["status"], "healthy")
        self.assertFalse(checks["datastore"]["alert_active"])
        self.assertEqual(checks["full_only_check"]["status"], "healthy")
        self.assertEqual(len(checks), 2)

    @patch("util.monitoring.modify_dashboard_snapshot")
    @patch("util.monitoring.get_run", return_value=None)
    def test_missing_run(self, get_run, modify):
        self.assertIsNone(monitoring.update_snapshot("nope"))
        modify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
