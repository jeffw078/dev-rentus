import pandas as pd
import sqlite3

# Ler arquivo Excel
print("Lendo produtos_com_posto.xlsx...")
df = pd.read_excel('produtos_com_posto.xlsx')

print(f"\n=== DADOS DO EXCEL ===")
print(f"Total de linhas: {len(df)}")
print(f"\nColunas disponíveis:")
print(df.columns.tolist())

# Mostrar primeiras linhas
print(f"\n=== PRIMEIRAS 5 LINHAS ===")
print(df.head())

# Verificar colunas de valor
valor_cols = [col for col in df.columns if 'valor' in col.lower() or 'total' in col.lower() or 'preco' in col.lower()]
print(f"\n=== COLUNAS DE VALOR ENCONTRADAS ===")
print(valor_cols)

# Calcular totais
if valor_cols:
    for col in valor_cols:
        try:
            total = df[col].sum()
            print(f"\nTotal de {col}: R$ {total:,.2f}")
            print(f"Média: R$ {df[col].mean():,.2f}")
            print(f"Min: R$ {df[col].min():,.2f}")
            print(f"Max: R$ {df[col].max():,.2f}")
        except:
            print(f"Não foi possível calcular total para {col}")

# Verificar se tem coluna de NFe
nfe_cols = [col for col in df.columns if 'nfe' in col.lower() or 'nota' in col.lower() or 'chave' in col.lower()]
print(f"\n=== COLUNAS DE NFE ===")
print(nfe_cols)

if nfe_cols:
    print(f"\nNFes únicas: {df[nfe_cols[0]].nunique()}")

# Comparar com banco de dados
print(f"\n=== COMPARAÇÃO COM BANCO DE DADOS ===")
conn = sqlite3.connect('data/rentus.db')

# Total de NFes no banco
nfes_banco = pd.read_sql_query("""
    SELECT COUNT(*) as total, SUM(valor_total) as soma
    FROM modulo2_nfe 
    WHERE xml LIKE '%<origem>JSON</origem>%'
""", conn)

print(f"\nNFes no banco: {nfes_banco['total'].iloc[0]}")
print(f"Valor total no banco: R$ {nfes_banco['soma'].iloc[0]:,.2f}")

# Postos no banco
postos_banco = pd.read_sql_query("""
    SELECT COUNT(*) as total, SUM(valor_orcado) as soma
    FROM modulo2_postos_trabalho
""", conn)

print(f"\nPostos no banco: {postos_banco['total'].iloc[0]}")
print(f"Valor orçado total: R$ {postos_banco['soma'].iloc[0]:,.2f}")

conn.close()

print("\n=== RESUMO ===")
print("Para validação, compare:")
print("1. Total de NFes: Excel vs Banco")
print("2. Valor total: Excel vs Banco")
print("3. Se os valores do Excel representam o 'realizado' esperado de ~600k")
