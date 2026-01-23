import pandas as pd
import sqlite3

# Ler arquivo Excel
print("Lendo produtos_com_posto.xlsx...")
df = pd.read_excel('produtos_com_posto.xlsx')

print(f"\n=== PRODUTOS NO EXCEL ===")
print(f"Total de linhas/produtos: {len(df)}")
print(f"Valor total dos produtos: R$ {df['valor_total_produto'].sum():,.2f}")

# Agrupar por produto
produtos_excel = df.groupby('produto').agg({
    'valor_total_produto': 'sum',
    'quantidade': 'sum'
}).sort_values('valor_total_produto', ascending=False)

print(f"\n=== TOP 10 PRODUTOS (EXCEL) ===")
for idx, (produto, row) in enumerate(produtos_excel.head(10).iterrows(), 1):
    print(f"{idx}. {produto[:50]}")
    print(f"   Valor total: R$ {row['valor_total_produto']:,.2f}")
    print(f"   Quantidade: {row['quantidade']:.2f}")

# Comparar com banco de dados
print(f"\n=== PRODUTOS NO BANCO DE DADOS ===")
conn = sqlite3.connect('data/rentus.db')

# Total de produtos/itens
produtos_banco = pd.read_sql_query("""
    SELECT 
        COUNT(*) as total_itens,
        SUM(valor_total) as valor_total,
        SUM(quantidade) as quantidade_total
    FROM modulo2_nfe_itens
    WHERE nfe_id IN (
        SELECT id FROM modulo2_nfe WHERE xml LIKE '%<origem>JSON</origem>%'
    )
""", conn)

print(f"Total de itens: {produtos_banco['total_itens'].iloc[0]}")
print(f"Valor total: R$ {produtos_banco['valor_total'].iloc[0]:,.2f}")
print(f"Quantidade total: {produtos_banco['quantidade_total'].iloc[0]:,.2f}")

# Top 10 produtos no banco
top_produtos_banco = pd.read_sql_query("""
    SELECT 
        descricao_produto,
        SUM(valor_total) as valor_total,
        SUM(quantidade) as quantidade
    FROM modulo2_nfe_itens
    WHERE nfe_id IN (
        SELECT id FROM modulo2_nfe WHERE xml LIKE '%<origem>JSON</origem>%'
    )
    GROUP BY descricao_produto
    ORDER BY valor_total DESC
    LIMIT 10
""", conn)

print(f"\n=== TOP 10 PRODUTOS (BANCO) ===")
for idx, row in top_produtos_banco.iterrows():
    print(f"{idx+1}. {row['descricao_produto'][:50]}")
    print(f"   Valor total: R$ {row['valor_total']:,.2f}")
    print(f"   Quantidade: {row['quantidade']:.2f}")

conn.close()

# Comparação direta
print(f"\n=== COMPARAÇÃO ===")
print(f"Produtos Excel: {len(df)} itens")
print(f"Produtos Banco: {produtos_banco['total_itens'].iloc[0]} itens")
print(f"Diferença: {len(df) - produtos_banco['total_itens'].iloc[0]} itens")

print(f"\nValor Excel: R$ {df['valor_total_produto'].sum():,.2f}")
print(f"Valor Banco: R$ {produtos_banco['valor_total'].iloc[0]:,.2f}")
diferenca_valor = df['valor_total_produto'].sum() - produtos_banco['valor_total'].iloc[0]
print(f"Diferença: R$ {diferenca_valor:,.2f}")

if abs(diferenca_valor) < 0.01:
    print("\n✅ Valores dos produtos estão CORRETOS!")
else:
    print(f"\n⚠️ ATENÇÃO: Diferença de R$ {abs(diferenca_valor):,.2f}")
