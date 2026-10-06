"""Compatibility imports for the original monitoring registry module.

The active runner uses :mod:`util.monitoring`. This module intentionally
aliases that package's compatibility registry so there is only one mutable
registry object in the application.
"""

from util.monitoring.checks import (
    COMPATIBILITY_CHECK_REGISTRY as CHECK_REGISTRY,
    register_compatibility_check as register,
)


__all__ = ["CHECK_REGISTRY", "register"]
