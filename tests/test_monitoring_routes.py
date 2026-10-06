import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from flask import Flask
from flask_login import LoginManager, UserMixin

from views import monitoring


NOW = datetime(2026, 10, 4, 12, 0, tzinfo=ZoneInfo("America/Chicago"))


class User(UserMixin):
    def __init__(self, groups):
        self.id = "admin@illinimedia.com"
        self.email = self.id
        self.groups = groups


class MonitoringRoutesTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SECRET_KEY="test")
        app.register_blueprint(monitoring.monitoring_routes)
        login_manager = LoginManager(app)
        self.user = User(["imc-staff-webdev"])

        @login_manager.user_loader
        def load_user(_user_id):
            return self.user

        self.client = app.test_client()

    def login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = self.user.id
            session["_fresh"] = True

    def test_liveness_and_readiness(self):
        self.assertEqual(self.client.get("/health/live").get_json(), {"status": "ok"})
        with patch.object(monitoring, "check_datastore_connection"):
            response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ready")
        with patch.object(
            monitoring, "check_datastore_connection", side_effect=RuntimeError("down")
        ):
            response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("down", response.get_data(as_text=True))

    def test_monitoring_health_reports_fresh_stale_stuck_and_storage_failure(self):
        fresh = SimpleNamespace(last_run_finished_at=NOW)
        with patch.object(
            monitoring, "get_dashboard_snapshot", return_value=fresh
        ), patch.object(monitoring, "get_stuck_runs", return_value=[]), patch.object(
            monitoring, "datetime"
        ) as clock:
            clock.now.return_value = NOW
            self.assertEqual(self.client.get("/health/monitoring").status_code, 200)

            fresh.last_run_finished_at = NOW - timedelta(hours=14)
            self.assertEqual(self.client.get("/health/monitoring").status_code, 503)

            fresh.last_run_finished_at = NOW
            monitoring.get_stuck_runs.return_value = [object()]
            self.assertEqual(self.client.get("/health/monitoring").status_code, 503)

        with patch.object(
            monitoring,
            "get_dashboard_snapshot",
            side_effect=RuntimeError("datastore down"),
        ):
            response = self.client.get("/health/monitoring")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {"status": "not_ready"})

    @patch.object(monitoring, "run_monitoring", return_value={"run_id": "run_1"})
    def test_cron_requires_header_and_selects_trigger(self, run):
        denied = self.client.get("/cron/backend-monitoring/critical")
        self.assertEqual(denied.status_code, 403)
        allowed = self.client.get(
            "/cron/backend-monitoring/critical",
            headers={"X-Appengine-Cron": "true"},
        )
        self.assertEqual(allowed.status_code, 200)
        run.assert_called_once_with(tier="critical", trigger="pre_peak")

    def test_monitoring_apis_require_login_and_group(self):
        self.assertEqual(self.client.get("/api/monitoring/runs").status_code, 401)
        self.user.groups = ["unrelated"]
        self.login()
        self.assertEqual(self.client.get("/api/monitoring/runs").status_code, 403)

    @patch.object(monitoring, "run_monitoring", return_value={"run_id": "manual"})
    def test_manual_run_validates_tier(self, run):
        self.login()
        invalid = self.client.post("/api/monitoring/runs", json={"tier": "other"})
        invalid_shape = self.client.post("/api/monitoring/runs", json=["full"])
        valid = self.client.post("/api/monitoring/runs", json={"tier": "full"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid_shape.status_code, 400)
        self.assertEqual(
            invalid_shape.get_json()["error"], "request body must be a JSON object"
        )
        self.assertEqual(valid.status_code, 200)
        run.assert_called_once_with(tier="full", trigger="manual")

    @patch.object(
        monitoring,
        "run_monitoring",
        side_effect=monitoring.MonitoringRunInProgress("already running"),
    )
    def test_manual_and_cron_runs_report_overlap_as_conflict(self, _run):
        self.login()
        manual = self.client.post("/api/monitoring/runs", json={"tier": "full"})
        cron = self.client.get(
            "/cron/backend-monitoring/critical",
            headers={"X-Appengine-Cron": "true"},
        )
        self.assertEqual(manual.status_code, 409)
        self.assertEqual(cron.status_code, 409)
        self.assertNotIn("traceback", manual.get_data(as_text=True).lower())

    @patch.object(monitoring, "get_recent_runs", return_value=[])
    def test_run_history_bounds_limit(self, recent_runs):
        self.login()
        self.assertEqual(
            self.client.get("/api/monitoring/runs?limit=101").status_code, 400
        )
        self.assertEqual(
            self.client.get("/api/monitoring/runs?limit=10").status_code, 200
        )
        recent_runs.assert_called_once_with(10)

    @patch.object(monitoring, "get_results_for_run", return_value=[])
    @patch.object(monitoring, "get_run")
    def test_run_detail_and_missing_run(self, get_run, _results):
        self.login()
        get_run.return_value = None
        self.assertEqual(
            self.client.get("/api/monitoring/runs/missing").status_code, 404
        )
        get_run.return_value = SimpleNamespace(
            key=SimpleNamespace(id=lambda: "run_1"),
            trigger="manual",
            tier="full",
            run_status="completed",
            start_time=NOW,
            end_time=NOW,
            total=0,
            healthy=0,
            degraded=0,
            failed=0,
        )
        self.assertEqual(self.client.get("/api/monitoring/runs/run_1").status_code, 200)

    def test_unknown_check_returns_404(self):
        self.login()
        self.assertEqual(
            self.client.get("/api/monitoring/checks/unknown").status_code, 404
        )

    @patch.object(monitoring, "get_results_for_check", return_value=[])
    def test_known_check_history_is_serializable(self, get_results):
        self.login()
        response = self.client.get("/api/monitoring/checks/datastore?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["check"]["id"], "datastore")
        get_results.assert_called_once_with("datastore", 5)

    @patch.object(monitoring, "get_stuck_runs")
    @patch.object(monitoring, "get_cron_job_heartbeats")
    @patch.object(monitoring, "get_run")
    @patch.object(monitoring, "get_dashboard_snapshot")
    def test_dashboard_serializes_snapshot_and_stuck_runs(
        self, get_snapshot, get_run, get_heartbeats, get_stuck
    ):
        self.login()
        completed = SimpleNamespace(
            key=SimpleNamespace(id=lambda: "run_1"),
            trigger="scheduled",
            tier="full",
            run_status="completed",
            start_time=NOW,
            end_time=NOW,
            total=9,
            healthy=9,
            degraded=0,
            failed=0,
        )
        stuck = SimpleNamespace(
            key=SimpleNamespace(id=lambda: "run_stuck"),
            trigger="scheduled",
            tier="critical",
            run_status="running",
            start_time=NOW,
            end_time=None,
            total=0,
            healthy=0,
            degraded=0,
            failed=0,
        )
        get_snapshot.return_value = SimpleNamespace(
            updated_at=NOW,
            last_run_id="run_1",
            last_run_finished_at=NOW,
            checks=[
                {
                    "check_id": "datastore",
                    "status": "healthy",
                    "uptime_24h": 100.0,
                    "hourly_counts": {"internal": {"up": 1}},
                }
            ],
        )
        get_run.return_value = completed
        get_stuck.return_value = [stuck]
        get_heartbeats.return_value = [
            SimpleNamespace(
                key=SimpleNamespace(id=lambda: "socials_rss_listener"),
                display_name="Socials RSS listener",
                tracking_started_at=NOW - timedelta(hours=2),
                last_started_at=NOW - timedelta(minutes=30),
                last_completed_at=NOW - timedelta(minutes=29),
                last_succeeded_at=NOW - timedelta(minutes=29),
                last_status="succeeded",
                last_duration_ms=100,
                last_http_status=200,
                last_error=None,
            )
        ]

        with patch.object(monitoring, "datetime") as clock:
            clock.now.return_value = NOW
            response = self.client.get("/api/monitoring/dashboard")
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["last_run"]["run_id"], "run_1")
        self.assertEqual(payload["stuck_runs"][0]["run_id"], "run_stuck")
        self.assertEqual(payload["cron_jobs"][0]["last_status"], "succeeded")
        self.assertFalse(payload["cron_jobs"][0]["overdue"])
        self.assertEqual(payload["snapshot"]["checks"][0]["uptime_24h"], 100.0)
        self.assertNotIn("hourly_counts", payload["snapshot"]["checks"][0])


if __name__ == "__main__":
    unittest.main()
