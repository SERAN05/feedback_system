import sqlite3
import sys

DB = 'course_feedback.db'

def main():
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info('student')")
        cols = [r[1] for r in cur.fetchall()]
        print('before:', cols)
        if 'session_token' in cols:
            print('session_token already present')
            return 0
        cur.execute("ALTER TABLE student ADD COLUMN session_token VARCHAR(128)")
        conn.commit()
        cur.execute("PRAGMA table_info('student')")
        cols = [r[1] for r in cur.fetchall()]
        print('after:', cols)
        return 0
    except Exception as e:
        print('error:', e)
        return 2
    finally:
        try:
            conn.close()
        except Exception:
            pass

if __name__ == '__main__':
    sys.exit(main())
