"""Tests for validation-stage sampling and scoring helpers."""

from __future__ import annotations

from pathlib import Path

from landslide_inventory.db import initialize_sqlite
from landslide_inventory.validation.audit_canonical import CanonicalAuditRow, sample_canonical_rows
from landslide_inventory.validation.manual_pack import ManualPackRow, build_manual_pack_sample, row_to_dict
from landslide_inventory.validation.manual_audit import build_manual_audit
from landslide_inventory.validation.manual_refresh import refresh_manual_rows
from landslide_inventory.validation.manual_score import compute_manual_metrics


def test_audit_canonical_outputs_exact_sample_size_when_available() -> None:
    rows = [
        CanonicalAuditRow(
            event_id=f'event-{index:02d}',
            cluster_id=f'cluster-{index:02d}',
            event_date_ad='2020-07-01',
            district='Dhading',
            municipality=None,
            ward=None,
            deaths=1,
            missing=None,
            injured=None,
            trigger='rainfall',
            sources_count=1,
            urls_count=1,
            representative_title=f'Title {index}',
            representative_url=f'https://example.com/{index}',
            specificity_reason='event_specific',
            specificity_score=0.9,
            location_consistency_status='consistent',
            in_nepal=1,
            scope_reason='district_match',
        )
        for index in range(40)
    ]
    sample = sample_canonical_rows(rows, 30, 42)
    assert len(sample) == 30


def test_audit_canonical_sampling_is_deterministic() -> None:
    rows = [
        CanonicalAuditRow(
            event_id=f'event-{index:02d}',
            cluster_id=f'cluster-{index:02d}',
            event_date_ad='2020-07-01',
            district='Dhading',
            municipality=None,
            ward=None,
            deaths=1,
            missing=None,
            injured=None,
            trigger='rainfall',
            sources_count=1,
            urls_count=1,
            representative_title=f'Title {index}',
            representative_url=f'https://example.com/{index}',
            specificity_reason='event_specific',
            specificity_score=0.9,
            location_consistency_status='consistent',
            in_nepal=1,
            scope_reason='district_match',
        )
        for index in range(40)
    ]
    first = [row.event_id for row in sample_canonical_rows(rows, 30, 99)]
    second = [row.event_id for row in sample_canonical_rows(rows, 30, 99)]
    assert first == second


def test_manual_pack_builds_balanced_language_sample() -> None:
    rows = []
    for year in range(2015, 2025):
        rows.append(ManualPackRow(f'https://en/{year}', 'src', str(year), 'en', f'EN {year}', 'snippet', 1, 'Dhading', None, None, f'{year}-07-01', 1, None, None, 'rainfall', 'event_specific', 0.9))
        rows.append(ManualPackRow(f'https://np/{year}', 'src', str(year), 'np', f'NP {year}', 'snippet', 1, 'Dhading', None, None, f'{year}-07-01', 1, None, None, 'rainfall', 'event_specific', 0.9))
    sample = build_manual_pack_sample(rows, 5, 5, 42)
    assert len(sample) == 10
    assert sum(1 for row in sample if row.route_lang == 'en') == 5
    assert sum(1 for row in sample if row.route_lang == 'np') == 5


def test_manual_score_computes_metrics() -> None:
    rows = [
        {
            'class_pred': '1', 'class_true': '1',
            'district_pred': 'Dhading', 'district_true': 'Dhading',
            'municipality_pred': 'Nilkantha Municipality', 'municipality_true': 'Nilkantha Municipality',
            'event_date_pred': '2024-07-16', 'date_true': '2024-07-16',
            'deaths_pred': '3', 'deaths_true': '3',
            'trigger_pred': 'rainfall', 'trigger_true': 'rainfall',
        },
        {
            'class_pred': '2', 'class_true': '1',
            'district_pred': '', 'district_true': 'Sindhupalchok',
            'municipality_pred': '', 'municipality_true': '',
            'event_date_pred': '', 'date_true': '2024-07-17',
            'deaths_pred': '4', 'deaths_true': '5',
            'trigger_pred': 'unknown', 'trigger_true': 'rainfall',
        },
    ]
    metrics = compute_manual_metrics(rows)
    assert metrics['labeled_rows'] == 2
    assert metrics['classification']['macro']['f1'] is not None
    assert metrics['district']['labeled_rows'] == 2
    assert metrics['deaths']['within_one_rate'] == 1.0
    assert metrics['trigger']['confusion_matrix']['rainfall']


