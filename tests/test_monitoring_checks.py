import unittest
from unittest.mock import Mock, patch

import requests

from util.monitoring.checks import execute_check
from util.monitoring.definitions import (
    get_check_target,
    get_check_definitions,
    get_checks_for_tier,
    validate_check_definitions,
    resolve_http_target,
)


def definition(**overrides):
    value = {
        "id": "test",
        "name": "Test",
        "kind": "http",
        "tier": "critical",
        "severity": "major",
        "timeout_ms": 1000,
        "latency_threshold_ms": 500,
        "enabled": True,
        "params": {
            "target": "/health/live",
            "expected_status": 200,
            "expected_json_type": "dict",
            "expected_values": {"status": "ok"},
        },
    }
    value.update(overrides)
    return value


class FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=None, text=""):
        self.status_code = status_code
        self.payload = {"status": "ok"} if payload is None else payload
        self.json_error = json_error
        self.text = text

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class MonitoringDefinitionTest(unittest.TestCase):
    def test_registry_has_unique_ids_and_full_contains_critical(self):
        checks = get_check_definitions()
        self.assertEqual(len(checks), len({check["id"] for check in checks}))
        self.assertEqual(len(get_checks_for_tier("critical")), 3)
        self.assertEqual(len(get_checks_for_tier("full")), 9)
        self.assertNotIn(
            "backend_liveness", {check["id"] for check in get_check_definitions()}
        )

    def test_registry_rejects_duplicates_and_unsafe_methods(self):
        first = definition()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_check_definitions([first, first.copy()])
        unsafe = definition(
            params={"target": "/x", "method": "POST", "expected_status": 200}
        )
        with self.assertRaisesRegex(ValueError, "Only GET"):
            validate_check_definitions([unsafe])

    def test_registry_rejects_invalid_definition_and_executor_fields(self):
        invalid_definitions = [
            ("not a mapping", "must be dictionaries"),
            (definition(unknown=True), "unknown fields"),
            (definition(name=" "), "name must be"),
            (definition(timeout_ms=0), "timeout_ms must be"),
            (definition(params=[]), "params must be"),
            (
                definition(
                    params={
                        "target": "/health/live",
                        "method": 1,
                        "expected_status": 200,
                    }
                ),
                "Only GET",
            ),
            (
                definition(params={"target": "/health/live", "expected_status": True}),
                "Invalid expected_status",
            ),
            (
                definition(
                    params={
                        "target": "/health/live",
                        "expected_status": 200,
                        "required_fields": "status",
                    }
                ),
                "required_fields",
            ),
            (
                definition(
                    params={
                        "target": "/health/live",
                        "expected_status": 200,
                        "expected_values": [],
                    }
                ),
                "expected_values",
            ),
            (
                definition(
                    params={
                        "target": "/health/live",
                        "expected_status": 200,
                        "min_items": -1,
                    }
                ),
                "min_items",
            ),
        ]
        for invalid, message in invalid_definitions:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate_check_definitions([invalid])

    def test_relative_targets_use_the_monitoring_base_url(self):
        self.assertEqual(
            resolve_http_target("/health/live"), "https://127.0.0.1:5001/health/live"
        )

    def test_cron_definitions_require_thresholds_and_expose_job_target(self):
        cron = definition(
            kind="function",
            params={"handler": "cron_heartbeat", "job_id": "job"},
        )
        with self.assertRaisesRegex(ValueError, "is missing"):
            validate_check_definitions([cron])

        invalid_name = definition(
            kind="function",
            params={
                "handler": "cron_heartbeat",
                "job_id": "job",
                "job_name": "",
                "max_success_age_minutes": 60,
                "max_runtime_minutes": 10,
            },
        )
        with self.assertRaisesRegex(ValueError, "job_name must be"):
            validate_check_definitions([invalid_name])

        registered = next(
            check
            for check in get_check_definitions()
            if check["id"] == "cron_socials_rss_listener"
        )
        self.assertEqual(get_check_target(registered), "socials_rss_listener")


