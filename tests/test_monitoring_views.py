import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from flask import Flask
from flask_login import LoginManager, UserMixin

from views import monitoring

NOW = datetime(2026, 10, 5, 14, 0, tzinfo=ZoneInfo("America/Chicago"))


class FakeUser(UserMixin):
    def __init__(self, groups):
        self.id = "1"
        self.email = "tester@illinimedia.com"
        self.groups = groups


def fake_run():
    return SimpleNamespace(
        uid="run_20261005_140000_critical",
        trigger="scheduled",
        tier="critical",
        run_status="completed",
        start_time=NOW,
        end_time=NOW,
        total=1,
        healthy=1,
        degraded=0,
        failed=0,
    )


def fake_result():
    return SimpleNamespace(
        uid=1,
        run=SimpleNamespace(id=lambda: "run_20261005_140000_critical"),
        check_id="datastore",
        check_name="Datastore",
        target=None,
        tier="critical",
        checked_at=NOW,
        response_time_ms=120,
        latency_threshold_ms=500,
        attempts=1,
        status="healthy",
        http_status_code=None,
        error_type=None,
        error_message=None,
        severity="major",
        alert_sent=False,
    )


class MonitoringViewsTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SECRET_KEY="test")
        login_manager = LoginManager()
        login_manager.init_app(app)
        self.user = None
        login_manager.request_loader(lambda request: self.user)
        app.register_blueprint(monitoring.monitoring_routes)
        self.client = app.test_client()
        monitoring._history_cache.clear()

    def login(self, groups=("imc-staff-webdev",)):
        self.user = FakeUser(list(groups))

    # Auth

    def test_requires_login(self):
        self.assertEqual(self.client.get("/monitoring/status").status_code, 401)

    def test_requires_group(self):
        self.login(groups=["editors"])
        self.assertEqual(self.client.get("/monitoring/status").status_code, 403)

    @patch("views.monitoring.get_dashboard_snapshot", return_value=None)
    def test_compatibility_routes_use_tools_admin_groups_and_are_deprecated(self, _):
        self.login(groups=["ceo"])
        response = self.client.get("/monitoring/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Deprecation"], "true")
        self.assertIn("/api/monitoring/dashboard", response.headers["Link"])

    # /status

    @patch("views.monitoring.get_dashboard_snapshot", return_value=None)
    def test_status_before_any_run(self, _):
        self.login()
        response = self.client.get("/monitoring/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "updated_at": None,
                "last_run_id": None,
                "last_run_finished_at": None,
                "checks": [],
            },
        )

    @patch("views.monitoring.get_dashboard_snapshot")
    def test_status_hides_hourly_counts(self, get_snapshot):
        self.login()
        get_snapshot.return_value = SimpleNamespace(
            updated_at=NOW,
            last_run_id="run_x",
            last_run_finished_at=NOW,
            checks=[
                {
                    "check_id": "datastore",
                    "status": "healthy",
                    "uptime_24h": 50.0,
                    "uptime_7d": 75.0,
                    "error_rate_24h": 50.0,
                    "hourly_counts": {},
                }
            ],
        )
        body = self.client.get("/monitoring/status").get_json()
        self.assertEqual(body["last_run_id"], "run_x")
        self.assertEqual(body["updated_at"], NOW.isoformat())
        self.assertEqual(
            body["checks"],
            [
                {
                    "check_id": "datastore",
                    "status": "healthy",
                    "uptime_24h": 50.0,
                    "uptime_7d": 75.0,
                    "error_rate_24h": 50.0,
                }
            ],
        )

    # /runs

    @patch("views.monitoring.get_recent_runs")
    def test_list_runs(self, get_runs):
        self.login()
        get_runs.return_value = [fake_run()]
        body = self.client.get("/monitoring/runs?limit=5").get_json()
        get_runs.assert_called_once_with(5)
        self.assertEqual(body["runs"][0]["run_id"], "run_20261005_140000_critical")
        self.assertEqual(body["runs"][0]["start_time"], NOW.isoformat())

    @patch("views.monitoring.get_recent_runs", return_value=[])
    def test_list_runs_default_limit(self, get_runs):
        self.login()
        self.client.get("/monitoring/runs")
        get_runs.assert_called_once_with(20)

    def test_list_runs_bad_limit(self):
        self.login()
        for bad in ("abc", "0", "101"):
            response = self.client.get(f"/monitoring/runs?limit={bad}")
            self.assertEqual(response.status_code, 400, bad)

    # /runs/<id>

    @patch("views.monitoring.get_results_for_run")
    @patch("views.monitoring.get_run")
    def test_run_detail(self, get_run, get_results):
        self.login()
        get_run.return_value = fake_run()
        get_results.return_value = [fake_result()]
        body = self.client.get("/monitoring/runs/run_x").get_json()
        self.assertEqual(body["run"]["total"], 1)
        result = body["results"][0]
        self.assertEqual(result["run_id"], "run_20261005_140000_critical")
        self.assertEqual(result["checked_at"], NOW.isoformat())
        self.assertIsNone(result["error_type"])

    @patch("views.monitoring.get_run", return_value=None)
    def test_run_detail_not_found(self, _):
        self.login()
        self.assertEqual(self.client.get("/monitoring/runs/nope").status_code, 404)

    # /checks/<id>/history

    @patch("views.monitoring.get_results_for_check_since")
    def test_history(self, get_since):
        self.login()
        get_since.return_value = [fake_result()]
        body = self.client.get("/monitoring/checks/datastore/history?days=3").get_json()
        self.assertEqual(body["check_id"], "datastore")
        self.assertEqual(body["days"], 3)
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(get_since.call_args.args[0], "datastore")

    @patch("views.monitoring.get_results_for_check_since", return_value=[])
    def test_history_is_cached(self, get_since):
        self.login()
        self.client.get("/monitoring/checks/datastore/history")
        self.client.get("/monitoring/checks/datastore/history")
        get_since.assert_called_once()

    @patch("views.monitoring.get_results_for_check_since", return_value=[])
    def test_history_cache_expires(self, get_since):
        self.login()
        with patch("views.monitoring.time.monotonic", return_value=1000):
            self.client.get("/monitoring/checks/datastore/history")
        with patch("views.monitoring.time.monotonic", return_value=1000 + 301):
            self.client.get("/monitoring/checks/datastore/history")
        self.assertEqual(get_since.call_count, 2)

    def test_history_bad_days(self):
        self.login()
        for bad in ("0", "31", "x"):
            response = self.client.get(
                f"/monitoring/checks/datastore/history?days={bad}"
            )
            self.assertEqual(response.status_code, 400, bad)

    def test_history_rejects_unknown_check(self):
        self.login()
        response = self.client.get("/monitoring/checks/not-registered/history")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
