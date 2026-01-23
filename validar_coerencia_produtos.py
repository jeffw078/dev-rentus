import sqlite3
import pandas as pd
from decimal import Decimal

# Conectar ao banco
conn = sqlite3.connect('data/rentus.db')

# Buscar todos os produtos/itens
query = """
SELECT 
    ni.id,
    ni.nfe_id,
    n.chave_acesso,
    ni.descricao_produto,
    ni.quantidade,
    ni.valor_unitario,
    ni.valor_total,
    (ni.quantidade * ni.valor_unitario) as valor_calculado,
    ABS(ni.valor_total - (ni.quantidade * ni.valor_unitario)) as diferenca
FROM modulo2_nfe_itens ni
JOIN modulo2_nfe n ON ni.nfe_id = n.id
ORDER BY diferenca DESC
"""

df = pd.read_sql_query(query, conn)

print("="*70)
print("VALIDAÇÃO DE COERÊNCIA DOS VALORES DOS PRODUTOS")
print("="*70)

# Análise geral
total_itens = len(df)
itens_corretos = len(df[df['diferenca'] < 0.01])  # Tolerância de 1 centavo
itens_com_diferenca = len(df[df['diferenca'] >= 0.01])

print(f"\n1. ANÁLISE GERAL")
print("-"*70)
print(f"Total de itens: {total_itens}")
print(f"Itens com valores corretos: {itens_corretos} ({itens_corretos/total_itens*100:.1f}%)")
print(f"Itens com diferença: {itens_com_diferenca} ({itens_com_diferenca/total_itens*100:.1f}%)")

if itens_com_diferenca > 0:
    print(f"\n2. ITENS COM DIFERENÇA (TOP 10)")
    print("-"*70)
    print(f"{'Chave NFe':<25} {'Produto':<35} {'Qtd':<8} {'Unit':<12} {'Total':<12} {'Calc':<12} {'Dif':<10}")
    print("-"*70)
    
    for idx, row in df[df['diferenca'] >= 0.01].head(10).iterrows():
        print(f"{row['chave_acesso'][-24:]:<25} {row['descricao_produto'][:33]:<35} "
              f"{row['quantidade']:<8.2f} {row['valor_unitario']:<12.2f} "
              f"{row['valor_total']:<12.2f} {row['valor_calculado']:<12.2f} "
              f"{row['diferenca']:<10.2f}")
    
    # Soma total das diferenças
    total_diferenca = df['diferenca'].sum()
    print(f"\nSoma total das diferenças: R$ {total_diferenca:.2f}")

# Verificar se há valores zerados ou negativos
print(f"\n3. ANÁLISE DE VALORES ANORMAIS")
print("-"*70)

valores_zerados = len(df[df['valor_total'] == 0])
valores_negativos = len(df[df['valor_total'] < 0])
qtd_zerada = len(df[df['quantidade'] == 0])
qtd_negativa = len(df[df['quantidade'] < 0])

print(f"Itens com valor_total = 0: {valores_zerados}")
print(f"Itens com valor_total < 0: {valores_negativos}")
print(f"Itens com quantidade = 0: {qtd_zerada}")
print(f"Itens com quantidade < 0: {qtd_negativa}")

# Análise de valor unitário
print(f"\n4. ESTATÍSTICAS DE VALORES")
print("-"*70)
print(f"Valor unitário mínimo: R$ {df['valor_unitario'].min():.2f}")
print(f"Valor unitário máximo: R$ {df['valor_unitario'].max():.2f}")
print(f"Valor unitário médio: R$ {df['valor_unitario'].mean():.2f}")
print(f"\nValor total mínimo: R$ {df['valor_total'].min():.2f}")
print(f"Valor total máximo: R$ {df['valor_total'].max():.2f}")
print(f"Valor total médio: R$ {df['valor_total'].mean():.2f}")

# Comparar com Excel
print(f"\n5. COMPARAÇÃO COM EXCEL")
print("-"*70)

try:
    excel = pd.read_excel('produtos_com_posto.xlsx')
    
    # Somar valores do Excel
    valor_excel = excel['Valor Total Produto'].sum()
    valor_banco = df['valor_total'].sum()
    
    print(f"Valor total Excel: R$ {valor_excel:,.2f}")
    print(f"Valor total Banco: R$ {valor_banco:,.2f}")
    print(f"Diferença: R$ {abs(valor_excel - valor_banco):,.2f}")
    
    if abs(valor_excel - valor_banco) < 0.01:
        print("✅ Valores totais conferem!")
    else:
        print("❌ Valores totais não conferem!")
        
except Exception as e:
    print(f"Não foi possível ler o Excel: {e}")

print("\n" + "="*70)
print("CONCLUSÃO")
print("="*70)

if itens_com_diferenca == 0:
    print("✅ TODOS os valores estão coerentes (quantidade x valor_unitario = valor_total)")
elif itens_com_diferenca < total_itens * 0.01:  # Menos de 1%
    print(f"⚠️  {itens_com_diferenca} itens com pequenas diferenças (arredondamento)")
    print(f"   Impacto: R$ {df['diferenca'].sum():.2f} em R$ {df['valor_total'].sum():,.2f}")
else:
    print(f"❌ {itens_com_diferenca} itens com diferenças significativas")
    print(f"   Necessário investigar!")

conn.close()
