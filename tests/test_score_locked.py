"""Regression tests for the frozen locked-set scoring definition."""

from __future__ import annotations

from pathlib import Path

import pytest

from landslide_inventory.config import load_config
from landslide_inventory.db import connect_sqlite, initialize_sqlite
from landslide_inventory.validation.score_locked import (
    _predicted_headline,
    _truth_headline,
    _typing_snapshot_rows,
    score,
)


def _label(row_id: str, *, granularity: str = 'single') -> dict[str, str]:
    return {
        'row_id': row_id,
        'url': f'https://example.test/{row_id}',
        'is_landslide_event_true': 'yes',
        'in_nepal_true': 'yes',
        'hazard_type_true': 'landslide',
        'event_granularity_true': granularity,
        'district_true': 'Mugu',
        'date_true': '2022-10-10',
    }


def _prediction(
    row_id: str,
    *,
    headline: int,
    weight: float,
    decision: str = 'kept_class1',
) -> dict[str, str]:
    return {
        'row_id': row_id,
        'url': f'https://example.test/{row_id}',
        'stratum': f'{decision}|en',
        'pipeline_decision': decision,
        'inclusion_weight': str(weight),
        'headline_pred': str(headline),
        'district_pred': 'Mugu',
        'event_date_pred': '2022-10-10',
    }


@pytest.mark.parametrize('granularity', ['multi', 'roundup', 'not_applicable'])
def test_truth_headline_requires_single_granularity(granularity: str) -> None:
    assert _truth_headline(_label('row', granularity=granularity)) is False


def test_truth_headline_keeps_unclear_out_of_metrics() -> None:
    row = _label('row')
    row['event_granularity_true'] = 'unclear'
    assert _truth_headline(row) is None


def test_predicted_headline_requires_frozen_typed_value() -> None:
    assert _predicted_headline({'row_id': 'one', 'headline_pred': '1'}) is True
    assert _predicted_headline({'row_id': 'two', 'headline_pred': '0'}) is False
    assert _predicted_headline({'row_id': 'numeric-zero', 'headline_pred': 0}) is False
    with pytest.raises(ValueError, match='typed headline_pred'):
        _predicted_headline({'row_id': 'missing'})


def test_score_separates_headline_classification_from_extraction() -> None:
    labels = [
        _label('positive'),
        _label('multi', granularity='multi'),
        {
            **_label('negative', granularity='not_applicable'),
            'is_landslide_event_true': 'no',
            'in_nepal_true': '',
            'hazard_type_true': 'not_a_hazard',
        },
    ]
    predictions = {
        'positive': _prediction('positive', headline=1, weight=2, decision='kept_class2'),
        'multi': _prediction('multi', headline=1, weight=3),
        'negative': _prediction(
            'negative', headline=0, weight=4, decision='dropped_specificity'
        ),
    }

    report = score(labels, predictions, bootstrap_replicates=30)

    assert report['unweighted_confusion'] == {'tp': 1, 'fp': 1, 'fn': 0, 'tn': 1}
    assert report['weighted']['precision'] == pytest.approx(0.4)
    assert report['weighted']['recall'] == pytest.approx(1.0)
    assert report['weighted_ci95_stratified_bootstrap']['precision'] is not None
    district = report['extraction_among_true_headline_articles']['district']
    event_date = report['extraction_among_true_headline_articles']['event_date']
    assert district['weighted_exact_accuracy'] == pytest.approx(1.0)
    assert event_date['weighted_exact_accuracy'] == pytest.approx(1.0)
    assert district['reportable'] is False
    assert event_date['reportable'] is False


def test_typing_snapshot_uses_canonical_event_typing_rules(config_file: Path) -> None:
    config = load_config(config_file)
    initialize_sqlite(config.sqlite_path)
    url = 'https://example.test/road'
    with connect_sqlite(config.sqlite_path) as connection:
        connection.execute(
            """
            INSERT INTO raw_articles (url, source, title, text)
            VALUES (?, 'test', 'Landslide blocks highway',
                    'A landslide blocked traffic along the highway.')
            """,
            (url,),
        )
        connection.commit()

    rows, changed = _typing_snapshot_rows(
        config,
        [
            {
                'row_id': 'v2-0001',
                'url': url,
                'pipeline_decision': 'kept_class2',
            }
        ],
    )

    assert changed is True
    assert rows[0]['event_type_pred'] == 'road_obstruction'
    assert rows[0]['hazard_type_pred'] == 'landslide'
    assert rows[0]['event_granularity_pred'] == 'single'
    assert rows[0]['article_role_pred'] == 'first_report'
    assert rows[0]['headline_pred'] == 1
