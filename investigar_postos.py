import sqlite3

conn = sqlite3.connect('data/rentus.db')
cur = conn.cursor()

# 1. Total de postos
total_postos = cur.execute("SELECT COUNT(*), SUM(valor_orcado) FROM modulo2_postos_trabalho").fetchone()
print(f"Total de postos: {total_postos[0]}")
print(f"Valor orçado total (todos): R$ {total_postos[1]:,.2f}")

# 2. Postos COM NFes JSON
postos_com_nfes = cur.execute("""
    SELECT COUNT(DISTINCT pt.id), SUM(DISTINCT pt.valor_orcado)
    FROM modulo2_postos_trabalho pt
    WHERE pt.id IN (
        SELECT DISTINCT nfe.posto_id 
        FROM modulo2_nfe nfe 
        WHERE nfe.xml LIKE '%<origem>JSON</origem>%'
    )
""").fetchone()
print(f"\nPostos COM NFes JSON: {postos_com_nfes[0]}")
print(f"Valor orçado (postos com NFes): R$ {postos_com_nfes[1]:,.2f}")

# 3. Quantas NFes por posto_id
nfes_por_posto = cur.execute("""
    SELECT COUNT(*) as total_nfes, COUNT(DISTINCT posto_id) as postos_distintos
    FROM modulo2_nfe 
    WHERE xml LIKE '%<origem>JSON</origem>%' AND posto_id IS NOT NULL
""").fetchone()
print(f"\nNFes JSON: {nfes_por_posto[0]} NFes distribuídas em {nfes_por_posto[1]} postos")

# 4. Quantas NFes sem posto_id
sem_posto = cur.execute("""
    SELECT COUNT(*) 
    FROM modulo2_nfe 
    WHERE xml LIKE '%<origem>JSON</origem>%' AND posto_id IS NULL
""").fetchone()
print(f"NFes sem posto_id: {sem_posto[0]}")

conn.close()

print("\n=== ANÁLISE ===")
print("O dashboard deveria mostrar:")
print("- Orçado: Soma de TODOS os postos (mesmo sem NFes)")
print("- Realizado: Soma de todas as NFes JSON")
print("\nOu mostrar apenas postos que TÊM NFes?")
