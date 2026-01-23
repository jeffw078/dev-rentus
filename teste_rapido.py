import sqlite3
conn = sqlite3.connect('data/rentus.db')
cur = conn.cursor()
cur.execute("SELECT COUNT(DISTINCT n.id), COALESCE(SUM(n.valor_total), 0) FROM modulo2_nfe n WHERE n.xml LIKE '%<origem>JSON</origem>%'")
row = cur.fetchone()
print(f'NFes: {row[0]}, Valor Total: R$ {row[1]:,.2f}')
conn.close()