def test_manual_score_normalizes_location_fields() -> None:
    rows = [
        {
            'class_pred': '2', 'class_true': '2',
            'district_pred': 'Sindhupalchowk', 'district_true': 'Sindhupalchok',
            'municipality_pred': 'Ichchakamana Rural Municipality', 'municipality_true': 'Ichhakamana Rural Municipality',
            'event_date_pred': '2024-07-16', 'date_true': '2024-07-16',
            'deaths_pred': '0', 'deaths_true': '0',
            'trigger_pred': 'rainfall', 'trigger_true': 'rainfall',
        },
    ]
    metrics = compute_manual_metrics(rows)
    assert metrics['district']['accuracy'] == 1.0
    assert metrics['municipality']['accuracy'] == 1.0


def test_manual_score_treats_blank_prediction_as_zero_deaths_for_no_fatality_rows() -> None:
    rows = [
        {
            'class_pred': '2', 'class_true': '2',
            'district_pred': 'Chitwan', 'district_true': 'Chitwan',
            'municipality_pred': '', 'municipality_true': '',
            'event_date_pred': '2024-07-16', 'date_true': '2024-07-16',
            'deaths_pred': '', 'deaths_true': '0',
            'trigger_pred': 'rainfall', 'trigger_true': 'rainfall',
        },
    ]
    metrics = compute_manual_metrics(rows)
    assert metrics['deaths']['exact_match_rate'] == 1.0
    assert metrics['deaths']['within_one_rate'] == 1.0
    assert metrics['deaths']['missing_rate'] == 0.0


def test_manual_pack_normalizes_multiline_review_fields() -> None:
    row = ManualPackRow(
        'https://np/example',
        'src',
        '2020',
        'np',
        'Line one\nline two',
        'First line\nSecond line\tThird',
        1,
        'Dhading',
        None,
        None,
        '2020-07-01',
        1,
        None,
        None,
        'rainfall',
        'event_specific',
        0.9,
    )
    exported = row_to_dict(row)
    assert exported['title'] == 'Line one line two'
    assert '\n' not in exported['snippet']


def test_manual_pack_replaces_code_like_snippets_with_clean_title_fallback() -> None:
    row = ManualPackRow(
        'https://example.com/himalayan-times',
        'himalayan-times',
        '2019',
        'en',
        "Six of a family buried to death in Rolpa landslide - The Himalayan Times - Nepal's No.1 English Daily Newspaper",
        '","#"===e.firstChild.getAttribute("href")})||fe("type|href|height|width",function(e,t,n){if(!n)return e.getAttribute(t)}',
        1,
        'Rolpa',
        None,
        None,
        '2019-09-14',
        None,
        None,
        None,
        'unknown',
        'event_specific',
        1.0,
    )
    exported = row_to_dict(row)
    assert exported['snippet'] == 'Six of a family buried to death in Rolpa landslide'


def test_manual_audit_reports_unlabeled_rows_and_prioritizes_class_one_mismatches() -> None:
    rows = [
        {
            'url': 'https://example.com/a',
            'source': 'setopati',
            'title': 'Fatal road event',
            'class_pred': '2', 'class_true': '1',
            'district_pred': 'Sindhupalchowk', 'district_true': 'Sindhupalchok',
            'municipality_pred': '', 'municipality_true': '',
            'event_date_pred': '2024-07-16', 'date_true': '2024-07-16',
            'deaths_pred': '0', 'deaths_true': '2',
            'trigger_pred': 'rainfall', 'trigger_true': 'rainfall',
        },
        {
            'url': 'https://example.com/b',
            'source': 'onlinekhabar',
            'title': 'Still unlabeled',
            'class_pred': '3', 'class_true': '',
            'district_pred': '', 'district_true': '',
            'municipality_pred': '', 'municipality_true': '',
            'event_date_pred': '', 'date_true': '',
            'deaths_pred': '', 'deaths_true': '',
            'trigger_pred': '', 'trigger_true': '',
        },
    ]
    audit = build_manual_audit(rows)
    assert audit['unlabeled_rows'] == 1
    assert audit['priority_rows'][0]['priority'] == 3
    assert 'class 2 -> 1' in audit['priority_rows'][0]['issues']
    assert audit['mismatch_summary']['district']['mismatch_rows'] == 0


