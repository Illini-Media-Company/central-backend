"""
This file holds the check functions that monitoring runs. Each one is added to
the registry with @register("<fn name>") and follows the contract described in
util/monitoring_registry.py.

The functions below are stubs so the check definitions validate. The real
implementations are owned by other teammates.

Created by Gus Nophaket on Oct. 5, 2026
Last modified Oct. 5, 2026
"""

from util.monitoring_registry import register


@register("check_datastore")
def check_datastore():
    """Checks that Datastore can be read."""
    # TODO: stub, implementation owned by the check-functions teammate
    raise NotImplementedError("check_datastore is not implemented yet")


@register("http_check")
def http_check(target, expected_status=200, has_field=None):
    """Checks that an internal route returns the expected status (and field)."""
    # TODO: stub, implementation owned by the check-functions teammate
    raise NotImplementedError("http_check is not implemented yet")
