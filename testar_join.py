import sqlite3

conn = sqlite3.connect('data/rentus.db')
cur = conn.cursor()

data_ini = '2026-01-01'
data_fim = '2026-01-23'

# Testar diferentes formatos de filtro de data
print("=== TESTE 1: date(data_emissao) ===")
result1 = cur.execute("""
    SELECT COUNT(*), SUM(valor_total)
    FROM modulo2_nfe
    WHERE xml LIKE '%<origem>JSON</origem>%'
    AND date(data_emissao) >= ?
    AND date(data_emissao) <= ?
""", (data_ini, data_fim)).fetchone()
print(f"Resultado: {result1[0]} NFes, R$ {result1[1]:,.2f}")

print("\n=== TESTE 2: substr(data_emissao, 1, 10) ===")
result2 = cur.execute("""
    SELECT COUNT(*), SUM(valor_total)
    FROM modulo2_nfe
    WHERE xml LIKE '%<origem>JSON</origem>%'
    AND substr(data_emissao, 1, 10) >= ?
    AND substr(data_emissao, 1, 10) <= ?
""", (data_ini, data_fim)).fetchone()
print(f"Resultado: {result2[0]} NFes, R$ {result2[1]:,.2f}")

print("\n=== TESTE 3: data_emissao LIKE '2026-01%' ===")
result3 = cur.execute("""
    SELECT COUNT(*), SUM(valor_total)
    FROM modulo2_nfe
    WHERE xml LIKE '%<origem>JSON</origem>%'
    AND data_emissao LIKE '2026-01%'
""").fetchone()
print(f"Resultado: {result3[0]} NFes, R$ {result3[1]:,.2f}")

print("\n=== TESTE 4: Sem filtro de data ===")
result4 = cur.execute("""
    SELECT COUNT(*), SUM(valor_total)
    FROM modulo2_nfe
    WHERE xml LIKE '%<origem>JSON</origem>%'
""").fetchone()
print(f"Resultado: {result4[0]} NFes, R$ {result4[1]:,.2f}")

# Testar JOIN simples
print("\n=== TESTE 5: JOIN sem filtro de data ===")
result5 = cur.execute("""
    SELECT 
        COALESCE(SUM(pt.valor_orcado), 0),
        COALESCE(SUM(nfe.valor_total), 0)
    FROM modulo2_postos_trabalho pt
    LEFT JOIN modulo2_nfe nfe ON nfe.posto_id = pt.id 
        AND nfe.xml LIKE '%<origem>JSON</origem>%'
""").fetchone()
print(f"Orçado: R$ {result5[0]:,.2f}, Realizado: R$ {result5[1]:,.2f}")

# Verificar se está duplicando valor_orcado
print("\n=== TESTE 6: Verificar duplicação ===")
result6 = cur.execute("""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT pt.id) as postos_distintos,
        COUNT(DISTINCT nfe.id) as nfes_distintas
    FROM modulo2_postos_trabalho pt
    LEFT JOIN modulo2_nfe nfe ON nfe.posto_id = pt.id 
        AND nfe.xml LIKE '%<origem>JSON</origem>%'
""").fetchone()
print(f"Total de linhas: {result6[0]}")
print(f"Postos distintos: {result6[1]}")
print(f"NFes distintas: {result6[2]}")
print(f"Diferença (postos duplicados): {result6[0] - result6[1]}")

conn.close()
