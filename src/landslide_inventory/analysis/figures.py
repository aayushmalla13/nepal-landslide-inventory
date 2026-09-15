"""Dependency-free SVG figures for the rainfall-threshold manuscript.

Every figure is generated from the analysis outputs on disk, so a figure can
never disagree with the numbers in the report.  SVG is written by hand rather
than through a plotting library to keep the analysis installable with nothing
beyond the standard library and PyYAML.

Figures
-------
1. Temporal-test ROC curves and the prespecified sensitivity designs.
2. Spatial distribution of the inventory: district choropleth and province bars.
3. Seasonality and the case-versus-control rainfall distributions.
4. Held-out validation: leave-one-year-out and spatial folds, with the
   concurrent and strictly antecedent exposures side by side.
"""

from __future__ import annotations

import csv
import html
import json
import math
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from ..config import AppConfig
from .pipeline import ANTECEDENT, CONCURRENT, PRIMARY_VARIANT
from .rainfall import normalize_district

WINDOW_COLORS = {1: "#6A51A3", 3: "#3182BD", 5: "#E6550D", 7: "#31A354"}
EXPOSURE_COLORS = {CONCURRENT: "#E6550D", ANTECEDENT: "#3182BD"}
CHOROPLETH = ["#F7FBFF", "#DEEBF7", "#C6DBEF", "#9ECAE1", "#6BAED6", "#3182BD", "#08519C"]
VARIANT_LABELS = {
    PRIMARY_VARIANT: "Primary",
    "all_dated_events": "All dated events",
    "high_conf_ge_0.80": "Date confidence ≥0.80",
    "primary_date_minus_1d": "Date −1 day",
    "primary_date_plus_1d": "Date +1 day",
    "include_known_nonrain_triggers": "Include non-rain triggers",
    "exclude_road_obstructions": "Exclude road obstructions",
    "balanced_source_panel": "Balanced source panel",
    "strict_matched_sets": "Strict matched sets",
}
FONT = "Arial,Helvetica,sans-serif"


def _line(x1: float, y1: float, x2: float, y2: float, **attrs: object) -> str:
    values = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, **attrs}
    body = " ".join(f'{key.replace("_", "-")}="{value}"' for key, value in values.items())
    return f"<line {body}/>"


def _text(x: float, y: float, value: object, **attrs: object) -> str:
    values = {"x": x, "y": y, **attrs}
    body = " ".join(f'{key.replace("_", "-")}="{item}"' for key, item in values.items())
    return f"<text {body}>{html.escape(str(value))}</text>"


def _rect(x: float, y: float, width: float, height: float, **attrs: object) -> str:
    values = {"x": x, "y": y, "width": width, "height": height, **attrs}
    body = " ".join(f'{key.replace("_", "-")}="{item}"' for key, item in values.items())
    return f"<rect {body}/>"


def _document(width: int, height: int, parts: Sequence[str]) -> str:
    header = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<g font-family="{FONT}" fill="#222">',
    ]
    return "\n".join([*header, *parts, "</g></svg>"]) + "\n"


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: str | None) -> float:
    try:
        return float(value) if value not in (None, "") else math.nan
    except ValueError:
        return math.nan


def _axis(
    parts: list[str],
    left: float,
    top: float,
    width: float,
    height: float,
    x_label: str,
    y_label: str,
) -> None:
    parts.append(_line(left, top + height, left + width, top + height, stroke="#222"))
    parts.append(_line(left, top, left, top + height, stroke="#222"))
    parts.append(
        _text(left + width / 2, top + height + 40, x_label, font_size=13, text_anchor="middle")
    )
    centre = top + height / 2
    parts.append(
        f'<text x="{left - 46}" y="{centre}" font-size="13" text-anchor="middle" '
        f'transform="rotate(-90 {left - 46} {centre})">{html.escape(y_label)}</text>'
    )


