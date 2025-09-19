from __future__ import annotations
from .utils.db_connection import get_connection

SCHEMA = r"""
-- per-topic database schema
CREATE TABLE IF NOT EXISTS questions (
  question_id INTEGER PRIMARY KEY,
  prompt      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS answers (
  answer_id   INTEGER PRIMARY KEY,
  question_id INTEGER NOT NULL,
  text        TEXT NOT NULL,
  is_correct  INTEGER NOT NULL CHECK (is_correct IN (0,1)),
  FOREIGN KEY(question_id) REFERENCES questions(question_id)
);

CREATE TABLE IF NOT EXISTS question_stats (
  user_id       INTEGER NOT NULL,
  question_id   INTEGER NOT NULL,
  correct_count INTEGER NOT NULL DEFAULT 0,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  last_updated  DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(user_id, question_id)
);
"""


def create_topic_db(path: str) -> None:
    conn = get_connection(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()