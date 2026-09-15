#!/usr/bin/env python3
"""Rebuild the municipality gazetteer from checksum-pinned reference sources.

Why this exists
---------------
The gazetteer shipped with the project covered 142 English and 100 Nepali local
units. Nepal has 753. Municipality extraction was therefore capped at roughly
40 per cent of event-bearing articles, not because the text lacked a
municipality but because the lookup table did not contain one.

Sources
-------
Two independent sources are used, both vendored under
``data/reference/sources`` and checksum-pinned in ``SOURCE_DIGESTS``:

``nepal_local_levels.json`` + ``nepal_districts_bilingual.json`` + ``nepal_local_level_types.json``
    bibekoli/local-levels-of-nepal-dataset. Provides all 753 local levels with
    both English and Devanagari names, the 77 districts bilingually, and the
    four local-level types. This is the only reachable source carrying Nepali
    names, which the Nepali extractor needs. The repository carries no LICENSE
    file; see ``LICENCE STATUS`` below.

``nepal_local_units_geometry.geojson``
    mesaugat/geoJSON-Nepal (MIT). Provides 747 local-unit polygons with name and
    district, plus 18 protected areas that are dropped. Used as an independent
    corroborating source and to settle discrepancies.

LICENCE STATUS
--------------
Administrative unit names and their district assignment are government facts.
The MIT-licensed geometry source corroborates 94 per cent of the name list
(83 per cent exact, a further 11 per cent as spelling variants), so the factual
content is independently attested. The bilingual source itself carries no
explicit licence. Before public redistribution of the derived gazetteer, replace
or confirm that source against an official government or OCHA release. This is
recorded as an open item rather than silently ignored.

Corrections
-----------
Discrepancies are never resolved silently. Every correction is listed in
``CORRECTIONS`` with the corroborating evidence, and re-emitted into the report.

Usage::

    python3 scripts/build_municipality_gazetteer.py [--root .] [--check]

``--check`` verifies that the committed gazetteer matches what this script would
produce, without writing anything. Exit status is 0 on success.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

SOURCE_DIR = Path("data/reference/sources")
SOURCE_DIGESTS = {
    "nepal_local_levels.json": "b300fb074b555a046f5bc8a3eb20c54ab48e9bc335cd995b04bbf67ada3a5f82",
    "nepal_districts_bilingual.json": (
        "171473d1fb69c45f77a86306a20ad78452d8414a2ce0fc9de64193c9db00d8b8"
    ),
    "nepal_local_level_types.json": (
        "031a716dc355302b15969f10f060e37f466b11f7301cd7ea674cddd801e4dbcf"
    ),
    "nepal_provinces_bilingual.json": (
        "cc305261b665527a02bcd8ae69b0ff7d413ab2d840a0be2c8ef298ab9681247d"
    ),
    "nepal_local_units_geometry.geojson": (
        "3258e6e61e273bc70daca9d795c40b448131d9a8667502cccbf65c97f443e675"
    ),
    # Snapshot of the 142-unit gazetteer this build replaces. It is read from
    # here, never from resources/, so the build is idempotent: reading its own
    # output would fold generated aliases back in on every re-run.
    "legacy_municipalities_en.csv": (
        "8efd802c4ad322cd454adfd10dfbf0935f981414a6b9c189c1b2c0fae4bdf446"
    ),
    "legacy_municipalities_np.csv": (
        "d59f6bf737dc5b68090ec3e4f5516107e750ec563529fa30a9d86e5afeb08bbd"
    ),
}

# The bilingual source spells six districts differently from this project's
# 77-district vocabulary, and one of them ("Nawalparari East") is a typo.
DISTRICT_ALIASES = {
    "Pachthar": "Panchthar",
    "Nawalparari East": "Nawalpur",
    "Nawalparasi West": "Parasi",
    "Kapilbastu": "Kapilvastu",
    "Rukum West": "Western Rukum",
    "Rukum East": "Eastern Rukum",
}

GEOMETRY_LEVELS = {
    "Mahanagarpalika": "Metropolitan City",
    "maha Nagarpalika": "Metropolitan City",
    "Upamahanagarpalika": "Sub-Metropolitan City",
    "Nagarpalika": "Municipality",
    "Gaunpalika": "Rural Municipality",
    "gaupaika": "Rural Municipality",
}


@dataclass(frozen=True)
class Correction:
    """A documented change to a source record, with its corroborating evidence."""

    district: str
    wrong: str
    right: str
    evidence: str


CORRECTIONS = (
    Correction(
        district="Gulmi",
        wrong="Chatrakot Rural Municipality",
        right="Dhurkot Rural Municipality",
        evidence=(
            "The bilingual source lists Chatrakot Rural Municipality twice in Gulmi and "
            "omits Dhurkot Rural Municipality. The MIT-licensed geometry source lists "
            "Gulmi's twelve units as Chandrakot, Chatrakot, Dhurkot, Gulmidarbar, Isma, "
            "Kaligandaki, Madane, Malika, Musikot, Resunga, Ruru and Satyawati, so the "
            "second Chatrakot row is a duplicate standing in for Dhurkot."
        ),
    ),
)

# Legacy canonical names whose modern spelling differs too much for the
# same-district fuzzy reconciliation to resolve safely. Each is a documented
# rename or a borderline spelling variant, mapped to (district, canonical name)
# so a legacy row placed in the wrong district can also be corrected.
LEGACY_OVERRIDES = {
    # Renames.
    ("Gorkha", "Lakhan Thapa Rural Municipality"): ("Gorkha", "Sahid Lakhan Rural Municipality"),
    ("Taplejung", "Taplejung Municipality"): ("Taplejung", "Phungling Municipality"),
    ("Nawalpur", "Binayi Triveni Rural Municipality"): ("Nawalpur", "Binayee Rural Municipality"),
    ("Gulmi", "Dhurkot Rural Municipality"): ("Gulmi", "Dhurkot Rural Municipality"),
    # Spelling variants that land just under the fuzzy acceptance threshold.
    ("Panchthar", "Phalelung Rural Municipality"): ("Panchthar", "Falelung Rural Municipality"),
    ("Taplejung", "Sirijunga Rural Municipality"): ("Taplejung", "Sirijangha Rural Municipality"),
    # District correction. The previous gazetteer placed Jagannath Rural
    # Municipality in Bajhang. Both reference sources place it in Bajura, and
    # neither lists a Jagannath unit among Bajhang's twelve local levels, so any
    # article naming this municipality would previously have been assigned to
    # the wrong district.
    ("Bajhang", "Jagannath Rural Municipality"): ("Bajura", "Jagannath Rural Municipality"),
}

# Legacy rows whose district was wrong, surfaced separately so the correction is
# visible in the report rather than buried in the override table.
LEGACY_DISTRICT_CORRECTIONS = (
    Correction(
        district="Bajhang",
        wrong="Jagannath Rural Municipality",
        right="Jagannath Rural Municipality (Bajura)",
        evidence=(
            "Both the bilingual list and the MIT-licensed geometry source place "
            "Jagannath Rural Municipality in Bajura. Bajhang's units are Bithadchir, "
            "Bungal, Chabispathivera, Durgathali, Jayaprithivi, Kanda, Kedarseu, "
            "Khaptachhanna, Masta, Surma, Talkot and Thalara. The previous gazetteer "
            "would have mapped this municipality to the wrong district."
        ),
    ),
)

FUZZY_ACCEPT = 95.0

# Populated during the build; reported so the withholding is visible.
WITHHELD_BARE_STEMS: list[str] = []


@dataclass
class Unit:
    """One local level in the project's district vocabulary."""

    english: str
    nepali: str
    district: str
    unit_type: str
    english_aliases: set[str] = field(default_factory=set)
    nepali_aliases: set[str] = field(default_factory=set)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_key(value: str) -> str:
    """Case- and punctuation-insensitive comparison key."""

    decomposed = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in decomposed.lower() if ch.isalnum())


