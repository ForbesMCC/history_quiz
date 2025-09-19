from __future__ import annotations
from .utils.db_connection import get_connection

SCHEMA = r"""
-- users and aggregated stats live in main.db
CREATE TABLE IF NOT EXISTS users (
  user_id   INTEGER PRIMARY KEY,
  username  TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS answer_history (
  id          INTEGER PRIMARY KEY,
  user_id     INTEGER NOT NULL,
  topic       TEXT NOT NULL,
  question_id INTEGER NOT NULL,
  was_correct INTEGER NOT NULL CHECK (was_correct IN (0,1)),
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS user_topic_stats (
  user_id    INTEGER NOT NULL,
  topic      TEXT NOT NULL,
  pct_green  REAL NOT NULL DEFAULT 0,
  pct_amber  REAL NOT NULL DEFAULT 0,
  pct_red    REAL NOT NULL DEFAULT 0,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(user_id, topic),
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);
"""


def create_main_db(path: str) -> None:
    conn = get_connection(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()