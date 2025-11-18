from beartype.claw import beartype_this_package

# Enable beartype runtime type-checking for all modules in this package
beartype_this_package()

from dossier.dossier import (  # noqa: E402
    get_logger,
)

# Note: Dossier class is internal - use get_logger() instead

__all__ = [
    "get_logger",
]
