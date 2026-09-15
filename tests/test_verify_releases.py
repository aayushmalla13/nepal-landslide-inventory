"""Tests for the release integrity verifier."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_releases.py"
_spec = importlib.util.spec_from_file_location("verify_releases", MODULE_PATH)
verify_releases = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(verify_releases)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_release(
    directory: Path,
    contents: dict[str, bytes],
    *,
    release_id: str,
    formula: str,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for name, data in contents.items():
        (directory / name).write_bytes(data)
        files.append({"file": name, "sha256": _sha(data), "bytes": len(data)})
    pairs = [(item["file"], item["sha256"]) for item in files]
    if formula == "analysis":
        payload = "\n".join(f"{name}:{digest}" for name, digest in pairs)
        lock = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    else:
        payload = json.dumps(
            ["release_bundle", release_id, [list(pair) for pair in pairs]],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        lock = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    (directory / "release_manifest.json").write_text(
        json.dumps(
            {"release_id": release_id, "files": files, "bundle_lock_hash": lock},
            indent=2,
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize("formula", ["analysis", "inventory"])
def test_both_bundle_lock_formulas_are_recognized(tmp_path: Path, formula: str) -> None:
    """Two builders in this project hash the lock differently; both must pass."""

    release = tmp_path / "rel"
    _make_release(release, {"a.csv": b"1,2\n"}, release_id="rel", formula=formula)
    ok, messages = verify_releases.verify_release(release)
    assert ok
    assert any(f"({formula} formula)" in message for message in messages)


def test_a_tampered_file_is_detected(tmp_path: Path) -> None:
    release = tmp_path / "rel"
    _make_release(release, {"a.csv": b"1,2\n"}, release_id="rel", formula="analysis")
    (release / "a.csv").write_bytes(b"9,9\n")
    ok, messages = verify_releases.verify_release(release)
    assert not ok
    assert any("checksum mismatch" in message for message in messages)


def test_a_missing_file_is_detected(tmp_path: Path) -> None:
    release = tmp_path / "rel"
    _make_release(
        release, {"a.csv": b"1,2\n", "b.csv": b"3,4\n"}, release_id="rel", formula="analysis"
    )
    (release / "b.csv").unlink()
    ok, messages = verify_releases.verify_release(release)
    assert not ok
    assert any("missing files" in message for message in messages)


def test_an_edited_manifest_is_detected(tmp_path: Path) -> None:
    """Rewriting a digest inside the manifest must break the bundle lock."""

    release = tmp_path / "rel"
    _make_release(release, {"a.csv": b"1,2\n"}, release_id="rel", formula="analysis")
    (release / "a.csv").write_bytes(b"9,9\n")
    manifest_path = release / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = _sha(b"9,9\n")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ok, messages = verify_releases.verify_release(release)
    assert not ok
    assert any("bundle lock mismatch" in message for message in messages)


def test_working_output_drift_is_reported(tmp_path: Path) -> None:
    release = tmp_path / "rel"
    _make_release(
        release, {"a.csv": b"1,2\n", "b.csv": b"3,4\n"}, release_id="rel", formula="analysis"
    )
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "a.csv").write_bytes(b"1,2\n")
    (outputs / "b.csv").write_bytes(b"changed\n")
    assert verify_releases.compare_working_outputs(release, outputs) == ["b.csv"]


def test_working_output_comparison_ignores_files_not_in_outputs(tmp_path: Path) -> None:
    release = tmp_path / "rel"
    _make_release(release, {"a.csv": b"1,2\n"}, release_id="rel", formula="analysis")
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    assert verify_releases.compare_working_outputs(release, outputs) == []


def test_main_reports_success_and_failure(tmp_path: Path, capsys) -> None:
    root = tmp_path
    (root / "data" / "outputs").mkdir(parents=True)
    good = root / "data" / "releases" / "nepal_landslide_rainfall_v9.9.9_20260101"
    _make_release(good, {"a.csv": b"1,2\n"}, release_id=good.name, formula="analysis")
    exit_code = _run_main(root)
    assert exit_code == 0
    assert "All checked releases verified." in capsys.readouterr().out

    (good / "a.csv").write_bytes(b"tampered\n")
    assert _run_main(root) == 1


def _run_main(root: Path) -> int:
    import sys

    argv = sys.argv
    sys.argv = ["verify_releases.py", "--root", str(root)]
    try:
        return verify_releases.main()
    finally:
        sys.argv = argv
