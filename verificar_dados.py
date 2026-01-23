import sqlite3

conn = sqlite3.connect('data/rentus.db')
cur = conn.cursor()

# 1. Verificar NFes com origem JSON
result1 = cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(valor_total), 0) 
    FROM modulo2_nfe 
    WHERE xml LIKE '%<origem>JSON</origem>%'
""").fetchone()
print(f'NFes com origem JSON: {result1[0]} NFes, Total: R$ {result1[1]:,.2f}')

# 2. Verificar NFes Mockadas
result2 = cur.execute("""
    SELECT COUNT(*) 
    FROM modulo2_nfe 
    WHERE nome_emitente IN ('FORNECEDOR ABC LTDA', 'SUPPLY COMPANY XYZ', 'DISTRIBUIDORA 123', 'COMERCIAL DEF LTDA')
""").fetchone()
print(f'NFes Mockadas: {result2[0]} NFes')

# 3. Verificar Postos com valores orçados
result3 = cur.execute("""
    SELECT COUNT(*), SUM(valor_orcado) 
    FROM modulo2_postos_trabalho
""").fetchone()
if result3[1]:
    print(f'Postos: {result3[0]} postos, Valor Orçado Total: R$ {result3[1]:,.2f}')
else:
    print(f'Postos: {result3[0]} postos, sem valores orçados')

# 4. Verificar problema da query multiplicada (LEFT JOIN)
result4 = cur.execute("""
    SELECT 
        COALESCE(SUM(pt.valor_orcado), 0) as total_orcado_errado,
        COALESCE(SUM(nfe.valor_total), 0) as total_realizado,
        (SELECT SUM(valor_orcado) FROM modulo2_postos_trabalho) as total_orcado_correto
    FROM modulo2_nfe nfe
    LEFT JOIN modulo2_postos_trabalho pt ON nfe.posto_id = pt.id
    WHERE nfe.xml LIKE '%<origem>JSON</origem>%'
""").fetchone()
print(f'\n=== PROBLEMA ENCONTRADO ===')
print(f'Total Orçado (ERRADO - multiplicado): R$ {result4[0]:,.2f}')
print(f'Total Realizado: R$ {result4[1]:,.2f}')
print(f'Total Orçado (CORRETO): R$ {result4[2]:,.2f}')
print(f'Diferença (multiplicação): R$ {result4[0] - result4[2]:,.2f}')

conn.close()
