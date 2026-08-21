"""Бизнес-логика очереди 3×3 и ручной модерации ссылок."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from random import SystemRandom
from typing import Iterable

from database import Database

MAX_REFERRALS_PER_LINK = 3
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@dataclass(frozen=True)
class ReferralLink:
    """Данные реферальной ссылки."""

    id: int
    url: str
    used_count: int
    max_limit: int
    status: str
    owner_user_id: int | None = None


class ReferralManager:
    """Управляет пользователями, FIFO-очередью и заявками на проверку."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create_or_get_user(
        self, telegram_id: int, username: str | None, full_name: str
    ) -> sqlite3.Row:
        """Возвращает пользователя, создавая уникальный код при первом входе."""
        with self.database.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE users
                    SET username = ?, full_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE telegram_id = ?
                    """,
                    (username, full_name, telegram_id),
                )
                return connection.execute(
                    "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
                ).fetchone()

            for _ in range(20):
                verification_code = self._generate_code()
                try:
                    cursor = connection.execute(
                        """
                        INSERT INTO users (telegram_id, username, full_name, verification_code)
                        VALUES (?, ?, ?, ?)
                        """,
                        (telegram_id, username, full_name, verification_code),
                    )
                    user_id = cursor.lastrowid
                    self._record_event(connection, user_id, "user_created")
                    return connection.execute(
                        "SELECT * FROM users WHERE id = ?", (user_id,)
                    ).fetchone()
                except sqlite3.IntegrityError:
                    continue

        raise RuntimeError("Не удалось сгенерировать уникальный код пользователя.")

    def set_step(self, user_id: int, step: str) -> None:
        """Сохраняет текущий этап пользователя."""
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE users
                SET current_step = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (step, user_id),
            )
            self._record_event(connection, user_id, f"step:{step}")

    def submit_referral_link(self, user_id: int, url: str) -> ReferralLink:
        """Сохраняет ссылку пользователя в ожидании стейкинга."""
        normalized_url = self._normalize_url(url)
        with self.database.connect() as connection:
            user = connection.execute(
                "SELECT verification_code FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if user is None:
                raise ValueError("Пользователь не найден.")

            existing = connection.execute(
                "SELECT * FROM referral_links WHERE owner_user_id = ?", (user_id,)
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE referral_links
                    SET url = ?, verification_code = ?, status = 'pending_staking'
                    WHERE id = ?
                    """,
                    (normalized_url, user["verification_code"], existing["id"]),
                )
                link_id = existing["id"]
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO referral_links (
                        owner_user_id, verification_code, url, max_limit, status
                    )
                    VALUES (?, ?, ?, ?, 'pending_staking')
                    """,
                    (
                        user_id,
                        user["verification_code"],
                        normalized_url,
                        MAX_REFERRALS_PER_LINK,
                    ),
                )
                link_id = cursor.lastrowid

            connection.execute(
                """
                UPDATE users
                SET current_step = 'pending_staking', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (user_id,),
            )
            self._record_event(connection, user_id, "referral_link_submitted", normalized_url)
            row = connection.execute(
                "SELECT * FROM referral_links WHERE id = ?", (link_id,)
            ).fetchone()

        return self._to_referral_link(row)

    def get_referral_link(self, recipient_user_id: int) -> ReferralLink | None:
        """Атомарно выдаёт первую доступную ссылку FIFO и увеличивает её счётчик."""
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT *
                FROM referral_links
                WHERE status = 'active' AND used_count < max_limit
                ORDER BY activated_at ASC, id ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                self._record_event(connection, recipient_user_id, "referral_link_unavailable")
                return None

            new_count = row["used_count"] + 1
            new_status = (
                "limit_reached" if new_count >= row["max_limit"] else "active"
            )
            connection.execute(
                """
                UPDATE referral_links
                SET used_count = ?, status = ?
                WHERE id = ?
                """,
                (new_count, new_status, row["id"]),
            )
            self._record_event(
                connection,
                recipient_user_id,
                "referral_link_issued",
                f"link_id={row['id']}",
            )
            return ReferralLink(
                id=row["id"],
                url=row["url"],
                used_count=new_count,
                max_limit=row["max_limit"],
                status=new_status,
                owner_user_id=row["owner_user_id"],
            )

    def get_user_referral_link(self, user_id: int) -> ReferralLink | None:
        """Возвращает последнюю сохранённую личную ссылку пользователя."""
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM referral_links
                WHERE owner_user_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return self._to_referral_link(row) if row is not None else None

    def get_previously_issued_link(
        self, recipient_user_id: int
    ) -> ReferralLink | None:
        """Возвращает стартовую ссылку, ранее выданную пользователю."""
        with self.database.connect() as connection:
            event = connection.execute(
                """
                SELECT details
                FROM events
                WHERE user_id = ? AND event_name = 'referral_link_issued'
                ORDER BY id DESC
                LIMIT 1
                """,
                (recipient_user_id,),
            ).fetchone()
            if event is None or not event["details"]:
                return None

            details = str(event["details"])
            if not details.startswith("link_id="):
                return None

            try:
                link_id = int(details.removeprefix("link_id="))
            except ValueError:
                return None

            row = connection.execute(
                "SELECT * FROM referral_links WHERE id = ?",
                (link_id,),
            ).fetchone()
        return self._to_referral_link(row) if row is not None else None

    def create_staking_review(
        self, user_id: int, screenshot_file_id: str
    ) -> sqlite3.Row:
        """Переводит ссылку в ожидание решения куратора и сохраняет скрин."""
        with self.database.connect() as connection:
            link = connection.execute(
                """
                SELECT *
                FROM referral_links
                WHERE owner_user_id = ? AND status IN ('submitted', 'pending_staking', 'rejected')
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if link is None:
                raise ValueError("Сначала отправьте свою реферальную ссылку.")

            connection.execute(
                "UPDATE referral_links SET status = 'pending_review' WHERE id = ?",
                (link["id"],),
            )
            cursor = connection.execute(
                """
                INSERT INTO staking_reviews (user_id, referral_link_id, screenshot_file_id)
                VALUES (?, ?, ?)
                """,
                (user_id, link["id"], screenshot_file_id),
            )
            connection.execute(
                """
                UPDATE users
                SET current_step = 'pending_review', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (user_id,),
            )
            self._record_event(connection, user_id, "staking_review_created")
            return connection.execute(
                "SELECT * FROM staking_reviews WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()

    def get_pending_review(self, review_id: int) -> sqlite3.Row | None:
        """Возвращает заявку с данными пользователя и ссылки."""
        with self.database.connect() as connection:
            return connection.execute(
                """
                SELECT
                    reviews.*,
                    users.telegram_id,
                    users.username,
                    users.full_name,
                    users.verification_code,
                    links.url AS referral_url
                FROM staking_reviews AS reviews
                JOIN users ON users.id = reviews.user_id
                JOIN referral_links AS links ON links.id = reviews.referral_link_id
                WHERE reviews.id = ? AND reviews.status = 'pending'
                """,
                (review_id,),
            ).fetchone()

    def decide_review(
        self, review_id: int, reviewer_telegram_id: int, approved: bool
    ) -> sqlite3.Row:
        """Одобряет или отклоняет заявку; при одобрении активирует ссылку FIFO."""
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            review = connection.execute(
                "SELECT * FROM staking_reviews WHERE id = ? AND status = 'pending'",
                (review_id,),
            ).fetchone()
            if review is None:
                raise ValueError("Заявка уже обработана или не существует.")

            decision = "approved" if approved else "rejected"
            link_status = "active" if approved else "rejected"
            user_step = "active_partner" if approved else "pending_staking"

            connection.execute(
                """
                UPDATE staking_reviews
                SET status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (decision, reviewer_telegram_id, review_id),
            )
            connection.execute(
                """
                UPDATE referral_links
                SET status = ?,
                    activated_at = CASE WHEN ? = 'active' THEN CURRENT_TIMESTAMP ELSE activated_at END
                WHERE id = ?
                """,
                (link_status, link_status, review["referral_link_id"]),
            )
            connection.execute(
                """
                UPDATE users
                SET current_step = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (user_step, review["user_id"]),
            )
            self._record_event(
                connection,
                review["user_id"],
                f"staking_review_{decision}",
                f"review_id={review_id}",
            )
            return connection.execute(
                "SELECT * FROM staking_reviews WHERE id = ?", (review_id,)
            ).fetchone()

    def add_admin_referral_link(
        self, url: str, max_limit: int = MAX_REFERRALS_PER_LINK
    ) -> ReferralLink:
        """Добавляет стартовую активную ссылку в хвост очереди."""
        normalized_url = self._normalize_url(url)
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO referral_links (url, max_limit, status, activated_at)
                VALUES (?, ?, 'active', CURRENT_TIMESTAMP)
                """,
                (normalized_url, max_limit),
            )
            row = connection.execute(
                "SELECT * FROM referral_links WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._to_referral_link(row)

    def add_to_waitlist(self, user_id: int) -> None:
        """Добавляет пользователя в лист ожидания без дублей."""
        with self.database.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO waitlist (user_id) VALUES (?)", (user_id,)
            )
            self._record_event(connection, user_id, "waitlist_joined")

    def pop_waitlist_users(self) -> list[int]:
        """Возвращает и очищает лист ожидания после появления новой ссылки."""
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT user_id FROM waitlist ORDER BY created_at, user_id"
            ).fetchall()
            connection.execute("DELETE FROM waitlist")
            return [row["user_id"] for row in rows]

    def _generate_code(self) -> str:
        random = SystemRandom()
        suffix = "".join(random.choice(CODE_ALPHABET) for _ in range(4))
        return f"BiNi-{suffix}"

    @staticmethod
    def _normalize_url(url: str) -> str:
        normalized = url.strip()
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("Ссылка должна начинаться с https:// или http://")
        if len(normalized) > 2048:
            raise ValueError("Ссылка слишком длинная.")
        return normalized

    @staticmethod
    def _to_referral_link(row: sqlite3.Row) -> ReferralLink:
        return ReferralLink(
            id=row["id"],
            url=row["url"],
            used_count=row["used_count"],
            max_limit=row["max_limit"],
            status=row["status"],
            owner_user_id=row["owner_user_id"],
        )

    @staticmethod
    def _record_event(
        connection: sqlite3.Connection,
        user_id: int | None,
        event_name: str,
        details: str | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO events (user_id, event_name, details) VALUES (?, ?, ?)",
            (user_id, event_name, details),
        )