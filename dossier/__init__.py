from beartype.claw import beartype_this_package

# Enable beartype runtime type-checking for all modules in this package
beartype_this_package()

from dossier.dossier import (  # noqa: E402
    close_logger,  # deprecated alias
    close_session,
    get_logger,  # deprecated alias
    get_session,
)

# Note: Dossier class is internal - use get_session() instead

__all__ = [
    "get_session",
    "close_session",
    # Backward compatibility
    "get_logger",
    "close_logger",
]
