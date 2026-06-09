import sqlite3
conn = sqlite3.connect('results/feedback.db')
c = conn.cursor()
c.execute('PRAGMA table_info(feedback)')
cols = c.fetchall()
with open('results/feedback_cols.txt', 'w', encoding='utf-8') as f:
    f.write('Feedback table columns:\n')
    for col in cols:
        f.write(f'  {col[1]} ({col[2]})\n')
    # Try to insert a test row
    f.write('\nTest insert...\n')
    try:
        c.execute("""INSERT INTO feedback (card_id, action, comment, reviewer_role, telegram_chat_id, created_at) VALUES ('TEST', 'watch', 'test', 'owner', '123', '2026-01-01')""")
        conn.commit()
        f.write('  SUCCESS\n')
        c.execute('DELETE FROM feedback WHERE card_id="TEST"')
        conn.commit()
    except Exception as e:
        f.write(f'  FAILED: {e}\n')
conn.close()