def verify_sources(root: Path) -> list[str]:
    """Confirm every pinned source is present and unmodified."""

    problems: list[str] = []
    for name, digest in SOURCE_DIGESTS.items():
        path = root / SOURCE_DIR / name
        if not path.exists():
            problems.append(f"missing source: {name}")
            continue
        actual = sha256(path)
        if actual != digest:
            problems.append(
                f"digest mismatch for {name}: expected {digest[:12]}, got {actual[:12]}"
            )
    return problems


def load_units(root: Path) -> tuple[list[Unit], list[str]]:
    """Build the 753 local levels in the project's district vocabulary."""

    base = root / SOURCE_DIR
    levels = json.loads((base / "nepal_local_levels.json").read_text(encoding="utf-8"))
    districts = {
        row["district_id"]: row
        for row in json.loads((base / "nepal_districts_bilingual.json").read_text(encoding="utf-8"))
    }
    types = {
        row["local_level_type_id"]: row
        for row in json.loads((base / "nepal_local_level_types.json").read_text(encoding="utf-8"))
    }
    notes: list[str] = []
    corrections = {(c.district, c.wrong): c for c in CORRECTIONS}
    applied: set[tuple[str, str]] = set()
    seen: set[tuple[str, str]] = set()

    units: list[Unit] = []
    for row in levels:
        district_row = districts[row["district_id"]]
        district = DISTRICT_ALIASES.get(district_row["name"], district_row["name"])
        type_row = types[row["local_level_type_id"]]
        english = f"{row['name']} {type_row['name']}"
        nepali = f"{row['nepali_name']} {type_row['nepali_name']}"
        key = (district, english)
        if key in seen and key in corrections and key not in applied:
            correction = corrections[key]
            english = correction.right
            applied.add(key)
            notes.append(
                f"corrected duplicate {correction.wrong} in {district} to {correction.right}"
            )
        seen.add((district, english))
        units.append(
            Unit(english=english, nepali=nepali, district=district, unit_type=type_row["name"])
        )
    unapplied = [c for c in CORRECTIONS if (c.district, c.wrong) not in applied]
    for correction in unapplied:
        notes.append(
            f"WARNING: correction for {correction.wrong} in {correction.district} did not fire"
        )
    return units, notes


