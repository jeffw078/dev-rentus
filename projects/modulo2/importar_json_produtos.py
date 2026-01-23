# projects/modulo2/importar_json_produtos.py
"""
Script para importar dados do arquivo produtos_com_posto.json para o banco de dados.
Processa produtos, agrupa por chave de NF, cria NFes e itens, e identifica pendências.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

# Adicionar o diretório do projeto ao path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from projects.modulo2.db import get_conn, init_db


def carregar_json_produtos(caminho_json: Path) -> Dict:
    """Carrega o arquivo JSON de produtos."""
    if not caminho_json.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_json}")
    
    with open(caminho_json, 'r', encoding='utf-8') as f:
        return json.load(f)


def processar_e_salvar_produtos(dados_json: Dict, limpar_antes: bool = False):
    """
    Processa os dados do JSON e salva no banco de dados.
    
    Estrutura esperada:
    {
        "metadata": {...},
        "produtos": [
            {
                "chave_nf": "...",
                "empresa": "...",
                "cliente": "...",
                "posto_trabalho": "...",
                "codpos": "...",
                "produto": "...",
                "ncm": "...",
                "categoria": "...",
                "quantidade": ...,
                "valor_unitario": ...,
                "valor_total_produto": ...,
                "end_cliente": "...",
                "nome_entrega": "...",
                "motivo_nao_identificado": "...",
                "sugestoes_postos": "...",
                "_status": "OK" | "PENDENTE",
                "_eh_limpeza": bool,
                "_score": ...
            }
        ]
    }
    """
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Inicializar banco se necessário
        init_db()
        
        if limpar_antes:
            print("[IMPORT] Limpando dados anteriores...")
            # Limpar apenas dados relacionados ao JSON (manter estrutura)
            cur.execute("DELETE FROM modulo2_pendencias WHERE motivo LIKE '%JSON%' OR motivo IS NULL")
            cur.execute("DELETE FROM modulo2_nfe_itens WHERE nfe_id IN (SELECT id FROM modulo2_nfe WHERE chave_acesso LIKE 'JSON%')")
            cur.execute("DELETE FROM modulo2_nfe WHERE chave_acesso LIKE 'JSON%'")
            conn.commit()
            print("[IMPORT] Dados anteriores removidos.")
        
        produtos = dados_json.get("produtos", [])
        metadata = dados_json.get("metadata", {})
        
        print(f"[IMPORT] Processando {len(produtos)} produtos de {metadata.get('total_xmls', '?')} NFes...")
        
        # Agrupar produtos por chave_nf
        nfes_por_chave = defaultdict(list)
        for produto in produtos:
            chave_nf = produto.get("chave_nf", "")
            if chave_nf:
                nfes_por_chave[chave_nf].append(produto)
        
        print(f"[IMPORT] Encontradas {len(nfes_por_chave)} NFes únicas.")
        
        # Processar cada NFe
        nfes_processadas = 0
        produtos_processados = 0
        pendencias_criadas = 0
        
        for chave_nf, produtos_nf in nfes_por_chave.items():
            # Pegar o primeiro produto para dados da NFe
            primeiro_produto = produtos_nf[0]
            
            # Calcular valores totais da NFe
            valor_total_nf = sum(p.get("valor_total_produto", 0) for p in produtos_nf)
            
            # Verificar se NFe já existe
            cur.execute("SELECT id FROM modulo2_nfe WHERE chave_acesso = ?", (chave_nf,))
            nfe_existente = cur.fetchone()
            
            if nfe_existente:
                nfe_id = nfe_existente[0]
                print(f"[IMPORT] NFe {chave_nf[:20]}... já existe (ID: {nfe_id}), pulando...")
            else:
                # Criar NFe
                empresa_nome = primeiro_produto.get("empresa", "DESCONHECIDO")
                cliente = primeiro_produto.get("cliente", "")
                posto_trabalho = primeiro_produto.get("posto_trabalho", "")
                codpos = primeiro_produto.get("codpos", "")
                end_cliente = primeiro_produto.get("end_cliente", "")
                nome_entrega = primeiro_produto.get("nome_entrega", "")
                
                # Buscar ou criar empresa (usar ID 1 como padrão se não existir)
                cur.execute("SELECT id FROM modulo2_empresas LIMIT 1")
                empresa_row = cur.fetchone()
                empresa_id = empresa_row[0] if empresa_row else 1
                
                # Buscar posto_id se cliente e posto estiverem preenchidos
                posto_id = None
                if cliente and posto_trabalho and codpos:
                    cur.execute(
                        "SELECT id FROM modulo2_postos_trabalho WHERE codigo = ? AND nomecli = ? AND nomepos = ?",
                        (codpos, cliente, posto_trabalho)
                    )
                    posto_row = cur.fetchone()
                    if posto_row:
                        posto_id = posto_row[0]
                
                # Status da NFe: 'identificado' se todos os produtos estão OK, senão 'pendente'
                status_nfe = "identificado"
                tem_pendente = False
                
                for p in produtos_nf:
                    if p.get("_status") == "PENDENTE":
                        tem_pendente = True
                        status_nfe = "pendente"
                        break
                
                # Inserir NFe
                cur.execute("""
                    INSERT INTO modulo2_nfe (
                        empresa_id, chave_acesso, nsu, data_emissao, valor_total,
                        nome_emitente, nome_destinatario, endereco_entrega,
                        posto_id, status, xml
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    empresa_id,
                    chave_nf,
                    0,  # NSU não aplicável para JSON
                    datetime.now().isoformat(),  # Data de emissão (não temos no JSON)
                    valor_total_nf,
                    empresa_nome,
                    nome_entrega or cliente,
                    end_cliente,
                    posto_id,
                    status_nfe,
                    f"<NFe><chave>{chave_nf}</chave><origem>JSON</origem></NFe>"  # XML mínimo
                ))
                
                nfe_id = cur.lastrowid
                nfes_processadas += 1
                
                # Inserir itens da NFe
                for idx, produto in enumerate(produtos_nf, start=1):
                    cur.execute("""
                        INSERT INTO modulo2_nfe_itens (
                            nfe_id, numero_item, descricao_produto, ncm,
                            quantidade, valor_unitario, valor_total
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        nfe_id,
                        idx,
                        produto.get("produto", ""),
                        produto.get("ncm", ""),
                        produto.get("quantidade", 0),
                        produto.get("valor_unitario", 0),
                        produto.get("valor_total_produto", 0)
                    ))
                    produtos_processados += 1
                
                # Criar pendência se houver produtos pendentes
                if tem_pendente:
                    # Agrupar produtos pendentes da mesma NFe
                    produtos_pendentes = [p for p in produtos_nf if p.get("_status") == "PENDENTE"]
                    
                    # Criar uma pendência por produto pendente (ou agrupar?)
                    for produto_pendente in produtos_pendentes:
                        motivo = produto_pendente.get("motivo_nao_identificado", "Não identificado")
                        sugestoes = produto_pendente.get("sugestoes_postos", "")
                        
                        # Combinar motivo e sugestões
                        motivo_completo = motivo
                        if sugestoes:
                            motivo_completo += f"\n\nSugestões de Postos:\n{sugestoes}"
                        
                        cur.execute("""
                            INSERT INTO modulo2_pendencias (
                                nfe_id, chave_nfe, valor, fornecedor, cliente,
                                posto_trabalho, motivo, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            nfe_id,
                            chave_nf,
                            produto_pendente.get("valor_total_produto", 0),
                            empresa_nome,
                            cliente or "",
                            posto_trabalho or "",
                            motivo_completo,
                            "pendente"
                        ))
                        pendencias_criadas += 1
            
            # Commit a cada 100 NFes para evitar transações muito longas
            if nfes_processadas % 100 == 0:
                conn.commit()
                print(f"[IMPORT] Processadas {nfes_processadas} NFes...")
        
        # Commit final
        conn.commit()
        
        print(f"\n[IMPORT] Importação concluída!")
        print(f"  - NFes processadas: {nfes_processadas}")
        print(f"  - Produtos processados: {produtos_processados}")
        print(f"  - Pendências criadas: {pendencias_criadas}")
        
        return {
            "nfes_processadas": nfes_processadas,
            "produtos_processados": produtos_processados,
            "pendencias_criadas": pendencias_criadas
        }
        
    except Exception as e:
        conn.rollback()
        print(f"[IMPORT] ERRO: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    # Caminho do arquivo JSON (raiz do projeto)
    json_path = PROJECT_ROOT / "produtos_com_posto.json"
    
    if not json_path.exists():
        print(f"ERRO: Arquivo não encontrado: {json_path}")
        sys.exit(1)
    
    print(f"[IMPORT] Carregando JSON: {json_path}")
    dados = carregar_json_produtos(json_path)
    
    print(f"[IMPORT] Iniciando importação...")
    resultado = processar_e_salvar_produtos(dados, limpar_antes=True)
    
    print(f"\n[IMPORT] Concluido com sucesso!")
