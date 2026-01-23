import sqlite3

conn = sqlite3.connect('data/rentus.db')
cur = conn.cursor()

print("Colunas da tabela modulo2_nfe:")
cur.execute("PRAGMA table_info(modulo2_nfe)")
for row in cur.fetchall():
    print(f"  {row[1]} ({row[2]})")

conn.close()
