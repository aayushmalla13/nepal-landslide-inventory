"""Analysis stage package, including the rainfall-threshold workflow.

The stage entry points are exposed lazily.

Importing them eagerly meant that ``from landslide_inventory.analysis.rainfall
import normalize_district`` -- a pure, standard-library-only helper -- pulled in
``figures``, then ``config``, then PyYAML. The data-acquisition scripts need
exactly that one function and are deliberately written against the standard
library, so on a machine without PyYAML installed they died on an import they
had no reason to make:

    ModuleNotFoundError: No module named 'yaml'

PEP 562 module-level ``__getattr__`` keeps ``from landslide_inventory.analysis
import run_rainfall_analysis_stage`` working exactly as before, while leaving
the leaf modules independently importable.
"""

from __future__ import annotations

from typing import Any

_LAZY_EXPORTS = {
    "run_rainfall_figures_stage": ".figures",
    "run_rainfall_analysis_stage": ".pipeline",
    "run_rainfall_release_stage": ".release",
}

__all__ = sorted(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value  # import once, then behave like an ordinary attribute
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