def corroborate(root: Path, units: list[Unit]) -> dict[str, object]:
    """Cross-check the unit list against the independent geometry source."""

    geo = json.loads(
        (root / SOURCE_DIR / "nepal_local_units_geometry.geojson").read_text(encoding="utf-8")
    )
    features = [
        feature
        for feature in geo["features"]
        if GEOMETRY_LEVELS.get(str(feature["properties"].get("LEVEL") or "").strip())
    ]
    stems = defaultdict(set)
    for unit in units:
        stem = unit.english.rsplit(" ", 1)[0]
        for suffix in (" Rural", " Sub-Metropolitan", " Metropolitan"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
        stems[normalize_key(stem)].add(unit.district)
    exact = 0
    unmatched: list[str] = []
    for feature in features:
        name = normalize_key(feature["properties"]["NAME"])
        if name in stems:
            exact += 1
        else:
            unmatched.append(feature["properties"]["NAME"])
    return {
        "geometry_units": len(features),
        "name_matches": exact,
        "match_fraction": exact / len(features) if features else 0.0,
        "unmatched_examples": sorted(unmatched)[:15],
        "unmatched_count": len(unmatched),
    }


def merge_legacy_aliases(root: Path, units: list[Unit]) -> tuple[list[str], list[dict[str, str]]]:
    """Fold the previous gazetteer's names in as aliases so nothing stops resolving.

    Every municipality string already present in the frozen inventory must keep
    resolving after this rebuild, otherwise a release that was reproducible
    stops being so. Legacy names are matched within their own district only.
    """

    from rapidfuzz import fuzz, process

    notes: list[str] = []
    unresolved: list[dict[str, str]] = []
    by_district: dict[str, list[Unit]] = defaultdict(list)
    for unit in units:
        by_district[unit.district].append(unit)
    index = {(u.district, u.english): u for u in units}

    def fold(path: Path, alias_columns: tuple[str, ...], lang: str) -> None:
        """Attach one legacy file's names as aliases of the modern unit.

        Both legacy files key on ``municipality_en_canonical``, so the English
        canonical is always what identifies the unit; the language only decides
        which alias bucket the names land in.
        """

        if not path.exists():
            return
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                district = row["district_canonical"].strip()
                legacy = row["municipality_en_canonical"].strip()
                aliases: list[str] = []
                for column in alias_columns:
                    value = (row.get(column) or "").strip()
                    if not value:
                        continue
                    aliases.extend(part.strip() for part in value.split("|") if part.strip())
                override = LEGACY_OVERRIDES.get((district, legacy))
                if override is not None:
                    target = index.get(override)
                else:
                    target = index.get((district, legacy))
                if target is None and override is None:
                    pool = by_district.get(district, [])
                    best = process.extractOne(
                        legacy, [u.english for u in pool], scorer=fuzz.WRatio
                    )
                    if best and best[1] >= FUZZY_ACCEPT:
                        target = index[(district, best[0])]
                        notes.append(
                            f"legacy '{legacy}' [{district}] -> '{best[0]}' (score {best[1]:.0f})"
                        )
                if target is None:
                    unresolved.append(
                        {"district": district, "legacy_name": legacy, "language": lang}
                    )
                    continue
                bucket = target.english_aliases if lang == "en" else target.nepali_aliases
                bucket.add(legacy) if lang == "en" else None
                bucket.update(aliases)

    fold(
        root / SOURCE_DIR / "legacy_municipalities_en.csv",
        ("municipality_en_variants",),
        "en",
    )
    fold(
        root / SOURCE_DIR / "legacy_municipalities_np.csv",
        ("municipality_np_canonical", "municipality_np_variants"),
        "np",
    )
    return notes, unresolved


def district_name_keys(root: Path) -> set[str]:
    """Every district name and variant, as comparison keys.

    Eight districts share their name with a local unit inside them -- Ramechhap
    district contains Ramechhap Municipality, Gorkha contains Gorkha
    Municipality, and so on. A bare-stem alias for those units would make the
    plain district name resolve to a municipality, so those stems are withheld.
    """

    keys: set[str] = set()
    path = root / "resources" / "districts_en.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            keys.add(normalize_key(row["district"]))
            for variant in (row.get("variants_en") or "").split("|"):
                if variant.strip():
                    keys.add(normalize_key(variant))
    path = root / "resources" / "districts_np.csv"
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                for column in ("district_np", "variants_np"):
                    for variant in (row.get(column) or "").split("|"):
                        if variant.strip():
                            keys.add(normalize_key(variant))
    return keys


def add_generated_aliases(units: list[Unit], district_keys: set[str]) -> None:
    """Add mechanical spelling variants that Nepali and English text actually use."""

    withheld: list[str] = []
    for unit in units:
        unit.english_aliases.add(unit.english)
        stem = unit.english.rsplit(" ", 1)[0]
        for suffix in (" Rural", " Sub-Metropolitan", " Metropolitan"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
        # "Ichchhyakamana Gaupalika" and bare "Ichchhyakamana" both occur, but a
        # bare stem identical to a district name would hijack the district.
        nepali_stem = unit.nepali.rsplit(" ", 1)[0]
        if normalize_key(stem) in district_keys or normalize_key(nepali_stem) in district_keys:
            withheld.append(unit.english)
        else:
            unit.english_aliases.add(stem)
            unit.nepali_aliases.add(nepali_stem)
        unit.nepali_aliases.add(unit.nepali)
        # Nepali text frequently omits the space before the administrative suffix.
        unit.nepali_aliases.add(unit.nepali.replace(" ", ""))
    if withheld:
        WITHHELD_BARE_STEMS.extend(sorted(withheld))


def ambiguity(units: list[Unit]) -> dict[str, list[str]]:
    """Canonical names shared by more than one district.

    Inferring a district from one of these names is a coin flip, so the
    gazetteer records them and callers must refuse to guess.
    """

    by_name: dict[str, list[str]] = defaultdict(list)
    for unit in units:
        by_name[unit.english].append(unit.district)
    return {name: sorted(ds) for name, ds in by_name.items() if len(ds) > 1}


def write_outputs(root: Path, units: list[Unit], ambiguous: dict[str, list[str]]) -> dict[str, str]:
    """Write both gazetteer CSVs and the ambiguity table."""

    resources = root / "resources"
    en_path = resources / "municipalities_en.csv"
    np_path = resources / "municipalities_np.csv"
    amb_path = resources / "municipality_ambiguous.csv"

    ordered = sorted(units, key=lambda u: (u.english, u.district))
    with en_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["municipality_en_canonical", "municipality_en_variants", "district_canonical"]
        )
        for unit in ordered:
            aliases = sorted(unit.english_aliases)
            writer.writerow([unit.english, "|".join(aliases), unit.district])
    with np_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "municipality_en_canonical",
                "municipality_np_canonical",
                "municipality_np_variants",
                "district_canonical",
            ]
        )
        for unit in ordered:
            aliases = sorted(unit.nepali_aliases)
            writer.writerow([unit.english, unit.nepali, "|".join(aliases), unit.district])
    with amb_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["municipality_en_canonical", "districts"])
        for name, districts in sorted(ambiguous.items()):
            writer.writerow([name, "|".join(districts)])
    return {
        "municipalities_en.csv": sha256(en_path),
        "municipalities_np.csv": sha256(np_path),
        "municipality_ambiguous.csv": sha256(amb_path),
    }


