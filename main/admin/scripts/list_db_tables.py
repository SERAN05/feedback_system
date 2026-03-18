import sqlite3
import sys

paths = ['course_feedback.db', 'instance/course_feedback.db']
for path in paths:
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        print(f"{path}: {tables}")
        conn.close()
    except Exception as e:
        print(f"{path}: ERROR: {e}")
