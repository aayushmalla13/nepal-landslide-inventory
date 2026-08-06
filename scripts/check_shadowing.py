"""Guard against top-level modules under src/ shadowing third-party dependencies."""

from __future__ import annotations

import sys
from pathlib import Path

FORBIDDEN_TOP_LEVEL = {
    'yaml',
    'tqdm',
    'langdetect',
    'spacy',
    'pytest',
    'pandas',
    'numpy',
    'requests',
    'bs4',
    'sklearn',
}
ALLOWED_TOP_LEVEL = {'landslide_inventory'}
IGNORED_SUFFIXES = {'.egg-info'}
IGNORED_NAMES = {'__pycache__'}


def find_shadowing_issues(src_dir: Path) -> list[str]:
    """Return human-readable problems for disallowed top-level entries under src/."""

    issues: list[str] = []
    if not src_dir.exists():
        return [f'missing src directory: {src_dir}']

    for entry in sorted(src_dir.iterdir(), key=lambda item: item.name):
        name = entry.name
        if name in IGNORED_NAMES:
            continue
        if any(name.endswith(suffix) for suffix in IGNORED_SUFFIXES):
            continue

        top_level_name = entry.stem if entry.is_file() else name
        if top_level_name in FORBIDDEN_TOP_LEVEL:
            issues.append(f'shadow dependency under src/: {name}')
            continue
        if top_level_name not in ALLOWED_TOP_LEVEL:
            issues.append(f'unexpected top-level entry under src/: {name}')
    return issues


def main() -> None:
    """Run the guard as a CLI."""

    src_dir = Path(__file__).resolve().parents[1] / 'src'
    issues = find_shadowing_issues(src_dir)
    if issues:
        for issue in issues:
            print(issue)
        raise SystemExit(1)
    print(f'no shadowing issues found in {src_dir}')


if __name__ == '__main__':
    main()
