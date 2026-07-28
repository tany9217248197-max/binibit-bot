"""SQLite-хранилище для MVP-бота BiNiBit."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class Database:
    """Создаёт схему и выдаёт соединения SQLite с транзакциями."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Открывает соединение и откатывает транзакцию при ошибке."""
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Создаёт таблицы, индексы и ограничения MVP."""
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    verification_code TEXT NOT NULL UNIQUE,
                    current_step TEXT NOT NULL DEFAULT 'start',
                    notifications_enabled INTEGER NOT NULL DEFAULT 1
                        CHECK (notifications_enabled IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS referral_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id INTEGER,
                    verification_code TEXT,
                    url TEXT NOT NULL UNIQUE,
                    used_count INTEGER NOT NULL DEFAULT 0
                        CHECK (used_count >= 0),
                    max_limit INTEGER NOT NULL DEFAULT 3
                        CHECK (max_limit > 0),
                    status TEXT NOT NULL
                        CHECK (status IN (
                            'submitted',
                            'pending_staking',
                            'pending_review',
                            'active',
                            'limit_reached',
                            'rejected'
                        )),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    activated_at TEXT,
                    FOREIGN KEY (owner_user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS staking_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    referral_link_id INTEGER NOT NULL,
                    screenshot_file_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected')),
                    reviewed_by INTEGER,
                    reviewed_at TEXT,
                    comment TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (referral_link_id) REFERENCES referral_links(id)
                );

                CREATE TABLE IF NOT EXISTS waitlist (
                    user_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    event_name TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_referral_queue
                    ON referral_links(status, created_at, id);

                CREATE INDEX IF NOT EXISTS idx_staking_reviews_pending
                    ON staking_reviews(status, created_at, id);
                """
            )