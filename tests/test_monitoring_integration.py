"""Emulator-backed monitoring validation, skipped during ordinary unit runs."""

from datetime import datetime, timedelta
import os
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from flask import Flask
from flask_login import LoginManager, UserMixin
from google.cloud import ndb

from db import monitoring as monitoring_db
from util.monitoring import runner
from util.monitoring.checks import CheckExecution, execute_check
from views import monitoring as monitoring_views


CHICAGO_TZ = ZoneInfo("America/Chicago")


class _Admin(UserMixin):
    id = "monitoring-live-test"
    email = "monitoring-live-test@illinimedia.com"
    groups = ["imc-staff-webdev"]


@unittest.skipUnless(
    os.environ.get("DATASTORE_EMULATOR_HOST"),
    "requires the local Datastore emulator",
)
class MonitoringIntegrationTest(unittest.TestCase):
    def setUp(self):
        self._clear_monitoring_data()

    def tearDown(self):
        self._clear_monitoring_data()

    def _clear_monitoring_data(self):
        with monitoring_db.client.context():
            keys = []
            for model in (
                monitoring_db.CheckResult,
                monitoring_db.Run,
                monitoring_db.DashboardSnapshot,
                monitoring_db.CronJobHeartbeat,
                monitoring_db.MonitoringLease,
            ):
                keys.extend(model.query().fetch(keys_only=True))
            if keys:
                ndb.delete_multi(keys)

    def _client(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SECRET_KEY="monitoring-live-test")
        app.register_blueprint(monitoring_views.monitoring_routes)
        login_manager = LoginManager(app)

        @login_manager.user_loader
        def load_user(_user_id):
            return _Admin()

        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = _Admin.id
            session["_fresh"] = True
        return client

    def test_live_full_run_snapshot_routes_and_overlap_protection(self):
        client = self._client()
        self.assertEqual(client.get("/health/monitoring").status_code, 503)

        def safe_execution(definition):
            if definition["kind"] == "function":
                return execute_check(definition, sleep=lambda _seconds: None)
            return CheckExecution(
                checked_at=datetime.now(CHICAGO_TZ),
                response_time_ms=10,
                attempts=1,
                status="healthy",
                http_status_code=definition["params"]["expected_status"],
            )

        with patch.object(runner, "execute_check", side_effect=safe_execution), patch(
            "util.monitoring.alerts._post_message", return_value=True
        ):
            summary = runner.run_monitoring("full", "manual")

        self.assertEqual(summary["run_status"], "completed")
        self.assertEqual(summary["total"], 9)
        self.assertEqual(summary["failed"], 0)
        results = monitoring_db.get_results_for_run(summary["run_id"])
        snapshot = monitoring_db.get_dashboard_snapshot()
        self.assertEqual(len(results), 9)
        self.assertEqual(len(snapshot.checks), 9)
        self.assertTrue(all(entry["uptime_24h"] == 100.0 for entry in snapshot.checks))
        self.assertEqual(client.get("/health/monitoring").status_code, 200)

        canonical = client.get("/api/monitoring/dashboard")
        compatibility = client.get("/monitoring/status")
        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(compatibility.status_code, 200)
        self.assertEqual(compatibility.headers["Deprecation"], "true")
        self.assertEqual(
            canonical.get_json()["snapshot"]["checks"],
            compatibility.get_json()["checks"],
        )

        self.assertTrue(monitoring_db.acquire_monitoring_lease("competing-run", 15))
        try:
            with self.assertRaises(runner.MonitoringRunInProgress):
                runner.run_monitoring("critical", "manual")
        finally:
            monitoring_db.release_monitoring_lease("competing-run")

        with monitoring_db.client.context():
            self.assertIsNone(
                monitoring_db.MonitoringLease.get_by_id(
                    monitoring_db.MONITORING_LEASE_ID
                )
            )

    def test_retention_removes_completed_and_abandoned_runs(self):
        expired_at = datetime.now(CHICAGO_TZ) - timedelta(days=31)
        with monitoring_db.client.context():
            completed = monitoring_db.Run(
                id="expired_completed",
                trigger="manual",
                tier="critical",
                run_status="completed",
                start_time=expired_at,
                end_time=expired_at,
            )
            abandoned = monitoring_db.Run(
                id="expired_abandoned",
                trigger="manual",
                tier="critical",
                run_status="running",
                start_time=expired_at,
            )
            completed.put()
            abandoned.put()
            monitoring_db.CheckResult(
                run=completed.key,
                check_id="datastore",
                checked_at=expired_at,
                status="healthy",
            ).put()

        deleted = monitoring_db.delete_old_monitoring_data(30)

        self.assertEqual(deleted, {"check_results": 1, "runs": 2})
        self.assertIsNone(monitoring_db.get_run("expired_completed"))
        self.assertIsNone(monitoring_db.get_run("expired_abandoned"))


if __name__ == "__main__":
    unittest.main()