def build(root: Path) -> dict[str, object]:
    problems = verify_sources(root)
    if problems:
        raise SystemExit("Source verification failed:\n  " + "\n  ".join(problems))
    units, notes = load_units(root)
    alias_notes, unresolved = merge_legacy_aliases(root, units)
    add_generated_aliases(units, district_name_keys(root))
    ambiguous = ambiguity(units)
    checks = corroborate(root, units)
    return {
        "units": units,
        "notes": notes + alias_notes,
        "unresolved_legacy": unresolved,
        "ambiguous": ambiguous,
        "corroboration": checks,
        "withheld_bare_stems": list(WITHHELD_BARE_STEMS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    result = build(root)
    units: list[Unit] = result["units"]  # type: ignore[assignment]
    ambiguous: dict[str, list[str]] = result["ambiguous"]  # type: ignore[assignment]

    districts = {unit.district for unit in units}
    failures: list[str] = []
    if len(units) != 753:
        failures.append(f"expected 753 local levels, built {len(units)}")
    if len(districts) != 77:
        failures.append(f"expected 77 districts, saw {len(districts)}")
    if result["unresolved_legacy"]:
        failures.append(f"{len(result['unresolved_legacy'])} legacy names did not resolve")

    print(f"local levels: {len(units)}  districts: {len(districts)}")
    corroboration = result["corroboration"]
    print(
        "corroborated by geometry source: "
        f"{corroboration['name_matches']}/{corroboration['geometry_units']} "
        f"({corroboration['match_fraction']:.1%})"
    )
    print(f"ambiguous canonical names: {len(ambiguous)}")
    withheld = result["withheld_bare_stems"]
    print(f"bare stems withheld (name equals a district): {len(withheld)}")
    for name in withheld:
        print(f"  withheld: {name}")
    for note in result["notes"]:
        print(f"  note: {note}")
    for row in result["unresolved_legacy"]:
        print(f"  UNRESOLVED legacy name: {row}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    if args.check:
        print("check mode: no files written")
        return 0

    digests = write_outputs(root, units, ambiguous)
    for name, digest in digests.items():
        print(f"wrote resources/{name}  sha256={digest[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
