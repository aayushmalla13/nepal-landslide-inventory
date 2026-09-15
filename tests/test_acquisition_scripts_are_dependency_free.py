"""The data-acquisition scripts must run with only the standard library.

Both downloaders are deliberately written against the standard library so they
can be run on any machine with a plain Python -- typically the author's laptop,
on a network the analysis environment cannot reach.

That property was quietly broken. Both scripts need one pure helper,
``analysis.rainfall.normalize_district``, but importing it ran
``landslide_inventory.analysis.__init__``, which eagerly imported ``figures`` ->
``config`` -> PyYAML. On a Mac using the system Python the IMERG script died
with ``ModuleNotFoundError: No module named 'yaml'`` before it did anything --
on an import it had no reason to make.

These tests import the leaf modules with PyYAML made unimportable, which is what
that laptop looked like.
"""

from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

LEAF_MODULES = [
    "landslide_inventory.analysis.rainfall",
    "landslide_inventory.gazetteer",
    "landslide_inventory.gazetteer_municipality",
    "landslide_inventory.nlp_counts",
    "landslide_inventory.nlp_attribution",
]


@pytest.fixture()
def without_pyyaml(monkeypatch):
    """Make `import yaml` fail, and drop anything already importing it."""

    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yaml" or name.startswith("yaml."):
            raise ModuleNotFoundError("No module named 'yaml'")
        return real_import(name, globals, locals, fromlist, level)

    for name in list(sys.modules):
        if name == "yaml" or name.startswith("yaml.") or name.startswith("landslide_inventory"):
            monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(builtins, "__import__", guarded)
    yield
    for name in list(sys.modules):
        if name.startswith("landslide_inventory"):
            sys.modules.pop(name, None)


@pytest.mark.parametrize("module_name", LEAF_MODULES)
def test_leaf_modules_import_without_pyyaml(without_pyyaml, module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module is not None


def test_normalize_district_is_reachable_without_pyyaml(without_pyyaml) -> None:
    """This is the exact import both downloaders make."""

    from landslide_inventory.analysis.rainfall import normalize_district

    assert normalize_district("rukum_west") == "Western Rukum"
    assert normalize_district("KASKI") == "Kaski"


def test_the_analysis_package_still_exposes_its_stage_entry_points() -> None:
    """Making the imports lazy must not change the package's public surface."""

    import landslide_inventory.analysis as analysis

    for name in (
        "run_rainfall_analysis_stage",
        "run_rainfall_figures_stage",
        "run_rainfall_release_stage",
    ):
        assert name in analysis.__all__
        assert name in dir(analysis)
        assert callable(getattr(analysis, name))


def test_an_unknown_attribute_still_raises_attribute_error() -> None:
    import landslide_inventory.analysis as analysis

    with pytest.raises(AttributeError):
        analysis.no_such_stage


@pytest.mark.parametrize(
    "script_name",
    ["download_chirps_climateserv.py", "download_imerg_gesdisc.py"],
)
def test_the_downloaders_only_import_the_standard_library_at_module_level(
    script_name: str,
) -> None:
    """A third-party import at module level would break the laptop use case."""

    import ast

    source = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")
    tree = ast.parse(source)
    third_party = {"yaml", "numpy", "pandas", "h5py", "netCDF4", "requests", "shapely"}
    offenders: list[str] = []
    for node in tree.body:  # module level only; function-level imports are fine
        if isinstance(node, ast.Import):
            offenders += [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            offenders.append(node.module.split(".")[0])
    assert not (set(offenders) & third_party), f"{script_name} imports {offenders}"
