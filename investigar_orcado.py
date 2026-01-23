import sqlite3

conn = sqlite3.connect('data/rentus.db')
cur = conn.cursor()

# 1. Total orçado dos postos que TÊM NFes
result1 = cur.execute("""
    SELECT 
        COUNT(DISTINCT pt.id) as postos,
        SUM(pt.valor_orcado) as total_orcado,
        AVG(pt.valor_orcado) as media_orcado
    FROM modulo2_postos_trabalho pt
    WHERE pt.id IN (
        SELECT DISTINCT posto_id 
        FROM modulo2_nfe 
        WHERE xml LIKE '%<origem>JSON</origem>%'
        AND posto_id IS NOT NULL
    )
""").fetchone()
print(f"Postos com NFes: {result1[0]}")
print(f"Total orçado (100%): R$ {result1[1]:,.2f}")
print(f"Total orçado (50%): R$ {result1[1] * 0.5:,.2f}")
print(f"Média por posto: R$ {result1[2]:,.2f}")

# 2. Total realizado
result2 = cur.execute("""
    SELECT 
        COUNT(*) as total_nfes,
        SUM(valor_total) as total_realizado,
        AVG(valor_total) as media_nfe
    FROM modulo2_nfe
    WHERE xml LIKE '%<origem>JSON</origem>%'
""").fetchone()
print(f"\nNFes JSON: {result2[0]}")
print(f"Total realizado: R$ {result2[1]:,.2f}")
print(f"Média por NFe: R$ {result2[2]:,.2f}")

# 3. Ver alguns exemplos de valor_orcado
exemplos = cur.execute("""
    SELECT 
        pt.codigo,
        pt.nomecli,
        pt.nomepos,
        pt.valor_orcado,
        COUNT(n.id) as num_nfes,
        COALESCE(SUM(n.valor_total), 0) as total_nfes
    FROM modulo2_postos_trabalho pt
    LEFT JOIN modulo2_nfe n ON n.posto_id = pt.id 
        AND n.xml LIKE '%<origem>JSON</origem>%'
    WHERE pt.id IN (
        SELECT DISTINCT posto_id 
        FROM modulo2_nfe 
        WHERE xml LIKE '%<origem>JSON</origem>%'
        AND posto_id IS NOT NULL
    )
    GROUP BY pt.id
    ORDER BY pt.valor_orcado DESC
    LIMIT 10
""").fetchall()

print(f"\n=== TOP 10 POSTOS POR VALOR ORÇADO ===")
for ex in exemplos:
    print(f"Posto {ex[0]} - {ex[1][:30]}")
    print(f"  Orçado: R$ {ex[3]:,.2f}")
    print(f"  NFes: {ex[4]} | Total NFes: R$ {ex[5]:,.2f}")

# 4. Verificar se valor_orcado deveria ser baseado nas NFes
print(f"\n=== ANÁLISE ===")
print(f"Se orçado esperado é ~300k (50%), então orçado total seria ~600k")
print(f"Mas valor_orcado dos postos soma: R$ {result1[1]:,.2f}")
print(f"Total realizado (NFes): R$ {result2[1]:,.2f}")
print(f"\nPossível solução: Usar soma das NFes como base do orçado?")
print(f"  Orçado = Total NFes * 0.90 = R$ {result2[1] * 0.90:,.2f}")
print(f"  Orçado 50% = R$ {result2[1] * 0.90 * 0.5:,.2f}")

conn.close()
