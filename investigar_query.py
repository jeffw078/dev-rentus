import sqlite3
from datetime import date

conn = sqlite3.connect('data/rentus.db')
cur = conn.cursor()

# Testar query com filtros de data
data_ini = '2026-01-01'
data_fim = '2026-01-23'

# 1. Total sem filtro de data
total_sem_filtro = cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(valor_total), 0)
    FROM modulo2_nfe
    WHERE xml LIKE '%<origem>JSON</origem>%'
""").fetchone()
print(f"NFes JSON (sem filtro): {total_sem_filtro[0]} NFes, Total: R$ {total_sem_filtro[1]:,.2f}")

# 2. Total COM filtro de data
total_com_filtro = cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(valor_total), 0)
    FROM modulo2_nfe
    WHERE xml LIKE '%<origem>JSON</origem>%'
    AND date(data_emissao) >= ?
    AND date(data_emissao) <= ?
""", (data_ini, data_fim)).fetchone()
print(f"NFes JSON ({data_ini} a {data_fim}): {total_com_filtro[0]} NFes, Total: R$ {total_com_filtro[1]:,.2f}")

# 3. Ver algumas datas
datas = cur.execute("""
    SELECT data_emissao, COUNT(*), SUM(valor_total)
    FROM modulo2_nfe
    WHERE xml LIKE '%<origem>JSON</origem>%'
    GROUP BY data_emissao
    ORDER BY data_emissao DESC
    LIMIT 10
""").fetchall()
print(f"\nDatas de emissão das NFes:")
for d in datas:
    print(f"  {d[0]}: {d[1]} NFes, R$ {d[2]:,.2f}")

# 4. Verificar se LEFT JOIN está duplicando
query_join = """
    SELECT 
        COALESCE(SUM(pt.valor_orcado), 0) as total_orcado,
        COALESCE(SUM(nfe.valor_total), 0) as total_realizado,
        COUNT(pt.id) as count_postos,
        COUNT(nfe.id) as count_nfes
    FROM modulo2_postos_trabalho pt
    LEFT JOIN modulo2_nfe nfe ON nfe.posto_id = pt.id 
        AND nfe.xml LIKE '%<origem>JSON</origem>%'
        AND date(nfe.data_emissao) >= ?
        AND date(nfe.data_emissao) <= ?
    WHERE 1=1
"""
resultado_join = cur.execute(query_join, (data_ini, data_fim)).fetchone()
print(f"\n=== RESULTADO LEFT JOIN ===")
print(f"Total Orçado: R$ {resultado_join[0]:,.2f}")
print(f"Total Realizado: R$ {resultado_join[1]:,.2f}")
print(f"Contagem Postos (com duplicação): {resultado_join[2]}")
print(f"Contagem NFes: {resultado_join[3]}")

conn.close()