def figure_roc(outputs: Path) -> str:
    """Figure 1 -- temporal-test ROC curves and the sensitivity designs."""

    roc_rows = [
        row
        for row in _read(outputs / "rainfall_primary_test_roc.csv")
        if row["exposure"] == CONCURRENT
    ]
    metrics = _read(outputs / "rainfall_threshold_metrics.csv")
    sensitivity = [
        row
        for row in _read(outputs / "rainfall_sensitivity_summary.csv")
        if row["exposure"] == CONCURRENT
    ]
    auc_by_window = {
        int(row["window_days"]): _float(row["auc"])
        for row in metrics
        if row["variant"] == PRIMARY_VARIANT
        and row["split"] == "temporal_test"
        and row["exposure"] == CONCURRENT
    }
    curves: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in roc_rows:
        curves[int(row["window_days"])].append(
            (_float(row["false_positive_rate"]), _float(row["true_positive_rate"]))
        )

    width, height = 1180, 640
    parts = [
        _text(
            50,
            34,
            "Antecedent rainfall discrimination for media-reported landslide days",
            font_size=20,
            font_weight="bold",
        ),
        _text(
            50,
            56,
            "Concurrent windows ending on the reported event day; temporal test period 2023 onward",
            font_size=12,
            fill="#555",
        ),
        _text(70, 92, "A. Temporal-test ROC curves", font_size=15, font_weight="bold"),
    ]
    left, top, plot_width, plot_height = 90, 112, 400, 400
    _axis(parts, left, top, plot_width, plot_height, "False-positive rate", "True-positive rate")
    parts.append(
        _line(
            left,
            top + plot_height,
            left + plot_width,
            top,
            stroke="#999",
            stroke_dasharray="5 5",
        )
    )
    for tick in range(6):
        value = tick / 5
        x = left + value * plot_width
        y = top + plot_height - value * plot_height
        parts.append(_line(x, top + plot_height, x, top + plot_height + 5, stroke="#222"))
        parts.append(
            _text(x, top + plot_height + 22, f"{value:.1f}", font_size=11, text_anchor="middle")
        )
        parts.append(_line(left - 5, y, left, y, stroke="#222"))
        parts.append(_text(left - 10, y + 4, f"{value:.1f}", font_size=11, text_anchor="end"))
    for index, window in enumerate(sorted(curves)):
        points = curves[window]
        stride = max(1, len(points) // 500)
        selected = points[::stride]
        if selected[-1] != points[-1]:
            selected.append(points[-1])
        coordinates = " ".join(
            f"{left + fpr * plot_width:.1f},{top + plot_height - tpr * plot_height:.1f}"
            for fpr, tpr in selected
        )
        parts.append(
            f'<polyline points="{coordinates}" fill="none" '
            f'stroke="{WINDOW_COLORS[window]}" stroke-width="2.2"/>'
        )
        legend_y = 372 + index * 24
        parts.append(
            _line(300, legend_y, 326, legend_y, stroke=WINDOW_COLORS[window], stroke_width=3)
        )
        parts.append(
            _text(
                334,
                legend_y + 4,
                f"R{window} AUC {auc_by_window.get(window, float('nan')):.3f}",
                font_size=12,
            )
        )

    parts.append(
        _text(600, 92, "B. Prespecified sensitivity designs", font_size=15, font_weight="bold")
    )
    panel_left, panel_top, panel_width = 810, 118, 270
    low, high = 0.55, 0.75
    for tick in range(5):
        value = low + tick * (high - low) / 4
        x = panel_left + (value - low) / (high - low) * panel_width
        parts.append(_line(x, panel_top, x, panel_top + 400, stroke="#e8e8e8"))
        parts.append(_text(x, panel_top + 420, f"{value:.2f}", font_size=11, text_anchor="middle"))
    for index, row in enumerate(sensitivity):
        y = panel_top + 26 + index * 42
        value = _float(row["test_auc"])
        x = panel_left + (value - low) / (high - low) * panel_width
        window = int(row["selected_window_days"])
        colour = WINDOW_COLORS.get(window, "#666")
        parts.append(
            _text(
                panel_left - 12,
                y + 4,
                VARIANT_LABELS.get(row["variant"], row["variant"]),
                font_size=11,
                text_anchor="end",
            )
        )
        parts.append(_line(panel_left, y, max(x, panel_left), y, stroke=colour, stroke_width=6))
        parts.append(f'<circle cx="{x:.1f}" cy="{y}" r="5" fill="{colour}"/>')
        parts.append(_text(x + 9, y + 4, f"{value:.3f} (R{window})", font_size=11))
    parts.append(
        _text(
            panel_left + panel_width / 2,
            panel_top + 450,
            "Temporal-test AUC",
            font_size=13,
            text_anchor="middle",
        )
    )
    parts.append(
        _text(
            50,
            height - 24,
            "Each design selected its own window in development data before the temporal test; "
            "bar colour marks the selected window.",
            font_size=11,
            fill="#555",
        )
    )
    return _document(width, height, parts)


def _project(
    features: Sequence[dict], box: tuple[float, float, float, float]
) -> tuple[list[tuple[str, list[list[tuple[float, float]]]]], float, float]:
    """Equirectangular projection with a latitude-dependent width correction.

    Nepal spans roughly 26-31 degrees north, so plain lon/lat plotting stretches
    the map east-west by about 12 per cent.  Scaling longitudes by the cosine of
    the mean latitude keeps district shapes recognisable without adding a
    projection dependency.
    """

    left, top, width, height = box
    latitudes: list[float] = []
    longitudes: list[float] = []
    for feature in features:
        for ring in feature["geometry"]["coordinates"]:
            for point in ring:
                longitudes.append(float(point[0]))
                latitudes.append(float(point[1]))
    mean_latitude = sum(latitudes) / len(latitudes)
    stretch = math.cos(math.radians(mean_latitude))
    min_x, max_x = min(longitudes) * stretch, max(longitudes) * stretch
    min_y, max_y = min(latitudes), max(latitudes)
    scale = min(width / (max_x - min_x), height / (max_y - min_y))
    offset_x = left + (width - (max_x - min_x) * scale) / 2
    offset_y = top + (height - (max_y - min_y) * scale) / 2

    shapes: list[tuple[str, list[list[tuple[float, float]]]]] = []
    for feature in features:
        name = normalize_district(str(feature["properties"]["DISTRICT"]))
        rings = [
            [
                (
                    offset_x + (float(point[0]) * stretch - min_x) * scale,
                    offset_y + (max_y - float(point[1])) * scale,
                )
                for point in ring
            ]
            for ring in feature["geometry"]["coordinates"]
        ]
        shapes.append((name, rings))
    return shapes, offset_x, offset_y


def figure_map(outputs: Path, boundaries: Path) -> str:
    """Figure 2 -- spatial distribution of the inventory."""

    district_rows = _read(outputs / "inventory_district_summary.csv")
    province_rows = _read(outputs / "inventory_province_summary.csv")
    counts = {
        normalize_district(row["district"]): int(row["canonical_events"]) for row in district_rows
    }
    geo = json.loads(boundaries.read_text(encoding="utf-8"))
    shapes, _, _ = _project(geo["features"], (60.0, 110.0, 640.0, 420.0))

    positive = sorted(value for value in counts.values() if value > 0)
    breaks: list[float] = []
    if positive:
        for index in range(1, len(CHOROPLETH)):
            position = index / len(CHOROPLETH) * (len(positive) - 1)
            breaks.append(positive[int(position)])

    def colour_for(value: int) -> str:
        if value <= 0:
            return "#FFFFFF"
        for index, edge in enumerate(breaks):
            if value <= edge:
                return CHOROPLETH[index]
        return CHOROPLETH[-1]

    width, height = 1180, 700
    parts = [
        _text(
            50,
            34,
            "Spatial and administrative distribution of the media-derived inventory",
            font_size=20,
            font_weight="bold",
        ),
        _text(
            50,
            56,
            "Counts are reported events, not landslide incidence: they carry media coverage as "
            "well as hazard.",
            font_size=12,
            fill="#555",
        ),
        _text(70, 92, "A. Canonical events per district", font_size=15, font_weight="bold"),
    ]
    for name, rings in shapes:
        fill = colour_for(counts.get(name, 0))
        for ring in rings:
            path = " ".join(f"{x:.1f},{y:.1f}" for x, y in ring)
            parts.append(
                f'<polygon points="{path}" fill="{fill}" stroke="#5a5a5a" stroke-width="0.6"/>'
            )
    legend_left, legend_top = 80, 560
    parts.append(_text(legend_left, legend_top - 10, "Events per district", font_size=12))
    labels = ["0"]
    for index, edge in enumerate(breaks):
        labels.append(f"≤{int(edge)}")
        if index == len(breaks) - 1:
            labels.append(f">{int(edge)}")
    swatches = ["#FFFFFF", *CHOROPLETH]
    for index, colour in enumerate(swatches):
        x = legend_left + index * 46
        parts.append(
            _rect(x, legend_top, 44, 16, fill=colour, stroke="#5a5a5a", stroke_width="0.6")
        )
        if index < len(labels):
            parts.append(
                _text(x + 22, legend_top + 32, labels[index], font_size=10, text_anchor="middle")
            )

    parts.append(
        _text(760, 92, "B. Events and case-days by province", font_size=15, font_weight="bold")
    )
    ordered = sorted(province_rows, key=lambda row: -int(row["canonical_events"]))
    maximum = max((int(row["canonical_events"]) for row in ordered), default=1)
    bar_left, bar_top, bar_width = 890, 120, 160
    for index, row in enumerate(ordered):
        y = bar_top + index * 56
        events = int(row["canonical_events"])
        cases = int(row["primary_case_days"])
        parts.append(
            _text(bar_left - 12, y + 12, row["province"], font_size=12, text_anchor="end")
        )
        parts.append(
            _rect(bar_left, y, bar_width * events / maximum, 15, fill="#3182BD", rx="2")
        )
        parts.append(
            _rect(bar_left, y + 18, bar_width * cases / maximum, 15, fill="#E6550D", rx="2")
        )
        parts.append(
            _text(
                bar_left + bar_width * events / maximum + 8,
                y + 12,
                f"{events} events",
                font_size=10,
            )
        )
        parts.append(
            _text(
                bar_left + bar_width * cases / maximum + 8,
                y + 30,
                f"{cases} primary case-days",
                font_size=10,
            )
        )
    parts.append(
        _text(
            50,
            height - 22,
            "District boundaries: Open Knowledge Nepal LocalBoundaries, 77 districts, WGS84.",
            font_size=11,
            fill="#555",
        )
    )
    return _document(width, height, parts)


def figure_distributions(outputs: Path) -> str:
    """Figure 3 -- seasonality and case-versus-control rainfall distributions."""

    months = _read(outputs / "inventory_month_summary.csv")
    distributions = _read(outputs / "rainfall_case_control_distributions.csv")
    width, height = 1180, 620
    parts = [
        _text(
            50,
            34,
            "Seasonality of reported events and rainfall in cases versus matched controls",
            font_size=20,
            font_weight="bold",
        ),
        _text(70, 82, "A. Reported events by calendar month", font_size=15, font_weight="bold"),
    ]
    left, top, plot_width, plot_height = 90, 104, 440, 360
    _axis(parts, left, top, plot_width, plot_height, "Month", "Canonical events")
    maximum = max((int(row["canonical_events"]) for row in months), default=1)
    slot = plot_width / 12
    for index, row in enumerate(months):
        value = int(row["canonical_events"])
        bar_height = plot_height * value / maximum
        x = left + index * slot + slot * 0.15
        colour = "#E6550D" if row["monsoon"].lower() == "true" else "#9ECAE1"
        parts.append(
            _rect(x, top + plot_height - bar_height, slot * 0.7, bar_height, fill=colour, rx="2")
        )
        parts.append(
            _text(
                x + slot * 0.35,
                top + plot_height + 18,
                index + 1,
                font_size=10,
                text_anchor="middle",
            )
        )
    parts.append(_rect(left + 12, top + 8, 14, 14, fill="#E6550D", rx="2"))
    parts.append(_text(left + 32, top + 20, "Monsoon (June-September)", font_size=11))
    parts.append(_rect(left + 12, top + 30, 14, 14, fill="#9ECAE1", rx="2"))
    parts.append(_text(left + 32, top + 42, "Rest of year", font_size=11))

    parts.append(
        _text(
            640,
            82,
            "B. Rainfall distribution, cases versus controls",
            font_size=15,
            font_weight="bold",
        )
    )
    panel_left, panel_top, panel_width, panel_height = 700, 104, 300, 360
    selected = [
        row
        for row in distributions
        if row["exposure"] == CONCURRENT and row["period"] == "all_years"
    ]
    windows = sorted({int(row["window_days"]) for row in selected})
    upper = max(
        (_float(row["p90_mm"]) for row in selected if math.isfinite(_float(row["p90_mm"]))),
        default=1.0,
    )
    _axis(
        parts,
        panel_left,
        panel_top,
        panel_width,
        panel_height,
        "Accumulated rainfall (mm)",
        "Accumulation window",
    )
    for tick in range(5):
        value = upper * tick / 4
        x = panel_left + panel_width * tick / 4
        parts.append(
            _text(
                x,
                panel_top + panel_height + 20,
                f"{value:.0f}",
                font_size=11,
                text_anchor="middle",
            )
        )
    row_height = panel_height / (len(windows) or 1)
    for index, window in enumerate(windows):
        base = panel_top + index * row_height + row_height / 2
        parts.append(
            _text(panel_left - 12, base + 4, f"R{window}", font_size=12, text_anchor="end")
        )
        for offset, group, colour in ((-14, "case", "#E6550D"), (6, "control", "#3182BD")):
            entry = next(
                (
                    row
                    for row in selected
                    if int(row["window_days"]) == window and row["group"] == group
                ),
                None,
            )
            if entry is None:
                continue
            def position(value: float) -> float:
                return panel_left + min(value / upper, 1.0) * panel_width

            p25, median, p75 = (
                position(_float(entry["p25_mm"])),
                position(_float(entry["median_mm"])),
                position(_float(entry["p75_mm"])),
            )
            p10, p90 = position(_float(entry["p10_mm"])), position(_float(entry["p90_mm"]))
            y = base + offset
            parts.append(_line(p10, y + 4, p90, y + 4, stroke=colour, stroke_width=1.6))
            parts.append(_rect(p25, y, max(p75 - p25, 1.0), 9, fill=colour, opacity="0.45", rx="2"))
            parts.append(_line(median, y - 2, median, y + 11, stroke=colour, stroke_width=2.6))
            parts.append(
                _text(
                    panel_left + panel_width + 8,
                    y + 9,
                    f"{group} median {_float(entry['median_mm']):.0f} mm",
                    font_size=9,
                    fill=colour,
                )
            )
    parts.append(
        _text(
            50,
            height - 22,
            "Boxes span the interquartile range with whiskers at the 10th and 90th percentiles; "
            "controls are matched on district, calendar month and year.",
            font_size=11,
            fill="#555",
        )
    )
    return _document(width, height, parts)


def figure_validation(outputs: Path) -> str:
    """Figure 4 -- held-out validation and the two exposure definitions."""

    rows = _read(outputs / "rainfall_resampled_validation.csv")
    sensitivity = _read(outputs / "rainfall_sensitivity_summary.csv")
    primary_test = {
        row["exposure"]: _float(row["test_auc"])
        for row in sensitivity
        if row["variant"] == PRIMARY_VARIANT
    }
    width, height = 1180, 620
    parts = [
        _text(
            50,
            34,
            "Held-out validation: one temporal split against the full year-to-year range",
            font_size=20,
            font_weight="bold",
        ),
        _text(
            50,
            56,
            "Concurrent windows include the reported event day; strictly antecedent windows end "
            "the day before it.",
            font_size=12,
            fill="#555",
        ),
    ]
    panels = (
        ("A. Leave-one-year-out", "leave_one_year_out", 90),
        ("B. Spatially held-out district folds", "spatial_holdout", 660),
    )
    for title, scheme, left in panels:
        parts.append(_text(left - 20, 96, title, font_size=15, font_weight="bold"))
        top, plot_width, plot_height = 120, 430, 380
        _axis(parts, left, top, plot_width, plot_height, "Held-out block", "AUC")
        low, high = 0.50, 0.80
        for tick in range(7):
            value = low + tick * (high - low) / 6
            y = top + plot_height - (value - low) / (high - low) * plot_height
            parts.append(_line(left, y, left + plot_width, y, stroke="#eee"))
            parts.append(_text(left - 10, y + 4, f"{value:.2f}", font_size=10, text_anchor="end"))
        folds = [row for row in rows if row["scheme"] == scheme]
        labels = list(dict.fromkeys(row["fold"] for row in folds))
        slot = plot_width / (len(labels) or 1)
        for exposure, colour in EXPOSURE_COLORS.items():
            series = [row for row in folds if row["exposure"] == exposure]
            points = []
            for row in series:
                index = labels.index(row["fold"])
                value = _float(row["auc"])
                if not math.isfinite(value):
                    continue
                x = left + index * slot + slot / 2
                y = top + plot_height - (value - low) / (high - low) * plot_height
                points.append((x, y))
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{colour}"/>')
            if points:
                path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
                parts.append(
                    f'<polyline points="{path}" fill="none" stroke="{colour}" '
                    'stroke-width="1.8" opacity="0.75"/>'
                )
        for index, label in enumerate(labels):
            x = left + index * slot + slot / 2
            short = label.replace("district_fold_", "F")
            parts.append(
                _text(x, top + plot_height + 18, short, font_size=10, text_anchor="middle")
            )
        for exposure, colour in EXPOSURE_COLORS.items():
            value = primary_test.get(exposure)
            if value is None or not math.isfinite(value):
                continue
            y = top + plot_height - (value - low) / (high - low) * plot_height
            parts.append(
                _line(
                    left,
                    y,
                    left + plot_width,
                    y,
                    stroke=colour,
                    stroke_width=1.4,
                    stroke_dasharray="6 4",
                )
            )
        legend_top = top + 8
        for index, (exposure, colour) in enumerate(EXPOSURE_COLORS.items()):
            y = legend_top + index * 20
            parts.append(_line(left + 12, y, left + 34, y, stroke=colour, stroke_width=3))
            name = "Concurrent" if exposure == CONCURRENT else "Strictly antecedent"
            parts.append(_text(left + 42, y + 4, name, font_size=11))
    parts.append(
        _text(
            50,
            height - 24,
            "Dashed lines mark the single prespecified temporal-test AUC for each exposure. "
            "A value near the top of the held-out spread is a favourable split, not a stronger "
            "result.",
            font_size=11,
            fill="#555",
        )
    )
    return _document(width, height, parts)


def run_rainfall_figures_stage(config: AppConfig) -> None:
    """Write every manuscript figure from the analysis outputs on disk."""

    root = config.config_path.parent
    settings = dict(config.raw.get("analysis", {}))
    outputs = config.resolve_path("outputs_dir")
    boundaries = root / str(
        settings.get("district_boundaries_path", "data/reference/nepal_districts_77.geojson")
    )
    written: list[Path] = []
    for name, svg in (
        ("rainfall_results_figure.svg", figure_roc(outputs)),
        ("inventory_map_figure.svg", figure_map(outputs, boundaries)),
        ("rainfall_distributions_figure.svg", figure_distributions(outputs)),
        ("rainfall_validation_figure.svg", figure_validation(outputs)),
    ):
        path = outputs / name
        path.write_text(svg, encoding="utf-8")
        written.append(path)
    for path in written:
        print(f"Wrote {path}")