def test_manual_audit_ignores_secondary_field_mismatches_for_class_three_truth() -> None:
    rows = [
        {
            'url': 'https://example.com/class3',
            'source': 'myrepublica',
            'title': 'Foreign roundup',
            'class_pred': '3', 'class_true': '3',
            'district_pred': '', 'district_true': '',
            'municipality_pred': '', 'municipality_true': '',
            'event_date_pred': '', 'date_true': '',
            'deaths_pred': '', 'deaths_true': '',
            'trigger_pred': 'unknown', 'trigger_true': 'rainfall',
        },
        {
            'url': 'https://example.com/class-mismatch',
            'source': 'myrepublica',
            'title': 'Needs downgrade',
            'class_pred': '2', 'class_true': '3',
            'district_pred': '', 'district_true': '',
            'municipality_pred': '', 'municipality_true': '',
            'event_date_pred': '', 'date_true': '',
            'deaths_pred': '', 'deaths_true': '',
            'trigger_pred': 'unknown', 'trigger_true': 'rainfall',
        },
    ]
    audit = build_manual_audit(rows)
    assert audit['mismatch_summary']['trigger']['labeled_rows'] == 0
    assert audit['mismatch_summary']['trigger']['mismatch_rows'] == 0
    assert len(audit['priority_rows']) == 1
    assert audit['priority_rows'][0]['issues'] == ['class 2 -> 3']


def test_manual_refresh_updates_prediction_fields_from_article_events(tmp_path) -> None:
    database_path = tmp_path / 'manual_refresh.sqlite'
    initialize_sqlite(database_path)

    import sqlite3

    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        INSERT INTO article_events (
            extracted_event_id, article_url, event_class, event_payload,
            url, source, title, route_lang, class, event_date_ad,
            district, municipality, ward, deaths, missing, injured, trigger,
            specificity_reason, specificity_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            'event-1', 'https://example.com/article', 1, '{}',
            'https://example.com/article', 'myrepublica', 'Updated title', 'en', 1, '2022-06-01',
            'Sankhuwasabha', 'Chainpur Municipality', '1', 2, 0, 5, 'rainfall',
            'event_specific', 0.95,
        ),
    )
    connection.commit()
    connection.close()

    rows = [{
        'url': 'https://example.com/article',
        'source': 'myrepublica',
        'year': '2024',
        'route_lang': 'en',
        'title': 'Original title',
        'snippet': 'Original snippet',
        'class_pred': '2',
        'district_pred': '',
        'municipality_pred': '',
        'ward_pred': '',
        'event_date_pred': '',
        'deaths_pred': '',
        'missing_pred': '',
        'injured_pred': '',
        'trigger_pred': '',
        'specificity_reason': '',
        'specificity_score': '',
        'class_true': '1',
        'district_true': 'Sankhuwasabha',
        'municipality_true': 'Chainpur Municipality',
        'date_true': '2022-06-01',
        'deaths_true': '2',
        'trigger_true': 'rainfall',
        'notes': '',
    }]

    refreshed = refresh_manual_rows(database_path, rows)
    assert refreshed[0]['class_pred'] == '1'
    assert refreshed[0]['district_pred'] == 'Sankhuwasabha'
    assert refreshed[0]['municipality_pred'] == 'Chainpur Municipality'
    assert refreshed[0]['event_date_pred'] == '2022-06-01'
    assert refreshed[0]['deaths_pred'] == '2'
    assert refreshed[0]['injured_pred'] == '5'
    assert refreshed[0]['trigger_pred'] == 'rainfall'
    assert refreshed[0]['title'] == 'Updated title'
    assert refreshed[0]['year'] == '2022'


