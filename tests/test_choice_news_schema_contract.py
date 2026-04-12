from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.schemas.choice_news import (
    ChoiceNewsGroup,
    ChoiceNewsTopic,
    ChoiceNewsTopicsAsset,
)


def test_choice_news_topic_extra_forbidden():
    with pytest.raises(ValidationError):
        ChoiceNewsTopic(topic_code="T1", topic_name="n1", unexpected="x")  # type: ignore[call-arg]


def test_choice_news_group_defaults():
    group = ChoiceNewsGroup(
        group_id="g1",
        group_name="G",
        topics=[ChoiceNewsTopic(topic_code="T1", topic_name="n1")],
    )
    assert group.is_core is False
    assert group.tags == []


def test_choice_news_nested_topics_validation_rejects_invalid_topic():
    with pytest.raises(ValidationError):
        ChoiceNewsGroup(
            group_id="g1",
            group_name="G",
            topics=[{"topic_code": "T1"}],  # missing topic_name
        )


def test_choice_news_topics_asset_accepts_datetime_generated_at():
    dt = datetime(2026, 4, 10, 18, 10, tzinfo=timezone.utc)
    asset = ChoiceNewsTopicsAsset(
        catalog_version="v1",
        vendor_name="choice",
        generated_at=dt,
        generated_from="test",
        subscription_mode="cnq",
        content_type="sectornews",
        callback_name="cb",
        groups=[
            ChoiceNewsGroup(
                group_id="g1",
                group_name="G",
                topics=[ChoiceNewsTopic(topic_code="T1", topic_name="n1")],
            )
        ],
    )
    assert asset.generated_at is dt


def test_choice_news_model_dump_preserves_groups_topics_structure():
    asset = ChoiceNewsTopicsAsset(
        catalog_version="v1",
        vendor_name="choice",
        generated_at=datetime(2026, 4, 10, 18, 10, tzinfo=timezone.utc),
        generated_from="test",
        subscription_mode="cnq",
        content_type="sectornews",
        callback_name="cb",
        groups=[
            ChoiceNewsGroup(
                group_id="g1",
                group_name="G",
                is_core=True,
                tags=["a"],
                topics=[
                    ChoiceNewsTopic(topic_code="C1", topic_name="N1"),
                    ChoiceNewsTopic(topic_code="C2", topic_name="N2"),
                ],
            )
        ],
    )
    dumped = asset.model_dump(mode="python")
    assert dumped["groups"][0]["group_id"] == "g1"
    assert [t["topic_code"] for t in dumped["groups"][0]["topics"]] == ["C1", "C2"]


def test_choice_news_missing_required_fields_raise():
    with pytest.raises(ValidationError):
        ChoiceNewsTopicsAsset()  # type: ignore[call-arg]
