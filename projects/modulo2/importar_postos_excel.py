#!/usr/bin/env python3
# projects/modulo2/importar_postos_excel.py

"""
Script para importar clientes/postos de trabalho de arquivo Excel para o banco de dados.

Uso:
    python -m projects.modulo2.importar_postos_excel <caminho_do_arquivo.xlsx>
    
    ou
    
    python projects/modulo2/importar_postos_excel.py <caminho_do_arquivo.xlsx>

Exemplo de estrutura esperada do Excel:
    | codigo | nomecli | nomepos | end | bairro | cep | nomecid | estado |
    |--------|---------|---------|-----|--------|-----|---------|--------|
    | PT001  | Cliente | Posto 1 | Rua | Centro | ... | Cidade  | RS     |
    
O script tenta mapear automaticamente as colunas (case-insensitive, com variações):
    - codigo: "codigo", "código", "id", "cod"
    - nomecli: "nomecli", "cliente", "nome_cliente", "client"
    - nomepos: "nomepos", "posto", "nome_posto", "posto_trabalho"
    - end: "end", "endereco", "endereço", "rua", "logradouro"
    - bairro: "bairro"
    - cep: "cep"
    - nomecid: "nomecid", "cidade", "city", "municipio", "município"
    - estado: "estado", "uf", "est", "sigla"
"""

import sys
import os
from pathlib import Path
from typing import Dict, Optional, List
import re

# Adicionar raiz do projeto ao path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    import pandas as pd
except ImportError:
    print("ERRO: Biblioteca 'pandas' não encontrada.")
    print("Instale com: pip install pandas openpyxl")
    sys.exit(1)

from projects.modulo2.db import salvar_posto, init_db, get_conn


# Mapeamento de nomes de colunas possíveis (case-insensitive)
COLUMN_MAPPING = {
    "codigo": ["codigo", "código", "id", "cod", "code", "codcli", "codpos", "cod_cli", "cod_pos"],
    "nomecli": ["nomecli", "cliente", "nome_cliente", "client", "nome cliente", "nomefil"],
    "nomepos": ["nomepos", "posto", "nome_posto", "posto_trabalho", "nome posto", "posto trabalho"],
    "end": ["end", "endereco", "endereço", "rua", "logradouro", "address"],
    "bairro": ["bairro", "bairro", "neighborhood", "distrito"],
    "cep": ["cep", "cep", "zip", "zipcode"],
    "nomecid": ["nomecid", "cidade", "city", "municipio", "município", "munic"],
    "estado": ["estado", "uf", "est", "sigla", "state"]
}


def normalizar_nome_coluna(nome: str) -> str:
    """Normaliza nome de coluna para comparação (remove espaços, acentos, lowercase)"""
    import unicodedata
    nome = str(nome).strip()
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = re.sub(r'\s+', '_', nome.lower())
    return nome


def encontrar_coluna(df_columns: List[str], possiveis_nomes: List[str]) -> Optional[str]:
    """
    Encontra a coluna no DataFrame que corresponde a um dos nomes possíveis.
    Retorna o nome original da coluna ou None se não encontrar.
    """
    df_columns_normalized = {normalizar_nome_coluna(col): col for col in df_columns}
    
    for nome_possivel in possiveis_nomes:
        nome_normalizado = normalizar_nome_coluna(nome_possivel)
        if nome_normalizado in df_columns_normalized:
            return df_columns_normalized[nome_normalizado]
    
    return None