def test_manual_refresh_falls_back_to_source_and_title_when_url_malformed(tmp_path) -> None:
    database_path = tmp_path / 'manual_refresh_title_lookup.sqlite'
    initialize_sqlite(database_path)

    import sqlite3

    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        INSERT INTO article_events (
            extracted_event_id, article_url, event_class, event_payload,
            url, source, title, route_lang, class, event_date_ad,
            district, municipality, ward, deaths, missing, injured, trigger,
            specificity_reason, specificity_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            'event-title-lookup', 'https://example.com/china-story', 3, '{}',
            'https://example.com/china-story', 'myrepublica',
            '32 people missing in China landslides following typhoon - myRepublica - The New York Times Partner, Latest news of Nepal in English, Latest News Articles | Republica',
            'en', 3, None, None, None, None, None, None, None, 'rainfall',
            'out_of_country', 0.2,
        ),
    )
    connection.commit()
    connection.close()

    rows = [{
        'url': '32 people missing in China landslides following typhoon - myRepublica',
        'source': 'myrepublica',
        'year': '2024',
        'route_lang': 'en',
        'title': '32 people missing in China landslides following typhoon - myRepublica - The New York Times Partner, Latest news of Nepal in English, Latest News Articles | Republica',
        'snippet': 'Original snippet',
        'class_pred': '2',
        'district_pred': '',
        'municipality_pred': '',
        'ward_pred': '',
        'event_date_pred': '',
        'deaths_pred': '',
        'missing_pred': '',
        'injured_pred': '',
        'trigger_pred': '',
        'specificity_reason': '',
        'specificity_score': '',
        'class_true': '3',
        'district_true': '',
        'municipality_true': '',
        'date_true': '',
        'deaths_true': '',
        'trigger_true': 'rainfall',
        'notes': '',
    }]

    refreshed = refresh_manual_rows(database_path, rows)
    assert refreshed[0]['class_pred'] == '3'
    assert refreshed[0]['trigger_pred'] == 'rainfall'
    assert refreshed[0]['specificity_reason'] == 'out_of_country'


def test_manual_refresh_normalizes_display_aliases_for_locations(tmp_path) -> None:
    database_path = tmp_path / 'manual_refresh_aliases.sqlite'
    initialize_sqlite(database_path)

    import sqlite3

    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        INSERT INTO article_events (
            extracted_event_id, article_url, event_class, event_payload,
            url, source, title, route_lang, class, event_date_ad,
            district, municipality, ward, deaths, missing, injured, trigger,
            specificity_reason, specificity_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            'event-2', 'https://example.com/alias-article', 2, '{}',
            'https://example.com/alias-article', 'myrepublica', 'Alias title', 'en', 2, '2024-08-13',
            'Nawalpur', 'Ichhakamana Rural Municipality', '', None, None, None, 'rainfall',
            'event_specific', 0.9,
        ),
    )
    connection.commit()
    connection.close()

    rows = [{
        'url': 'https://example.com/alias-article',
        'source': 'myrepublica',
        'year': '2024',
        'route_lang': 'en',
        'title': 'Original title',
        'snippet': 'Original snippet',
        'class_pred': '',
        'district_pred': '',
        'municipality_pred': '',
        'ward_pred': '',
        'event_date_pred': '',
        'deaths_pred': '',
        'missing_pred': '',
        'injured_pred': '',
        'trigger_pred': '',
        'specificity_reason': '',
        'specificity_score': '',
        'class_true': '2',
        'district_true': 'Nawalparasi East',
        'municipality_true': 'Ichchhakamana Rural Municipality',
        'date_true': '2024-08-13',
        'deaths_true': '',
        'trigger_true': 'rainfall',
        'notes': '',
    }]

    refreshed = refresh_manual_rows(database_path, rows)
    assert refreshed[0]['district_pred'] == 'Nawalpur'
    assert refreshed[0]['district_true'] == 'Nawalpur'
    assert refreshed[0]['municipality_pred'] == 'Ichhakamana Rural Municipality'
    assert refreshed[0]['municipality_true'] == 'Ichhakamana Rural Municipality'


def test_manual_audit_prefers_refreshed_file_when_available(tmp_path) -> None:
    from landslide_inventory.validation.manual_audit import run_manual_audit_stage
    from landslide_inventory.config import load_config

    # Derive the repo root from this file's location. It was previously
    # hardcoded to one machine's absolute path, so the test failed for anyone
    # who cloned the repo anywhere else -- including on the same machine after
    # the project moved.
    project_root = Path(__file__).resolve().parents[1]
    config_path = tmp_path / 'config.yaml'
    outputs = tmp_path / 'outputs'
    outputs.mkdir()
    config_text = (project_root / 'config.yaml').read_text(encoding='utf-8')
    config_text = config_text.replace('outputs_dir: data/outputs', f'outputs_dir: {outputs}')
    config_path.write_text(config_text, encoding='utf-8')
    (outputs / 'manual_verification_sample.csv').write_text(
        'url,source,title,class_pred,class_true\nhttps://a,src,A,2,1\n', encoding='utf-8'
    )
    (outputs / 'manual_verification_sample_refreshed.csv').write_text(
        'url,source,title,class_pred,class_true\nhttps://a,src,A,1,1\n', encoding='utf-8'
    )
    config = load_config(config_path)
    run_manual_audit_stage(config)
    report = (outputs / 'manual_audit.json').read_text(encoding='utf-8')
    assert '"mismatch_rows": 0' in report
