import unittest
from unittest.mock import patch

from util import monitoring_checks
from util.monitoring_checks import InvalidCheckDefinition, validate_checks
from util.monitoring_registry import register

REGISTRY = {"check_datastore": lambda: {"ok": True}}


def definition(**overrides):
    base = {
        "id": "datastore",
        "name": "Datastore",
        "fn": "check_datastore",
        "params": {},
        "tier": "critical",
        "severity": "major",
        "timeout_ms": 3000,
        "latency_threshold_ms": 500,
        "enabled": True,
    }
    base.update(overrides)
    return base


class ValidateChecksTest(unittest.TestCase):
    def assert_invalid(self, checks, message):
        with self.assertRaises(InvalidCheckDefinition) as ctx:
            validate_checks(checks, registry=REGISTRY)
        self.assertIn(message, str(ctx.exception))

    def test_valid_definition_passes(self):
        validate_checks([definition()], registry=REGISTRY)

    def test_latency_threshold_is_optional(self):
        d = definition()
        del d["latency_threshold_ms"]
        validate_checks(
            [d, definition(id="other", latency_threshold_ms=None)], REGISTRY
        )

    def test_missing_key(self):
        d = definition()
        del d["severity"]
        self.assert_invalid([d], "missing 'severity'")

    def test_wrong_type(self):
        self.assert_invalid([definition(params=[])], "'params' must be dict")
        self.assert_invalid([definition(enabled="yes")], "'enabled' must be bool")

    def test_bad_tier(self):
        self.assert_invalid([definition(tier="hourly")], "'tier' must be one of")

    def test_bad_severity(self):
        self.assert_invalid(
            [definition(severity="critical")], "'severity' must be one of"
        )

    def test_timeout_must_be_positive_int(self):
        for bad in (0, -1, 2.5, True, "3000"):
            self.assert_invalid([definition(timeout_ms=bad)], "'timeout_ms' must be")

    def test_bad_latency_threshold(self):
        self.assert_invalid(
            [definition(latency_threshold_ms=0)], "'latency_threshold_ms' must be"
        )

    def test_duplicate_ids(self):
        self.assert_invalid([definition(), definition()], "duplicate 'id'")

    def test_unknown_fn(self):
        self.assert_invalid([definition(fn="check_missing")], "not in CHECK_REGISTRY")

    def test_empty_id(self):
        self.assert_invalid([definition(id=" ")], "'id' must not be empty")

    def test_unknown_field_catches_typos(self):
        self.assert_invalid([definition(latency_threshold=500)], "unknown fields")

    def test_not_a_dict(self):
        self.assert_invalid(["datastore"], "definition is not a dict")

    def test_reports_every_problem(self):
        with self.assertRaises(InvalidCheckDefinition) as ctx:
            validate_checks(
                [definition(tier="x"), definition(id="b", fn="nope")], REGISTRY
            )
        self.assertIn("check datastore: 'tier'", str(ctx.exception))
        self.assertIn("check b: 'fn'", str(ctx.exception))

    def test_real_checks_are_valid(self):
        # Also enforced at import, but keeps a failure readable here
        validate_checks(monitoring_checks.CHECKS)


class LoadChecksTest(unittest.TestCase):
    CHECKS = [
        definition(id="a", tier="critical"),
        definition(id="b", tier="full"),
        definition(id="c", tier="critical", enabled=False),
    ]

    @patch.object(monitoring_checks, "CHECKS", CHECKS)
    def test_returns_enabled_only(self):
        self.assertEqual([c["id"] for c in monitoring_checks.load_checks()], ["a", "b"])

    @patch.object(monitoring_checks, "CHECKS", CHECKS)
    def test_filters_by_tier(self):
        ids = [c["id"] for c in monitoring_checks.load_checks("critical")]
        self.assertEqual(ids, ["a"])

    @patch.object(monitoring_checks, "CHECKS", CHECKS)
    def test_returns_copies(self):
        monitoring_checks.load_checks()[0]["name"] = "changed"
        self.assertEqual(self.CHECKS[0]["name"], "Datastore")

    def test_bad_tier_argument(self):
        with self.assertRaises(ValueError):
            monitoring_checks.load_checks("hourly")


class RegistryTest(unittest.TestCase):
    def test_register_twice_with_different_functions_fails(self):
        @register("test_only_check")
        def first():
            return {"ok": True}

        with self.assertRaises(ValueError):

            @register("test_only_check")
            def second():
                return {"ok": True}


if __name__ == "__main__":
    unittest.main()
