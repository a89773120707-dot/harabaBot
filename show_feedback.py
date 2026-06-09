import sqlite3
conn = sqlite3.connect('results/feedback.db')
c = conn.cursor()

c.execute('SELECT name FROM sqlite_master WHERE type="table"')
print('Tables:', c.fetchall())

for t in ['sent_ads', 'feedback']:
    c.execute(f'PRAGMA table_info({t})')
    print(f'\n--- {t} ({c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]} rows) ---')
    for col in c.fetchall():
        print(f'  {col[1]} ({col[2]})')

print('\n=== Feedback ===')
c.execute('SELECT card_id, title, price, action, comment, created_at FROM feedback ORDER BY created_at')
for r in c.fetchall():
    print(f'  {r[0]} | {r[1]} | {r[2]:,}r | {r[3]} | "{r[4]}" | {r[5]}')
