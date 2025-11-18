"""Test that all imports in the codebase are valid and can be resolved."""

import importlib
import pkgutil
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _import_submodules(package: str | ModuleType) -> dict[str, ModuleType]:
    """
    Import all submodules of a module, recursively, including subpackages.

    Useful for finding broken imports in a package in unit tests.

    https://stackoverflow.com/a/25562415/4212158
    """
    if isinstance(package, str):
        try:
            package = importlib.import_module(package)
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(f"Could not import package: {package}") from e
    results = {}
    # Use path parameter to ensure we only walk the package's own directory
    # This prevents pkgutil from finding similarly named test directories
    for _loader, name, is_pkg in pkgutil.walk_packages(
        path=package.__path__, prefix=package.__name__ + "."
    ):
        try:
            results[name] = importlib.import_module(name)
            if is_pkg:
                results.update(_import_submodules(name))  # recurse into subpackage
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(f"Could not import module: {name}") from e
    return results


def test_all_imports_are_valid():
    """Test that all modules in the dossier package can be imported.

    This test recursively imports all submodules in the package, which will
    catch any import errors at import time. This catches issues like:
    - Incorrect relative vs absolute imports
    - Typos in module names
    - Missing dependencies
    - Circular import issues at import time
    """
    project_root = Path(__file__).parent.parent

    # Add project root to sys.path to ensure imports work
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        modules = _import_submodules("dossier")
        # Ensure we imported something
        assert modules, "No modules were imported from dossier"
        print(f"Successfully imported {len(modules)} modules from dossier")
    except ModuleNotFoundError as e:
        pytest.fail(f"Import error: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error during import: {type(e).__name__}: {e}")


if __name__ == "__main__":
    # Allow running this test directly
    pytest.main([__file__, "-v"])
