"""Тесты FIFO-очереди BiNiBit 3×3."""

from __future__ import annotations

from pathlib import Path

import pytest

from database import Database
from referral_manager import ReferralManager


@pytest.fixture()
def manager(tmp_path: Path) -> ReferralManager:
    database = Database(tmp_path / "test.db")
    database.initialize()
    return ReferralManager(database)


def create_user(manager: ReferralManager, telegram_id: int):
    return manager.create_or_get_user(telegram_id, f"user{telegram_id}", "Тест")


def test_fifo_order_and_limit_of_three(manager: ReferralManager) -> None:
    first = manager.add_admin_referral_link("https://binibit.com/ref/first")
    second = manager.add_admin_referral_link("https://binibit.com/ref/second")

    issued = [
        manager.get_referral_link(create_user(manager, 100 + index)["id"])
        for index in range(4)
    ]

    assert [item.url for item in issued if item] == [
        first.url,
        first.url,
        first.url,
        second.url,
    ]
    assert issued[2] is not None
    assert issued[2].status == "limit_reached"
    assert issued[3] is not None
    assert issued[3].used_count == 1


def test_user_link_is_inactive_before_review(manager: ReferralManager) -> None:
    user = create_user(manager, 1)
    link = manager.submit_referral_link(user["id"], "https://binibit.com/ref/new")

    assert link.status == "pending_staking"
    assert manager.get_referral_link(create_user(manager, 2)["id"]) is None


def test_approval_activates_user_link(manager: ReferralManager) -> None:
    user = create_user(manager, 1)
    pending_link = manager.submit_referral_link(
        user["id"], "https://binibit.com/ref/approved"
    )
    review = manager.create_staking_review(user["id"], "telegram-file-id")

    manager.decide_review(review["id"], reviewer_telegram_id=999, approved=True)

    issued = manager.get_referral_link(create_user(manager, 2)["id"])
    assert issued is not None
    assert issued.id == pending_link.id
    assert issued.url == pending_link.url
    assert issued.used_count == 1


def test_rejection_keeps_link_out_of_queue(manager: ReferralManager) -> None:
    user = create_user(manager, 1)
    manager.submit_referral_link(user["id"], "https://binibit.com/ref/rejected")
    review = manager.create_staking_review(user["id"], "telegram-file-id")

    manager.decide_review(review["id"], reviewer_telegram_id=999, approved=False)

    assert manager.get_referral_link(create_user(manager, 2)["id"]) is None


def test_get_user_referral_link_returns_saved_personal_link(
    manager: ReferralManager,
) -> None:
    user = create_user(manager, 1)
    manager.submit_referral_link(user["id"], "https://binibit.com/ref/personal")

    link = manager.get_user_referral_link(user["id"])

    assert link is not None
    assert link.url == "https://binibit.com/ref/personal"
    assert link.owner_user_id == user["id"]


def test_get_previously_issued_link_returns_last_issued_starter_link(
    manager: ReferralManager,
) -> None:
    first = manager.add_admin_referral_link("https://binibit.com/ref/first")
    manager.add_admin_referral_link("https://binibit.com/ref/second")
    user = create_user(manager, 77)

    issued = manager.get_referral_link(user["id"])
    previous = manager.get_previously_issued_link(user["id"])

    assert issued is not None
    assert previous is not None
    assert previous.id == issued.id
    assert previous.url == first.url


def test_get_curator_name_for_link_returns_owner_username(
    manager: ReferralManager,
) -> None:
    curator = create_user(manager, 1)
    link = manager.submit_referral_link(curator["id"], "https://binibit.com/ref/curator")

    curator_name = manager.get_curator_name_for_link(link)

    assert curator_name == "@user1"
