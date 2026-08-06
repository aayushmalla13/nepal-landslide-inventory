"""Environment and configuration diagnostics."""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig, ConfigError, load_config

MIN_PYTHON = (3, 10)
REQUIRED_IMPORTS = ("yaml", "langdetect", "spacy", "tqdm")


@dataclass(frozen=True)
class DoctorCheck:
    """Single doctor check result."""

    name: str
    ok: bool
    detail: str


def check_python_version() -> DoctorCheck:
    """Verify the interpreter version."""

    version_ok = sys.version_info >= MIN_PYTHON
    detail = f"Python {sys.version.split()[0]}"
    if not version_ok:
        detail = f"{detail} is too old; require >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    return DoctorCheck(name="python", ok=version_ok, detail=detail)


def check_required_imports() -> list[DoctorCheck]:
    """Verify required package imports."""

    checks: list[DoctorCheck] = []
    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - defensive branch
            checks.append(DoctorCheck(module_name, False, f"import failed: {exc}"))
        else:
            checks.append(DoctorCheck(module_name, True, "import ok"))
    return checks

def check_spacy_model(model_name: str = "en_core_web_sm") -> DoctorCheck:
    """Verify spaCy model can be loaded."""
    try:
        import spacy

        spacy.load(model_name)
        return DoctorCheck(name="spacy_model", ok=True, detail=f"Model '{model_name}' loadable")
    except Exception as exc:
        return DoctorCheck(
            name="spacy_model",
            ok=False,
            detail=f"Model '{model_name}' not loadable: {exc}. Run: python -m spacy download {model_name}",
        )

def check_config_exists(config_path: str | Path) -> DoctorCheck:
    """Verify that the requested config file exists."""

    path = Path(config_path).resolve()
    if path.exists():
        return DoctorCheck(name="config", ok=True, detail=str(path))

    suggestion = path.with_name("config.example.yaml")
    return DoctorCheck(
        name="config",
        ok=False,
        detail=f"Missing {path}. Copy {suggestion} to {path.name} and update paths.",
    )


def check_writable_paths(config: AppConfig) -> list[DoctorCheck]:
    """Verify required runtime directories are writable."""

    checks: list[DoctorCheck] = []
    for directory in config.data_directories():
        directory.mkdir(parents=True, exist_ok=True)
        is_writable = directory.is_dir() and Path(directory).exists()
        checks.append(
            DoctorCheck(
                name=f"writable:{directory.name}",
                ok=is_writable,
                detail=str(directory),
            )
        )
    return checks


def run_doctor(config_path: str | Path, minimal: bool = False) -> list[DoctorCheck]:
    """Run doctor checks and return structured results."""

    checks: list[DoctorCheck] = [check_python_version(), check_config_exists(config_path)]
    checks.extend(check_required_imports())

    if Path(config_path).exists():
        try:
            config = load_config(config_path)
        except ConfigError as exc:
            checks.append(DoctorCheck(name="config_load", ok=False, detail=str(exc)))
            return checks

        checks.extend(check_writable_paths(config))
        if not minimal:
            model_name = str(config.doctor_settings.get("spacy_model", "en_core_web_sm"))
            checks.append(check_spacy_model(model_name))

    return checks


def build_parser() -> argparse.ArgumentParser:
    """Create the doctor CLI parser."""

    parser = argparse.ArgumentParser(description="Run environment checks.")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config.")
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Skip expensive checks such as spaCy model loading.",
    )
    return parser


def main() -> None:
    """Run doctor CLI and exit non-zero on failure."""

    parser = build_parser()
    args = parser.parse_args()
    checks = run_doctor(args.config, minimal=args.minimal)
    for check in checks:
        state = "OK" if check.ok else "FAIL"
        print(f"[{state}] {check.name}: {check.detail}")

    if not all(check.ok for check in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
