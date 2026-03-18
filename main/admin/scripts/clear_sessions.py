import sqlite3
import os

# Resolve DB path from project root
DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'course_feedback.db')
if not os.path.exists(DB):
    DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'course_feedback.db')

print('Using DB:', DB)
conn = sqlite3.connect(DB)
cur = conn.cursor()
try:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_session'")
    if not cur.fetchone():
        print('No student_session table found. Nothing to clear.')
    else:
        cur.execute('SELECT COUNT(*) FROM student_session')
        n = cur.fetchone()[0]
        cur.execute('DELETE FROM student_session')
        conn.commit()
        print('Cleared student_session rows:', n)
except Exception as e:
    print('Error clearing sessions:', e)
finally:
    conn.close()
