#!/usr/bin/env python3
"""Verify every frozen release bundle and compare it with the working outputs.

Checks performed for each release directory under ``data/releases``:

1. every file listed in ``release_manifest.json`` exists and matches its
   recorded SHA-256;
2. the recorded ``bundle_lock_hash`` equals the hash recomputed from those
   digests, so a manifest cannot be edited without detection; and
3. for the current rainfall release, whether the working copies in
   ``data/outputs`` still match the frozen copies.

Item 3 is a warning, not a failure: re-running the analysis is allowed, and a
difference simply means the working tree has moved ahead of the frozen release
and a new version is needed before the new numbers are reported.

Usage::

    python3 scripts/verify_releases.py [--root .] [--strict]

``--strict`` also treats a working-copy drift as a failure. Exit status is 0
when everything checked passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

MANIFEST = "release_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lock_candidates(manifest: dict, files: list[dict]) -> dict[str, str]:
    """Recompute the bundle lock under each formula used in this project.

    Two builders exist and they hash differently, so a verifier that knew only
    one would raise a false alarm on the other:

    * ``analysis`` -- ``analysis/release.py`` joins ``file:sha256`` with newlines.
    * ``inventory`` -- ``validation/final_report.py`` uses ``stable_hash`` over
      ``("release_bundle", release_id, [(file, sha256), ...])``.
    """

    pairs = [(item["file"], item["sha256"]) for item in files]
    joined = "\n".join(f"{name}:{digest}" for name, digest in pairs)
    stable_payload = json.dumps(
        ["release_bundle", manifest.get("release_id"), [list(pair) for pair in pairs]],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "analysis": hashlib.sha256(joined.encode("utf-8")).hexdigest(),
        "inventory": hashlib.sha256(stable_payload.encode("utf-8")).hexdigest(),
    }


def verify_release(release_dir: Path) -> tuple[bool, list[str]]:
    """Return (ok, messages) for one release directory."""

    messages: list[str] = []
    manifest_path = release_dir / MANIFEST
    if not manifest_path.exists():
        return False, [f"missing {MANIFEST}"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    if not files:
        return False, ["manifest lists no files"]

    missing: list[str] = []
    mismatched: list[str] = []
    for entry in files:
        path = release_dir / entry["file"]
        if not path.exists():
            missing.append(entry["file"])
            continue
        if sha256(path) != entry["sha256"]:
            mismatched.append(entry["file"])

    ok = not missing and not mismatched
    if missing:
        messages.append(f"missing files: {', '.join(sorted(missing))}")
    if mismatched:
        messages.append(f"checksum mismatch: {', '.join(sorted(mismatched))}")

    recorded_lock = manifest.get("bundle_lock_hash")
    if recorded_lock:
        candidates = _lock_candidates(manifest, files)
        if recorded_lock in candidates.values():
            formula = next(k for k, v in candidates.items() if v == recorded_lock)
            messages.append(
                f"lock {recorded_lock[:12]} ok ({formula} formula), {len(files)} files"
            )
        else:
            ok = False
            messages.append(
                f"bundle lock mismatch: manifest={recorded_lock[:12]}, "
                "recomputed under no known formula "
                f"({', '.join(f'{k}={v[:12]}' for k, v in candidates.items())})"
            )
    else:
        messages.append(f"{len(files)} files, no bundle lock recorded")
    return ok, messages


def compare_working_outputs(release_dir: Path, outputs_dir: Path) -> list[str]:
    """Report frozen files whose working copy has since changed."""

    manifest = json.loads((release_dir / MANIFEST).read_text(encoding="utf-8"))
    drifted: list[str] = []
    for entry in manifest.get("files", []):
        candidate = outputs_dir / entry["file"]
        if not candidate.exists():
            continue
        if sha256(candidate) != entry["sha256"]:
            drifted.append(entry["file"])
    return sorted(drifted)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat working-copy drift from the newest rainfall release as a failure",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    releases_dir = root / "data" / "releases"
    if not releases_dir.is_dir():
        print(f"no releases directory at {releases_dir}", file=sys.stderr)
        return 2

    failures = 0
    release_dirs = sorted(p for p in releases_dir.iterdir() if (p / MANIFEST).exists())
    if not release_dirs:
        print("no release manifests found", file=sys.stderr)
        return 2

    for release_dir in release_dirs:
        ok, messages = verify_release(release_dir)
        status = "OK  " if ok else "FAIL"
        print(f"[{status}] {release_dir.name}")
        for message in messages:
            print(f"         {message}")
        if not ok:
            failures += 1

    rainfall = [p for p in release_dirs if p.name.startswith("nepal_landslide_rainfall_")]
    if rainfall:
        newest = rainfall[-1]
        drifted = compare_working_outputs(newest, root / "data" / "outputs")
        print()
        if drifted:
            print(f"[WARN] working outputs differ from {newest.name}:")
            for name in drifted:
                print(f"         {name}")
            print(
                "         Re-running the analysis is allowed. Cut a new versioned\n"
                "         release before reporting numbers from these files."
            )
            if args.strict:
                failures += 1
        else:
            print(f"[OK  ] working outputs match {newest.name}")

    print()
    print("FAILED" if failures else "All checked releases verified.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
