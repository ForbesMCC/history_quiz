#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, random, sys
from history_quiz.utils.db_connection import get_connection
from .config import MAIN_DB_PATH, TOPICS_DIR, ensure_initialized
from pathlib import Path

GREEN_THRESHOLD = 0.8
AMBER_THRESHOLD = 0.5


def _get_user_id(username: str):
    conn = get_connection(str(MAIN_DB_PATH))
    try:
        row = conn.execute("SELECT user_id FROM users WHERE username = ?", (username,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def register_user(args) -> int:
    ensure_initialized()
    username = args.username.strip()
    if not username:
        print("Username is required.")
        return 2
    conn = get_connection(str(MAIN_DB_PATH))
    try:
        if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            print(f"Error: User '{username}' already exists.")
            return 1
        conn.execute("INSERT INTO users (username) VALUES (?)", (username,))
        conn.commit()
        print(f"Registered new user: {username}")
        return 0
    finally:
        conn.close()


def view_summary(args) -> int:
    ensure_initialized()
    username = args.username
    uid = _get_user_id(username)
    if not uid:
        print(f"Error: User '{username}' not found. Please register first.")
        return 1
    conn = get_connection(str(MAIN_DB_PATH))
    try:
        rows = conn.execute(
            "SELECT topic, pct_green, pct_amber, pct_red, updated_at "
            "FROM user_topic_stats WHERE user_id = ?",
            (uid,),
        ).fetchall()
        if not rows:
            print("No summary data found. Try taking a quiz first.")
            return 0
        print(f"RAG Summary for {username}:")
        for topic, g, a, r, updated in rows:
            print(f"  • {topic}:  G={g:.1f}%  A={a:.1f}%  R={r:.1f}%  (updated {updated})")
        return 0
    finally:
        conn.close()


# ---------- Core quiz helpers used by CLI and GUI ----------

def load_questions(topic_db_path: str, user_id: int, count: int, fetch_all: bool = False):
    """
    Returns list[(question_id, prompt, answers)] where answers is
    list[(answer_id, text, is_correct)]. Ordered by lowest performance first.
    """
    tconn = get_connection(topic_db_path)
    try:
        cur = tconn.execute(
            """
            SELECT q.question_id, q.prompt,
                   COALESCE(s.correct_count, 0) AS cc,
                   COALESCE(s.attempt_count, 0) AS ac
            FROM questions q
            LEFT JOIN question_stats s
              ON q.question_id = s.question_id AND s.user_id = ?
            """,
            (user_id,),
        )
        qlist = []
        for qid, prompt, cc, ac in cur.fetchall():
            ratio = (cc / ac) if ac > 0 else 0.0
            qlist.append((qid, prompt, ratio))
        qlist.sort(key=lambda x: (x[2], x[0]))

        selected = qlist if fetch_all else (qlist * ((max(1, count) // max(1, len(qlist))) + 1))[: max(0, count)]
        questions = []
        for qid, prompt, _ in selected:
            answers = tconn.execute(
                "SELECT answer_id, text, is_correct FROM answers WHERE question_id = ?",
                (qid,),
            ).fetchall()
            random.shuffle(answers)
            questions.append((qid, prompt, answers))
        return questions
    finally:
        tconn.close()


def update_stats(username: str, topic: str, session_results: list[tuple[int, bool]]) -> None:
    ensure_initialized()
    uid = _get_user_id(username)
    if uid is None:
        raise RuntimeError(f"User '{username}' does not exist.")

    topic_db = os.path.join(str(TOPICS_DIR), f"{topic}.db")
    tconn = get_connection(topic_db)
    mconn = get_connection(str(MAIN_DB_PATH))
    try:
        for qid, ok in session_results:
            row = tconn.execute(
                "SELECT correct_count, attempt_count FROM question_stats WHERE user_id=? AND question_id=?",
                (uid, qid),
            ).fetchone()
            if row:
                cc, ac = row
                cc += int(ok)
                ac += 1
                tconn.execute(
                    "UPDATE question_stats SET correct_count=?, attempt_count=?, last_updated=CURRENT_TIMESTAMP "
                    "WHERE user_id=? AND question_id=?",
                    (cc, ac, uid, qid),
                )
            else:
                tconn.execute(
                    "INSERT INTO question_stats (user_id, question_id, correct_count, attempt_count) VALUES (?,?,?,?)",
                    (uid, qid, int(ok), 1),
                )
            mconn.execute(
                "INSERT INTO answer_history (user_id, topic, question_id, was_correct) VALUES (?,?,?,?)",
                (uid, topic, qid, int(ok)),
            )
        tconn.commit(); mconn.commit()

        # recompute topic-level RAG
        rows = tconn.execute(
            "SELECT correct_count, attempt_count FROM question_stats WHERE user_id=?",
            (uid,),
        ).fetchall()
        green = amber = red = total = 0
        for cc, ac in rows:
            ratio = cc / ac if ac else 0.0
            if ratio >= GREEN_THRESHOLD:
                green += 1
            elif ratio >= AMBER_THRESHOLD:
                amber += 1
            else:
                red += 1
            total += 1
        pct_g = (green / total * 100) if total else 0
        pct_a = (amber / total * 100) if total else 0
        pct_r = (red / total * 100) if total else 0
        mconn.execute(
            (
                "INSERT INTO user_topic_stats (user_id, topic, pct_green, pct_amber, pct_red) "
                "VALUES (?,?,?,?,?) "
                "ON CONFLICT(user_id, topic) DO UPDATE SET "
                "pct_green=excluded.pct_green, pct_amber=excluded.pct_amber, pct_red=excluded.pct_red, "
                "updated_at=CURRENT_TIMESTAMP"
            ),
            (uid, topic, pct_g, pct_a, pct_r),
        )
        mconn.commit()
    finally:
        tconn.close(); mconn.close()


# ---------- CLI entry ----------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="history-quiz", description="History Quiz CLI")
    sub = p.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="Create a new user")
    p_reg.add_argument("username", help="Username to register")
    p_reg.set_defaults(func=register_user)

    p_sum = sub.add_parser("summary", help="View your RAG summary")
    p_sum.add_argument("username", help="Your username")
    p_sum.set_defaults(func=view_summary)

    p_q = sub.add_parser("quiz", help="Take a quiz on a topic")
    p_q.add_argument("username", help="Your username")
    p_q.add_argument("topic", help="Topic name (filename without .db)")
    g = p_q.add_mutually_exclusive_group(required=True)
    g.add_argument("--count", type=int, help="Number of questions to ask")
    g.add_argument("--all", action="store_true", help="Ask all questions")

    def _run(args):
        ensure_initialized()
        if args.command == "quiz":
            # lightweight wrapper so exit codes are clear
            uid = _get_user_id(args.username)
            if not uid:
                print(f"Error: User '{args.username}' not found. Please register first.")
                return 1
            topic_db = (Path(TOPICS_DIR) / f"{args.topic}.db").as_posix()
            if not Path(topic_db).is_file():
                print(f"Error: Topic database not found: {topic_db}")
                return 1
            qs = load_questions(topic_db, uid, args.count or 0, bool(args.all))
            if not qs:
                print(f"No questions found in topic '{args.topic}'.")
                return 0
            # simple terminal quiz loop
            results = []
            for idx, (qid, prompt, answers) in enumerate(qs if args.all else qs[: args.count], start=1):
                print(f"Q{idx}: {prompt}")
                for i, (_, text, _) in enumerate(answers, start=1):
                    print(f"  {i}) {text}")
                try:
                    choice = int(input("Your answer (number): ").strip()) - 1
                    correct = bool(answers[choice][2])
                except Exception:
                    correct = False
                print("Correct!" if correct else "Wrong.")
                print()
                results.append((qid, correct))
            update_stats(args.username, args.topic, results)
            ok = sum(1 for _, c in results if c)
            print(f"✨ Quiz complete: you answered {ok}/{len(results)} correctly. ✨")
            return 0
        else:
            return args.func(args) or 0

    p.set_defaults(func=_run)
    return p


def cli(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    rc = args.func(args)
    return int(rc or 0)


if __name__ == "__main__":
    raise SystemExit(cli())