class MonitoringCheckExecutionTest(unittest.TestCase):
    def _clock(self, *values):
        return Mock(side_effect=values)

    def test_healthy_http_check(self):
        getter = Mock(return_value=FakeResponse())
        result = execute_check(
            definition(),
            request_get=getter,
            sleep=Mock(),
            monotonic=self._clock(0, 0.1),
        )
        self.assertEqual(result.status, "healthy")
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.http_status_code, 200)
        getter.assert_called_once()
        self.assertFalse(getter.call_args.kwargs["verify"])

    def test_slow_or_retry_success_is_degraded(self):
        slow = execute_check(
            definition(latency_threshold_ms=10),
            request_get=Mock(return_value=FakeResponse()),
            sleep=Mock(),
            monotonic=self._clock(0, 0.1),
        )
        retry_get = Mock(side_effect=[requests.Timeout("late"), FakeResponse()])
        sleep = Mock()
        retried = execute_check(
            definition(),
            request_get=retry_get,
            sleep=sleep,
            monotonic=self._clock(0, 0.2),
        )
        self.assertEqual(slow.status, "degraded")
        self.assertEqual(retried.status, "degraded")
        self.assertEqual(retried.attempts, 2)
        sleep.assert_called_once_with(0.5)

    def test_status_json_and_required_field_failures_are_normalized(self):
        cases = [
            (FakeResponse(status_code=503), "bad_status"),
            (FakeResponse(json_error=ValueError("bad json")), "invalid_response"),
            (FakeResponse(payload={}), "invalid_response"),
        ]
        for response, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                result = execute_check(
                    definition(),
                    request_get=Mock(return_value=response),
                    sleep=Mock(),
                    monotonic=self._clock(0, 0.1),
                )
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.attempts, 2)
                self.assertEqual(result.error_type, expected_error)

    def test_timeout_and_connection_failures_are_normalized(self):
        for error, expected_type in [
            (requests.Timeout("late"), "timeout"),
            (requests.ConnectionError("offline"), "connection_error"),
        ]:
            with self.subTest(expected_type=expected_type):
                result = execute_check(
                    definition(),
                    request_get=Mock(side_effect=error),
                    sleep=Mock(),
                    monotonic=self._clock(0, 0.1),
                )
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.error_type, expected_type)

    def test_auth_response_body_and_validation_errors_are_recorded(self):
        auth = execute_check(
            definition(),
            request_get=Mock(
                return_value=FakeResponse(status_code=403, text="access denied")
            ),
            sleep=Mock(),
            monotonic=self._clock(0, 0.1),
        )
        mismatch = execute_check(
            definition(),
            request_get=Mock(return_value=FakeResponse(payload={"status": "wrong"})),
            sleep=Mock(),
            monotonic=self._clock(0, 0.1),
        )
        empty_list = execute_check(
            definition(
                params={
                    "target": "https://example.test/items",
                    "expected_status": 200,
                    "expected_json_type": "list",
                    "min_items": 1,
                }
            ),
            request_get=Mock(return_value=FakeResponse(payload=[])),
            sleep=Mock(),
            monotonic=self._clock(0, 0.1),
        )
        self.assertEqual(auth.error_type, "auth_failed")
        self.assertIn("access denied", auth.error_message)
        self.assertEqual(mismatch.error_type, "invalid_response")
        self.assertEqual(empty_list.error_type, "invalid_response")

    def test_unexpected_errors_are_isolated_and_external_tls_is_verified(self):
        getter = Mock(side_effect=RuntimeError("unexpected"))
        result = execute_check(
            definition(
                params={
                    "target": "https://example.test/health",
                    "expected_status": 200,
                }
            ),
            request_get=getter,
            sleep=Mock(),
            monotonic=self._clock(0, 0.1),
        )
        self.assertEqual(result.error_type, "unexpected_error")
        self.assertTrue(getter.call_args.kwargs["verify"])

    @patch("util.monitoring.checks.check_datastore_connection", return_value=True)
    def test_function_check(self, datastore_check):
        function_definition = definition(
            kind="function", params={"handler": "datastore"}
        )
        result = execute_check(
            function_definition, sleep=Mock(), monotonic=self._clock(0, 0.1)
        )
        self.assertEqual(result.status, "healthy")
        datastore_check.assert_called_once_with(timeout_seconds=1.0)

    @patch("util.monitoring.checks.evaluate_cron_job")
    def test_cron_heartbeat_function_check_preserves_degraded_details(self, evaluate):
        evaluate.return_value = type(
            "Health",
            (),
            {
                "status": "degraded",
                "error_type": "not_configured",
                "error_message": "not observed",
            },
        )()
        cron_definition = definition(
            kind="function",
            params={
                "handler": "cron_heartbeat",
                "job_id": "job",
                "job_name": "Job",
                "max_success_age_minutes": 60,
                "max_runtime_minutes": 10,
            },
        )
        result = execute_check(
            cron_definition, sleep=Mock(), monotonic=self._clock(0, 0.1)
        )
        self.assertEqual(result.status, "degraded")
        self.assertEqual(result.error_type, "not_configured")
        self.assertEqual(result.error_message, "not observed")


if __name__ == "__main__":
    unittest.main()
