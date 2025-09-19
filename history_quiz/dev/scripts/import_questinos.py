#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv
from pathlib import Path

# Run this from the folder that contains 'history_quiz' and 'dev'
from history_quiz.config import TOPICS_DIR
from history_quiz.create_topic_db import create_topic_db
from history_quiz.utils.db_connection import get_connection


def import_csv(topic: str, csv_path: Path) -> Path:
    topic_db = Path(TOPICS_DIR) / f"{topic}.db"
    topic_db.parent.mkdir(parents=True, exist_ok=True)
    create_topic_db(str(topic_db))

    conn = get_connection(str(topic_db))
    inserted = 0
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            required = ["question", "a", "b", "c", "d", "correct"]
            if reader.fieldnames is None or any(h not in reader.fieldnames for h in required):
                raise SystemExit(f"CSV must have headers: {', '.join(required)}")
            for row in reader:
                q = (row.get("question") or "").strip()
                opts = [row.get("a",""), row.get("b",""), row.get("c",""), row.get("d","")]
                try:
                    correct_idx = int(str(row.get("correct","0")).strip())
                except ValueError:
                    correct_idx = 0
                if not q or any(not (o or "").strip() for o in opts) or not (1 <= correct_idx <= 4):
                    continue  # skip malformed rows
                cur = conn.execute("INSERT INTO questions (prompt) VALUES (?)", (q,))
                qid = cur.lastrowid
                for i, text in enumerate(opts, start=1):
                    conn.execute(
                        "INSERT INTO answers (question_id, text, is_correct) VALUES (?,?,?)",
                        (qid, (text or "").strip(), 1 if i == correct_idx else 0),
                    )
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    print(f"Imported {inserted} questions into {topic_db}")
    return topic_db


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Import topic questions from CSV into a SQLite topic DB")
    p.add_argument("--topic", required=True, help="Topic name (db will be named <topic>.db)")
    p.add_argument("--csv", required=True, help="Path to CSV file")
    args = p.parse_args(argv)
    csv_path = Path(args.csv)
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")
    import_csv(args.topic, csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
