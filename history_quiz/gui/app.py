from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from history_quiz.config import MAIN_DB_PATH, TOPICS_DIR, ensure_initialized
from ..utils.db_connection import get_connection
from ..main import load_questions, update_stats


def _get_user_id(username: str) -> int | None:
    if not username:
        return None
    conn = get_connection(str(MAIN_DB_PATH))
    try:
        row = conn.execute("SELECT user_id FROM users WHERE username=?", (username,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _list_topics() -> list[str]:
    return [p.stem for p in Path(TOPICS_DIR).glob("*.db")]


class QuizSession:
    def __init__(self, username: str, topic: str, questions):
        self.username = username
        self.topic = topic
        self.questions = questions
        self.index = 0
        self.results: list[tuple[int, bool]] = []

    @property
    def done(self) -> bool:
        return self.index >= len(self.questions)

    def current(self):
        return None if self.done else self.questions[self.index]

    def answer(self, choice_index: int) -> bool:
        qid, _prompt, answers = self.questions[self.index]
        try:
            ok = bool(answers[choice_index][2])
        except Exception:
            ok = False
        self.results.append((qid, ok))
        self.index += 1
        return ok


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("History Quiz (GUI)")
        self.geometry("560x400")
        self.resizable(False, False)
        ensure_initialized()
        self.session: QuizSession | None = None
        self._build_home()

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _build_home(self):
        self._clear()
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Username").grid(row=0, column=0, sticky="w")
        self.username_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.username_var, width=24).grid(row=0, column=1, sticky="w")
        ttk.Button(frm, text="Register", command=self._on_register).grid(row=0, column=2, padx=8)

        ttk.Separator(frm).grid(row=1, column=0, columnspan=3, sticky="ew", pady=10)

        ttk.Label(frm, text="Topic").grid(row=2, column=0, sticky="w")
        self.topic_var = tk.StringVar()
        self.topic_combo = ttk.Combobox(frm, textvariable=self.topic_var, values=_list_topics(), state="readonly", width=24)
        self.topic_combo.grid(row=2, column=1, sticky="w")

        self.mode_var = tk.StringVar(value="count")
        ttk.Radiobutton(frm, text="Count", variable=self.mode_var, value="count").grid(row=3, column=0, sticky="w")
        ttk.Radiobutton(frm, text="All",   variable=self. mode_var, value="all").grid(row=3, column=1, sticky="w")

        ttk.Label(frm, text="Count").grid(row=4, column=0, sticky="w")
        self.count_var = tk.IntVar(value=10)
        ttk.Spinbox(frm, from_=1, to=200, textvariable=self.count_var, width=7).grid(row=4, column=1, sticky="w")

        ttk.Button(frm, text="Start Quiz", command=self._start_quiz).grid(row=5, column=0, pady=12, sticky="w")
        ttk.Button(frm, text="View Summary", command=self._view_summary).grid(row=5, column=1, pady=12, sticky="w")

        for r in range(6):
            frm.grid_rowconfigure(r, pad=6)
        for c in range(3):
            frm.grid_columnconfigure(c, pad=6)

    def _on_register(self):
        username = self.username_var.get().strip()
        if not username:
            messagebox.showerror("Error", "Enter a username.")
            return
        conn = get_connection(str(MAIN_DB_PATH))
        try:
            if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                messagebox.showerror("Error", f"User '{username}' already exists.")
                return
            conn.execute("INSERT INTO users (username) VALUES (?)", (username,))
            conn.commit()
            messagebox.showinfo("Success", f"Registered '{username}'.")
            self.topic_combo["values"] = _list_topics()
        finally:
            conn.close()

    def _start_quiz(self):
        username = self.username_var.get().strip()
        topic = self.topic_var.get().strip()
        mode = self.mode_var.get()
        count = int(self.count_var.get())
        if not username:
            messagebox.showerror("Error", "Enter a username.")
            return
        uid = _get_user_id(username)
        if not uid:
            messagebox.showerror("Error", f"User '{username}' not found. Register first.")
            return
        if not topic:
            messagebox.showerror("Error", "Select a topic.")
            return
        topic_db = (Path(TOPICS_DIR) / f"{topic}.db")
        if not topic_db.is_file():
            messagebox.showerror("Error", f"Topic DB not found: {topic_db}")
            return
        questions = load_questions(topic_db.as_posix(), uid, count, mode == "all")
        if not questions:
            messagebox.showerror("Error", f"No questions found in topic '{topic}'.")
            return
        if mode != "all":
            questions = questions[: min(count, len(questions))]
        self.session = QuizSession(username, topic, questions)
        self._show_question()

    def _show_question(self, feedback: str | None = None):
        self._clear()
        if self.session is None or self.session.done:
            self._finish_quiz(); return
        qid, prompt, answers = self.session.current()
        frm = ttk.Frame(self, padding=16); frm.pack(fill="both", expand=True)
        if feedback:
            ttk.Label(frm, text=feedback).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,8))
        ttk.Label(frm, text=prompt, wraplength=500).grid(row=1, column=0, columnspan=2, sticky="w")
        self.choice_var = tk.IntVar(value=-1)
        for i, (_, text, _) in enumerate(answers, start=1):
            ttk.Radiobutton(frm, text=f"{i}) {text}", variable=self.choice_var, value=i-1).grid(row=1+i, column=0, sticky="w")
        ttk.Button(frm, text="Submit", command=self._submit_answer).grid(row=3+len(answers), column=0, pady=12, sticky="w")
        ttk.Button(frm, text="Cancel", command=self._build_home).grid(row=3+len(answers), column=1, pady=12, sticky="e")

    def _submit_answer(self):
        if self.session is None: return
        idx = self.choice_var.get()
        if idx < 0:
            messagebox.showerror("Error", "Select an answer.")
            return
        ok = self.session.answer(idx)
        self._show_question("✅ Correct!" if ok else "❌ Wrong.")

    def _finish_quiz(self):
        self._clear()
        if self.session is None: self._build_home(); return
        correct = sum(1 for _, ok in self.session.results if ok)
        total = len(self.session.results)
        try:
            update_stats(self.session.username, self.session.topic, self.session.results)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to write stats: {e}")
        frm = ttk.Frame(self, padding=16); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Quiz complete: {correct}/{total} correct.").pack(anchor="w", pady=(0,8))
        ttk.Button(frm, text="Back to Home", command=self._build_home).pack(anchor="w")

    def _view_summary(self):
        username = self.username_var.get().strip()
        if not username:
            messagebox.showerror("Error", "Enter a username first.")
            return
        uid = _get_user_id(username)
        if not uid:
            messagebox.showerror("Error", f"User '{username}' not found.")
            return
        conn = get_connection(str(MAIN_DB_PATH))
        try:
            rows = conn.execute(
                "SELECT topic, pct_green, pct_amber, pct_red, updated_at FROM user_topic_stats WHERE user_id=?",
                (uid,),
            ).fetchall()
        finally:
            conn.close()
        self._clear()
        frm = ttk.Frame(self, padding=16); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"RAG Summary for {username}").pack(anchor="w", pady=(0,8))
        if not rows:
            ttk.Label(frm, text="No summary yet. Take a quiz.").pack(anchor="w")
        else:
            cols = ("topic","G","A","R","Updated")
            tree = ttk.Treeview(frm, columns=cols, show="headings", height=8)
            for c in cols:
                tree.heading(c, text=c)
            tree.column("topic", width=180)
            tree.column("G", width=60, anchor="e")
            tree.column("A", width=60, anchor="e")
            tree.column("R", width=60, anchor="e")
            tree.column("Updated", width=160)
            for topic, g, a, r, upd in rows:
                tree.insert("", "end", values=(topic, f"{g:.1f}", f"{a:.1f}", f"{r:.1f}", upd))
            tree.pack(fill="both", expand=True, pady=(0,8))
        ttk.Button(frm, text="Back", command=self._build_home).pack(anchor="w")


def main():
    App().mainloop()