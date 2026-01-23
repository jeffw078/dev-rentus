import pandas as pd
import sqlite3

print("="*70)
print("ANÁLISE COMPLETA: EXCEL vs BANCO DE DADOS")
print("="*70)

# Ler arquivo Excel
df = pd.read_excel('produtos_com_posto.xlsx')

# Conectar ao banco
conn = sqlite3.connect('data/rentus.db')

# ============================================================================
# 1. NFES
# ============================================================================
print("\n1. NFes")
print("-" * 70)

nfes_excel = df['chave_nf'].nunique()
valor_total_excel = df['valor_total_produto'].sum()

nfes_banco = pd.read_sql_query("""
    SELECT COUNT(*) as total, SUM(valor_total) as soma
    FROM modulo2_nfe WHERE xml LIKE '%<origem>JSON</origem>%'
""", conn)

print(f"NFes Excel:  {nfes_excel}")
print(f"NFes Banco:  {nfes_banco['total'].iloc[0]}")
print(f"✅ Match" if nfes_excel == nfes_banco['total'].iloc[0] else "❌ Diferença")

print(f"\nValor Excel: R$ {valor_total_excel:,.2f}")
print(f"Valor Banco: R$ {nfes_banco['soma'].iloc[0]:,.2f}")
print(f"✅ Match" if abs(valor_total_excel - nfes_banco['soma'].iloc[0]) < 0.01 else "❌ Diferença")

# ============================================================================
# 2. PRODUTOS/ITENS
# ============================================================================
print("\n2. Produtos/Itens")
print("-" * 70)

itens_excel = len(df)
itens_banco = pd.read_sql_query("""
    SELECT COUNT(*) as total
    FROM modulo2_nfe_itens
    WHERE nfe_id IN (SELECT id FROM modulo2_nfe WHERE xml LIKE '%<origem>JSON</origem>%')
""", conn)

print(f"Itens Excel: {itens_excel}")
print(f"Itens Banco: {itens_banco['total'].iloc[0]}")
print(f"✅ Match" if itens_excel == itens_banco['total'].iloc[0] else "❌ Diferença")

# ============================================================================
# 3. CLIENTES
# ============================================================================
print("\n3. Clientes")
print("-" * 70)

# Clientes identificados no Excel
clientes_excel = df[df['cliente'].notna()]['cliente'].nunique()
clientes_com_nfes_excel = df[df['cliente'].notna()].groupby('cliente').agg({
    'valor_total_produto': 'sum'
}).sort_values('valor_total_produto', ascending=False)

print(f"Clientes identificados no Excel: {clientes_excel}")
print(f"\nTOP 5 Clientes (Excel):")
for idx, (cliente, row) in enumerate(clientes_com_nfes_excel.head(5).iterrows(), 1):
    print(f"  {idx}. {cliente[:40]}: R$ {row['valor_total_produto']:,.2f}")

# Clientes no banco
clientes_banco = pd.read_sql_query("""
    SELECT DISTINCT nomecli FROM modulo2_postos_trabalho
    WHERE nomecli IS NOT NULL AND nomecli != ''
""", conn)

print(f"\nTotal de clientes cadastrados no banco: {len(clientes_banco)}")

# ============================================================================
# 4. POSTOS DE TRABALHO
# ============================================================================
print("\n4. Postos de Trabalho")
print("-" * 70)

# Postos identificados no Excel
postos_excel = df[df['posto_trabalho'].notna()]['posto_trabalho'].nunique()
print(f"Postos identificados no Excel: {postos_excel}")

postos_banco = pd.read_sql_query("""
    SELECT COUNT(*) as total FROM modulo2_postos_trabalho
""", conn)
print(f"Postos cadastrados no banco: {postos_banco['total'].iloc[0]}")

# ============================================================================
# 5. STATUS DE IDENTIFICAÇÃO
# ============================================================================
print("\n5. Status de Identificação")
print("-" * 70)

# Status no Excel
status_excel = df['_status'].value_counts()
print("Status no Excel:")
for status, count in status_excel.items():
    produtos_status = count
    valor_status = df[df['_status'] == status]['valor_total_produto'].sum()
    print(f"  {status}: {produtos_status} itens (R$ {valor_status:,.2f})")

# Status no banco
status_banco = pd.read_sql_query("""
    SELECT 
        n.status,
        COUNT(DISTINCT n.id) as nfes,
        COUNT(i.id) as itens,
        SUM(i.valor_total) as valor_total
    FROM modulo2_nfe n
    LEFT JOIN modulo2_nfe_itens i ON i.nfe_id = n.id
    WHERE n.xml LIKE '%<origem>JSON</origem>%'
    GROUP BY n.status
""", conn)

print("\nStatus no Banco (por NFe):")
for _, row in status_banco.iterrows():
    print(f"  {row['status']}: {row['nfes']} NFes, {row['itens']} itens (R$ {row['valor_total']:,.2f})")

# ============================================================================
# 6. PENDÊNCIAS
# ============================================================================
print("\n6. Análise de Pendências")
print("-" * 70)

# NFes pendentes no Excel
nfes_pendentes_excel = df[df['_status'] == 'PENDENTE']['chave_nf'].nunique()
valor_pendente_excel = df[df['_status'] == 'PENDENTE']['valor_total_produto'].sum()

print(f"NFes pendentes Excel: {nfes_pendentes_excel}")
print(f"Valor pendente Excel: R$ {valor_pendente_excel:,.2f}")

# NFes pendentes no banco
pendentes_banco = pd.read_sql_query("""
    SELECT COUNT(*) as total, SUM(valor_total) as soma
    FROM modulo2_nfe 
    WHERE status = 'pendente' AND xml LIKE '%<origem>JSON</origem>%'
""", conn)

print(f"\nNFes pendentes Banco: {pendentes_banco['total'].iloc[0]}")
print(f"Valor pendente Banco: R$ {pendentes_banco['soma'].iloc[0]:,.2f}")

# ============================================================================
# 7. RESUMO FINAL
# ============================================================================
print("\n" + "="*70)
print("RESUMO DA VALIDAÇÃO")
print("="*70)

issues = []

if nfes_excel != nfes_banco['total'].iloc[0]:
    issues.append(f"❌ NFes: Excel={nfes_excel}, Banco={nfes_banco['total'].iloc[0]}")
else:
    print("✅ Quantidade de NFes: CORRETO")

if abs(valor_total_excel - nfes_banco['soma'].iloc[0]) > 0.01:
    issues.append(f"❌ Valor total: Diferença de R$ {abs(valor_total_excel - nfes_banco['soma'].iloc[0]):,.2f}")
else:
    print("✅ Valor total: CORRETO")

if itens_excel != itens_banco['total'].iloc[0]:
    issues.append(f"❌ Itens: Excel={itens_excel}, Banco={itens_banco['total'].iloc[0]}")
else:
    print("✅ Quantidade de itens: CORRETO")

if abs(nfes_pendentes_excel - pendentes_banco['total'].iloc[0]) > 0:
    print(f"⚠️  NFes pendentes: Excel={nfes_pendentes_excel}, Banco={pendentes_banco['total'].iloc[0]}")
else:
    print("✅ NFes pendentes: CORRETO")

if issues:
    print("\n⚠️  PROBLEMAS ENCONTRADOS:")
    for issue in issues:
        print(f"  {issue}")
else:
    print("\n🎉 TODOS OS DADOS ESTÃO CORRETOS E SINCRONIZADOS!")

conn.close()