def mapear_colunas_excel(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Mapeia as colunas do Excel para os campos do banco de dados.
    Retorna dict com {campo_banco: nome_coluna_excel}
    """
    mapeamento = {}
    
    for campo_banco, nomes_possiveis in COLUMN_MAPPING.items():
        coluna_encontrada = encontrar_coluna(df.columns.tolist(), nomes_possiveis)
        mapeamento[campo_banco] = coluna_encontrada
        
        if coluna_encontrada:
            print(f"  [OK] '{coluna_encontrada}' -> {campo_banco}")
        else:
            print(f"  [ERRO] Campo '{campo_banco}' não encontrado no Excel")
    
    return mapeamento


def limpar_cep(cep: str) -> Optional[str]:
    """Limpa e formata CEP (remove caracteres não numéricos, completa com zeros)"""
    if pd.isna(cep) or not cep:
        return None
    
    cep_str = str(cep).strip()
    cep_str = re.sub(r'\D', '', cep_str)  # Remove não numéricos
    
    if not cep_str:
        return None
    
    # Completar com zeros à esquerda até 8 dígitos
    cep_str = cep_str.zfill(8)
    
    return cep_str[:8] if len(cep_str) >= 8 else None


def limpar_estado(estado: str) -> Optional[str]:
    """Limpa e formata estado (maiúsculas, máximo 2 caracteres)"""
    if pd.isna(estado) or not estado:
        return None
    
    estado_str = str(estado).strip().upper()
    
    # Se for nome completo, tentar converter para sigla (exemplo básico)
    estados_completos = {
        "RIO GRANDE DO SUL": "RS",
        "SANTA CATARINA": "SC",
        "PARANÁ": "PR",
        "PARANA": "PR",
        "SÃO PAULO": "SP",
        "SAO PAULO": "SP",
        "RIO DE JANEIRO": "RJ",
        "MINAS GERAIS": "MG"
    }
    
    if estado_str in estados_completos:
        estado_str = estados_completos[estado_str]
    
    return estado_str[:2] if estado_str else None


def processar_linha_excel(row: pd.Series, mapeamento: Dict[str, Optional[str]]) -> Optional[Dict]:
    """
    Processa uma linha do Excel e retorna dict com dados do posto.
    Retorna None se linha inválida.
    """
    try:
        # Criar código único baseado em codcli e codpos (se disponíveis)
        codigo = None
        codcli_val = None
        codpos_val = None
        
        # Buscar codcli
        for col in row.index:
            if 'codcli' in str(col).lower() or 'cod_cli' in str(col).lower():
                codcli_val = row.get(col)
                if pd.notna(codcli_val):
                    try:
                        codcli_int = int(codcli_val)
                        if codcli_int != -1:  # -1 parece ser código reservado
                            codcli_val = str(codcli_int)
                        else:
                            codcli_val = None
                    except:
                        codcli_val = str(codcli_val).strip() if codcli_val else None
                break
        
        # Buscar codpos
        for col in row.index:
            if 'codpos' in str(col).lower() or 'cod_pos' in str(col).lower():
                codpos_val = row.get(col)
                if pd.notna(codpos_val):
                    try:
                        codpos_val = str(int(codpos_val))
                    except:
                        codpos_val = str(codpos_val).strip() if codpos_val else None
                break
        
        # Criar código único: codcli-codpos
        if codcli_val and codpos_val:
            codigo = f"{codcli_val}-{codpos_val}"
        elif codcli_val:
            codigo = codcli_val
        elif codpos_val:
            codigo = codpos_val
        else:
            # Tentar usar mapeamento se existir
            if mapeamento["codigo"]:
                codigo_val = row.get(mapeamento["codigo"])
                codigo = str(codigo_val).strip() if not pd.isna(codigo_val) else None
        
        nomecli = None
        if mapeamento["nomecli"]:
            nomecli_val = row.get(mapeamento["nomecli"])
            nomecli = str(nomecli_val).strip() if not pd.isna(nomecli_val) else None
        
        nomepos = None
        if mapeamento["nomepos"]:
            nomepos_val = row.get(mapeamento["nomepos"])
            nomepos = str(nomepos_val).strip() if not pd.isna(nomepos_val) else None
        
        # Validar campos obrigatórios
        if not nomecli or not nomepos:
            return None  # Campos obrigatórios ausentes
        
        # Extrair campos opcionais
        end = None
        if mapeamento["end"]:
            end_val = row.get(mapeamento["end"])
            end = str(end_val).strip() if not pd.isna(end_val) else None
        
        bairro = None
        if mapeamento["bairro"]:
            bairro_val = row.get(mapeamento["bairro"])
            bairro = str(bairro_val).strip() if not pd.isna(bairro_val) else None
        
        cep = None
        if mapeamento["cep"]:
            cep_val = row.get(mapeamento["cep"])
            cep = limpar_cep(cep_val)
        
        nomecid = None
        if mapeamento["nomecid"]:
            nomecid_val = row.get(mapeamento["nomecid"])
            nomecid = str(nomecid_val).strip() if not pd.isna(nomecid_val) else None
        
        estado = None
        if mapeamento["estado"]:
            estado_val = row.get(mapeamento["estado"])
            estado = limpar_estado(estado_val)
        
        # Garantir que código existe (já foi criado acima, mas fallback se necessário)
        if not codigo:
            # Fallback: criar código baseado em nomecli + nomepos
            codigo_base = f"{nomecli[:10]}_{nomepos[:10]}"
            codigo_base = re.sub(r'[^a-zA-Z0-9_]', '_', codigo_base)
            codigo = codigo_base.upper()
        
        return {
            "codigo": codigo,
            "nomecli": nomecli,
            "nomepos": nomepos,
            "end": end,
            "bairro": bairro,
            "cep": cep,
            "nomecid": nomecid,
            "estado": estado
        }
    
    except Exception as e:
        print(f"    ERRO ao processar linha: {e}")
        return None


def importar_postos_excel(caminho_excel: str, sheet_name: str = 0, skip_rows: int = 0) -> Dict:
    """
    Importa postos de trabalho de arquivo Excel.
    
    Args:
        caminho_excel: Caminho para o arquivo Excel (.xlsx ou .xls)
        sheet_name: Nome ou índice da planilha (padrão: 0 = primeira planilha)
        skip_rows: Número de linhas a pular no início (padrão: 0)
    
    Returns:
        dict com estatísticas da importação
    """
    print(f"\n{'='*70}")
    print(f"IMPORTAÇÃO DE POSTOS DE TRABALHO DO EXCEL")
    print(f"{'='*70}")
    print(f"Arquivo: {caminho_excel}")
    print(f"Planilha: {sheet_name}")
    print(f"Pular linhas: {skip_rows}")
    print()
    
    # Verificar se arquivo existe
    if not os.path.exists(caminho_excel):
        return {
            "success": False,
            "error": f"Arquivo não encontrado: {caminho_excel}",
            "total": 0,
            "importados": 0,
            "atualizados": 0,
            "erros": 0
        }
    
    # Inicializar banco de dados
    try:
        init_db()
        print("[OK] Banco de dados inicializado")
    except Exception as e:
        return {
            "success": False,
            "error": f"Erro ao inicializar banco: {e}",
            "total": 0,
            "importados": 0,
            "atualizados": 0,
            "erros": 0
        }
    
    # Ler Excel
    try:
        print(f"[OK] Lendo arquivo Excel...")
        df = pd.read_excel(caminho_excel, sheet_name=sheet_name, skiprows=skip_rows)
        print(f"[OK] {len(df)} linhas encontradas no Excel")
        print()
    except Exception as e:
        return {
            "success": False,
            "error": f"Erro ao ler Excel: {e}",
            "total": 0,
            "importados": 0,
            "atualizados": 0,
            "erros": 0
        }
    
    # Mostrar colunas encontradas
    print("Colunas encontradas no Excel:")
    for col in df.columns:
        print(f"  - {col}")
    print()
    
    # Mapear colunas
    print("Mapeando colunas do Excel para campos do banco:")
    mapeamento = mapear_colunas_excel(df)
    print()
    
    # Verificar campos obrigatórios
    if not mapeamento["nomecli"] or not mapeamento["nomepos"]:
        return {
            "success": False,
            "error": "Campos obrigatórios não encontrados: 'nomecli' (cliente) e 'nomepos' (posto)",
            "total": len(df),
            "importados": 0,
            "atualizados": 0,
            "erros": 0
        }
    
    # Verificar códigos existentes antes de importar (para distinguir inserção de atualização)
    print("Verificando postos existentes no banco...")
    conn = None
    codigos_existentes = set()
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT codigo FROM modulo2_postos_trabalho WHERE codigo IS NOT NULL")
        codigos_existentes = {row[0] for row in cur.fetchall() if row[0]}
        cur.close()
        conn.close()
        print(f"[OK] {len(codigos_existentes)} postos já existem no banco")
    except Exception as e:
        print(f"[AVISO] Erro ao verificar postos existentes: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass
    
    print()
    print(f"Processando {len(df)} linhas...")
    print()
    
    # Processar cada linha
    importados = 0
    atualizados = 0
    erros = 0
    linhas_invalidas = 0
    
    for idx, row in df.iterrows():
        try:
            # Processar linha
            posto_data = processar_linha_excel(row, mapeamento)
            
            if not posto_data:
                linhas_invalidas += 1
                continue
            
            # Verificar se é inserção ou atualização
            codigo = posto_data.get("codigo")
            is_atualizacao = codigo and codigo in codigos_existentes
            
            # Salvar no banco
            posto_id = salvar_posto(posto_data)
            
            if posto_id:
                if is_atualizacao:
                    atualizados += 1
                else:
                    importados += 1
                    # Adicionar ao conjunto de códigos existentes para próximas iterações
                    if codigo:
                        codigos_existentes.add(codigo)
            else:
                erros += 1
                print(f"  [ERRO] Erro ao salvar linha {idx + 1 + skip_rows}: {posto_data.get('nomecli')} - {posto_data.get('nomepos')}")
            
            # Progresso a cada 50 linhas
            if (idx + 1) % 50 == 0:
                print(f"  Progresso: {idx + 1}/{len(df)} ([OK] {importados} novos, [UPD] {atualizados} atualizados, [ERRO] {erros} erros, [INV] {linhas_invalidas} invalidas)")
        
        except Exception as e:
            erros += 1
            print(f"  [ERRO] ERRO na linha {idx + 1 + skip_rows}: {e}")
            continue
    
    # Resumo final
    print()
    print("="*70)
    print("IMPORTACAO CONCLUIDA")
    print("="*70)
    print(f"  Total de linhas processadas: {len(df)}")
    print(f"  [OK] Novos postos inseridos: {importados}")
    print(f"  [UPD] Postos atualizados: {atualizados}")
    print(f"  [INV] Linhas invalidas (sem nomecli ou nomepos): {linhas_invalidas}")
    print(f"  [ERRO] Erros: {erros}")
    print()
    
    return {
        "success": True,
        "total": len(df),
        "importados": importados,
        "atualizados": atualizados,
        "linhas_invalidas": linhas_invalidas,
        "erros": erros
    }


def main():
    """Função principal para execução via linha de comando"""
    if len(sys.argv) < 2:
        print("Uso: python -m projects.modulo2.importar_postos_excel <caminho_do_arquivo.xlsx> [sheet_name] [skip_rows]")
        print()
        print("Exemplos:")
        print("  python -m projects.modulo2.importar_postos_excel postos.xlsx")
        print("  python -m projects.modulo2.importar_postos_excel postos.xlsx 'Planilha1'")
        print("  python -m projects.modulo2.importar_postos_excel postos.xlsx 0 1  # pula primeira linha (cabeçalho)")
        sys.exit(1)
    
    caminho_excel = sys.argv[1]
    sheet_name = sys.argv[2] if len(sys.argv) > 2 else 0
    skip_rows = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    
    # Tentar converter sheet_name para int se for número
    try:
        sheet_name = int(sheet_name)
    except ValueError:
        pass  # Manter como string (nome da planilha)
    
    resultado = importar_postos_excel(caminho_excel, sheet_name=sheet_name, skip_rows=skip_rows)
    
    if not resultado["success"]:
        print(f"\nERRO: {resultado.get('error', 'Erro desconhecido')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
