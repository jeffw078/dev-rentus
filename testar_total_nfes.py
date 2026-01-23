import sqlite3

conn = sqlite3.connect('data/rentus.db')
cur = conn.cursor()

# Query antiga (com problema)
query_antiga = """
    SELECT 
        COUNT(DISTINCT n.id) as total_nfes,
        COUNT(DISTINCT CASE WHEN n.status = 'identificado' THEN n.id END) as nfes_identificadas,
        COUNT(DISTINCT CASE WHEN n.status = 'pendente' THEN n.id END) as nfes_pendentes,
        COALESCE(SUM(n.valor_total), 0) as valor_total,
        COUNT(DISTINCT i.id) as total_produtos
    FROM modulo2_nfe n
    LEFT JOIN modulo2_nfe_itens i ON i.nfe_id = n.id
    LEFT JOIN modulo2_postos_trabalho pt ON pt.id = n.posto_id
    WHERE n.xml LIKE '%<origem>JSON</origem>%'
"""

# Query nova (corrigida)
query_nova = """
    SELECT 
        COUNT(DISTINCT n.id) as total_nfes,
        COUNT(DISTINCT CASE WHEN n.status = 'identificado' THEN n.id END) as nfes_identificadas,
        COUNT(DISTINCT CASE WHEN n.status = 'pendente' THEN n.id END) as nfes_pendentes,
        COALESCE(SUM(n.valor_total), 0) as valor_total,
        (SELECT COUNT(*) FROM modulo2_nfe_itens i WHERE i.nfe_id IN (SELECT id FROM modulo2_nfe WHERE xml LIKE '%<origem>JSON</origem>%')) as total_produtos
    FROM modulo2_nfe n
    LEFT JOIN modulo2_postos_trabalho pt ON pt.id = n.posto_id
    WHERE n.xml LIKE '%<origem>JSON</origem>%'
"""

print("="*70)
print("TESTE: Query Antiga vs Nova")
print("="*70)

print("\nQuery ANTIGA (com LEFT JOIN itens - PROBLEMA):")
cur.execute(query_antiga)
row = cur.fetchone()
print(f"  Total NFes: {row[0]}")
print(f"  Identificadas: {row[1]}")
print(f"  Pendentes: {row[2]}")
print(f"  Valor Total: R$ {row[3]:,.2f}")
print(f"  Total Produtos: {row[4]}")

print("\nQuery NOVA (sem JOIN itens - CORRIGIDA):")
cur.execute(query_nova)
row = cur.fetchone()
print(f"  Total NFes: {row[0]}")
print(f"  Identificadas: {row[1]}")
print(f"  Pendentes: {row[2]}")
print(f"  Valor Total: R$ {row[3]:,.2f}")
print(f"  Total Produtos: {row[4]}")

print("\n" + "="*70)
print("VALOR ESPERADO: R$ 666.601,42")
print("="*70)

conn.close()
