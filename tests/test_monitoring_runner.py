import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from util.monitoring import alerts, runner
from util.monitoring.checks import CheckExecution


NOW = datetime(2026, 10, 4, 12, 0, tzinfo=ZoneInfo("America/Chicago"))


class FakeKey:
    def __init__(self, value):
        self.value = value

    def id(self):
        return self.value


def check_definition(check_id="one", tier="critical", severity="major"):
    return {
        "id": check_id,
        "name": check_id.title(),
        "kind": "http",
        "tier": tier,
        "severity": severity,
        "timeout_ms": 1000,
        "latency_threshold_ms": 500,
        "enabled": True,
        "params": {"target": f"/{check_id}", "expected_status": 200},
    }


def execution(status="healthy", error_type=None):
    return CheckExecution(
        checked_at=NOW,
        response_time_ms=20,
        attempts=2 if status == "failed" else 1,
        status=status,
        error_type=error_type,
        error_message=error_type,
    )


class MonitoringAlertTest(unittest.TestCase):
    @patch.object(alerts, "_post_message", return_value=True)
    def test_initial_failure_and_recovery_alert_once(self, post):
        definition = check_definition()
        failed = SimpleNamespace(**execution("failed", "timeout").__dict__)
        healthy = SimpleNamespace(**execution().__dict__)
        self.assertTrue(alerts.send_alert_transition(definition, failed, False))
        self.assertFalse(alerts.send_alert_transition(definition, failed, True))
        self.assertTrue(alerts.send_alert_transition(definition, healthy, True))
        self.assertEqual(post.call_count, 2)

    @patch.object(alerts, "_post_message", return_value=True)
    def test_minor_failures_do_not_alert(self, post):
        self.assertFalse(
            alerts.send_alert_transition(
                check_definition(severity="minor"),
                SimpleNamespace(**execution("failed", "timeout").__dict__),
                False,
            )
        )
        post.assert_not_called()

    @patch.object(alerts, "_post_message", return_value=False)
    def test_failed_delivery_can_be_retried_next_run(self, post):
        result = SimpleNamespace(**execution("failed", "timeout").__dict__)
        self.assertFalse(
            alerts.send_alert_transition(check_definition(), result, False)
        )
        post.assert_called_once()


class MonitoringRunnerTest(unittest.TestCase):
    @patch.object(runner, "release_monitoring_lease")
    @patch.object(runner, "acquire_monitoring_lease", return_value=True)
    @patch.object(runner, "delete_old_monitoring_data")
    @patch.object(runner, "update_snapshot")
    @patch.object(runner, "update_run")
    @patch.object(runner, "send_alert_transition", return_value=False)
    @patch.object(runner, "has_active_alert_for_check", return_value=False)
    @patch.object(runner, "execute_check")
    @patch.object(runner, "create_check_result")
    @patch.object(runner, "get_checks_for_tier")
    @patch.object(runner, "create_run")
    def test_run_isolates_checks_finalizes_counts_and_cleans_full_runs(
        self,
        create_run,
        get_checks,
        create_result,
        execute,
        _active_alert,
        _alert,
        update_run,
        update_snapshot,
        cleanup,
        acquire_lease,
        release_lease,
    ):
        create_run.return_value = SimpleNamespace(key=FakeKey("run_1"), start_time=NOW)
        get_checks.return_value = [check_definition("one"), check_definition("two")]
        execute.side_effect = [execution("healthy"), RuntimeError("boom")]

        def stored_result(**kwargs):
            return SimpleNamespace(
                key=FakeKey(len(create_result.mock_calls)), alert_sent=False, **kwargs
            )

        create_result.side_effect = stored_result

        summary = runner.run_monitoring("full", "manual")

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["healthy"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(create_result.call_count, 2)
        update_run.assert_called_once()
        update_snapshot.assert_called_once()
        cleanup.assert_called_once_with(30)
        acquire_lease.assert_called_once()
        release_lease.assert_called_once()

    def test_persistence_failure_does_not_stop_later_checks(self):
        stored = SimpleNamespace(
            key=FakeKey(2),
            status="healthy",
            alert_sent=False,
        )
        run_entity = SimpleNamespace(key=FakeKey("run_2"), start_time=NOW)
        with patch.object(
            runner, "acquire_monitoring_lease", return_value=True
        ), patch.object(runner, "release_monitoring_lease"), patch.object(
            runner, "create_run", return_value=run_entity
        ), patch.object(
            runner,
            "get_checks_for_tier",
            return_value=[check_definition("one"), check_definition("two")],
        ), patch.object(
            runner, "has_active_alert_for_check", return_value=False
        ), patch.object(
            runner, "execute_check", return_value=execution("healthy")
        ) as execute, patch.object(
            runner,
            "create_check_result",
            side_effect=[RuntimeError("write failed"), stored],
        ), patch.object(
            runner, "send_alert_transition", return_value=False
        ), patch.object(
            runner, "update_run"
        ), patch.object(
            runner, "update_snapshot"
        ), patch.object(
            runner, "delete_old_monitoring_data"
        ):
            summary = runner.run_monitoring("critical", "manual")

        self.assertEqual(execute.call_count, 2)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["healthy"], 1)

    def test_alert_bookkeeping_failure_does_not_stop_later_checks(self):
        run_entity = SimpleNamespace(key=FakeKey("run_3"), start_time=NOW)

        def stored_result(**kwargs):
            return SimpleNamespace(
                key=FakeKey(kwargs["check_id"]), alert_sent=False, **kwargs
            )

        with patch.object(
            runner, "acquire_monitoring_lease", return_value=True
        ), patch.object(runner, "release_monitoring_lease"), patch.object(
            runner, "create_run", return_value=run_entity
        ), patch.object(
            runner,
            "get_checks_for_tier",
            return_value=[check_definition("one"), check_definition("two")],
        ), patch.object(
            runner, "has_active_alert_for_check", return_value=False
        ), patch.object(
            runner, "execute_check", return_value=execution("healthy")
        ) as execute, patch.object(
            runner, "create_check_result", side_effect=stored_result
        ), patch.object(
            runner, "send_alert_transition", return_value=True
        ), patch.object(
            runner, "update_check_result", side_effect=RuntimeError("write failed")
        ), patch.object(
            runner, "update_run"
        ), patch.object(
            runner, "update_snapshot"
        ), patch.object(
            runner, "delete_old_monitoring_data"
        ):
            summary = runner.run_monitoring("critical", "manual")

        self.assertEqual(execute.call_count, 2)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["healthy"], 2)

    def test_invalid_tier_and_trigger_are_rejected(self):
        with self.assertRaises(ValueError):
            runner.run_monitoring("unknown", "manual")
        with self.assertRaises(ValueError):
            runner.run_monitoring("critical", "unknown")

    def test_overlapping_run_is_rejected_without_creating_a_run(self):
        with patch.object(
            runner, "acquire_monitoring_lease", return_value=False
        ), patch.object(runner, "create_run") as create_run, patch.object(
            runner, "release_monitoring_lease"
        ) as release:
            with self.assertRaises(runner.MonitoringRunInProgress):
                runner.run_monitoring("critical", "manual")
        create_run.assert_not_called()
        release.assert_not_called()

    def test_lease_is_released_when_run_creation_fails(self):
        with patch.object(
            runner, "acquire_monitoring_lease", return_value=True
        ), patch.object(
            runner, "create_run", side_effect=RuntimeError("datastore down")
        ), patch.object(
            runner, "release_monitoring_lease"
        ) as release:
            with self.assertRaisesRegex(RuntimeError, "datastore down"):
                runner.run_monitoring("critical", "manual")
        release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
