"""Tests for canonical cluster-level event typing."""

from __future__ import annotations

from landslide_inventory.unify.event_typing import (
    EVENT_TYPE_LANDSLIDE,
    EXTRACTION_BASIS_FULL,
    HAZARD_DEBRIS_FLOW,
    HAZARD_LANDSLIDE,
    HAZARD_ROCKFALL,
    EventTyping,
)
from landslide_inventory.unify.event_typing_stage import refine_hazard_from_members


def generic_landslide() -> EventTyping:
    return EventTyping(
        event_type=EVENT_TYPE_LANDSLIDE,
        extraction_basis=EXTRACTION_BASIS_FULL,
        reason='default_landslide',
        hazard_type=HAZARD_LANDSLIDE,
    )


def test_cluster_member_can_refine_generic_representative_hazard() -> None:
    refined = refine_hazard_from_members(
        generic_landslide(), {HAZARD_LANDSLIDE, HAZARD_DEBRIS_FLOW}
    )
    assert refined.hazard_type == HAZARD_DEBRIS_FLOW


def test_conflicting_specific_member_hazards_do_not_override_representative() -> None:
    refined = refine_hazard_from_members(
        generic_landslide(), {HAZARD_DEBRIS_FLOW, HAZARD_ROCKFALL}
    )
    assert refined.hazard_type == HAZARD_LANDSLIDE


def test_specific_representative_hazard_is_not_replaced() -> None:
    representative = replace_hazard(generic_landslide(), HAZARD_ROCKFALL)
    refined = refine_hazard_from_members(representative, {HAZARD_DEBRIS_FLOW})
    assert refined.hazard_type == HAZARD_ROCKFALL


def replace_hazard(typing: EventTyping, hazard: str) -> EventTyping:
    return EventTyping(
        event_type=typing.event_type,
        extraction_basis=typing.extraction_basis,
        reason=typing.reason,
        hazard_type=hazard,
        event_granularity=typing.event_granularity,
        article_role=typing.article_role,
    )
