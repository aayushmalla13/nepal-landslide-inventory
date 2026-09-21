"""Shared classification rules for audit-driven canonical-event corrections."""

from __future__ import annotations

ACTION_HYPOTHESES = {
    "exclude_false_event": "scope_or_event_specificity",
    "review_event_existence": "scope_or_event_specificity",
    "split_or_exclude_aggregate": "event_granularity",
    "review_event_granularity": "event_granularity",
    "correct_district": "location_role_resolution",
    "review_district": "location_role_resolution",
    "correct_date": "event_date_resolution",
    "review_date": "event_date_resolution",
    "correct_municipality": "location_role_resolution",
    "review_municipality": "location_role_resolution",
    "correct_event_type": "event_type_classification",
    "review_event_type": "event_type_classification",
    "correct_hazard_type": "hazard_type_classification",
    "review_hazard_type": "hazard_type_classification",
    "correct_deaths": "casualty_extraction",
    "clear_deaths": "casualty_extraction",
    "review_deaths": "casualty_extraction",
    "recluster_articles": "deduplication",
    "review_duplicate_merge": "deduplication",
}
ARTICLE_MAPPING_ACTIONS = {
    "exclude_false_event",
    "split_or_exclude_aggregate",
    "review_event_granularity",
    "recluster_articles",
    "review_duplicate_merge",
}
TRUE_VALUE_REVIEW_ACTIONS = {
    "review_event_existence",
    "correct_district",
    "review_district",
    "correct_date",
    "review_date",
    "correct_municipality",
    "review_municipality",
    "review_event_type",
    "review_hazard_type",
    "review_deaths",
}
IDENTITY_ACTIONS = {
    "exclude_false_event",
    "review_event_existence",
    "split_or_exclude_aggregate",
    "review_event_granularity",
    "correct_district",
    "review_district",
    "correct_date",
    "review_date",
    "recluster_articles",
    "review_duplicate_merge",
}


def deaths_mismatch(claimed: str, true: str) -> bool:
    """Return whether a reviewed death value differs from the inventory claim."""
    claimed = claimed.strip()
    true = true.strip().lower()
    if true in {"", "unclear"}:
        return False
    if true == "not_reported":
        return bool(claimed)
    return not claimed or int(claimed) != int(true)


def classify(row: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """Translate one completed audit row into ordered remediation actions."""
    actions: list[str] = []
    proposed = {"event_type": "", "hazard_type": "", "deaths": ""}
    event = row["event_really_happened"].strip().lower()
    if event == "no":
        return ["exclude_false_event"], proposed
    if event == "unclear":
        return ["review_event_existence"], proposed

    binary_actions = (
        ("one_physical_event", "split_or_exclude_aggregate", "review_event_granularity"),
        ("district_correct", "correct_district", "review_district"),
        ("date_correct", "correct_date", "review_date"),
        ("municipality_correct", "correct_municipality", "review_municipality"),
    )
    for field, no_action, unclear_action in binary_actions:
        value = row[field].strip().lower()
        if value == "no":
            actions.append(no_action)
        elif value == "unclear":
            actions.append(unclear_action)

    for truth, claim, correct, review, proposed_key in (
        (
            "event_type_true",
            "claimed_event_type",
            "correct_event_type",
            "review_event_type",
            "event_type",
        ),
        (
            "hazard_type_true",
            "claimed_hazard_type",
            "correct_hazard_type",
            "review_hazard_type",
            "hazard_type",
        ),
    ):
        value = row[truth].strip().lower()
        if value == "unclear":
            actions.append(review)
        elif value and value != row[claim].strip().lower():
            actions.append(correct)
            proposed[proposed_key] = value

    deaths = row["deaths_true"].strip().lower()
    if deaths == "unclear":
        actions.append("review_deaths")
    elif deaths_mismatch(row["claimed_deaths"], deaths):
        actions.append("clear_deaths" if deaths == "not_reported" else "correct_deaths")
        proposed["deaths"] = "" if deaths == "not_reported" else deaths

    duplicate = row["duplicate_merge_correct"].strip().lower()
    if duplicate == "no":
        actions.append("recluster_articles")
    elif duplicate == "unclear":
        actions.append("review_duplicate_merge")
    return actions, proposed


def readiness(actions: list[str]) -> str:
    """Assign the earliest safe manual-correction batch."""
    if any(action in ARTICLE_MAPPING_ACTIONS for action in actions):
        return "requires_article_mapping"
    if any(action in TRUE_VALUE_REVIEW_ACTIONS for action in actions):
        return "requires_true_value_review"
    return "structured_attribute_candidate"


def priority(actions: list[str]) -> str:
    """Prioritize identity and linkage errors ahead of attribute-only errors."""
    if any(action in IDENTITY_ACTIONS for action in actions):
        return "P0_identity_or_linkage"
    if any(action.startswith("review_") for action in actions):
        return "P2_uncertain"
    return "P1_attribute"


def certainty(actions: list[str]) -> str:
    """Describe whether a queue row has confirmed, uncertain, or mixed actions."""
    has_review = any(action.startswith("review_") for action in actions)
    has_confirmed = any(not action.startswith("review_") for action in actions)
    if has_review and has_confirmed:
        return "mixed_confirmed_and_review"
    if has_review:
        return "requires_review"
    return "confirmed"
