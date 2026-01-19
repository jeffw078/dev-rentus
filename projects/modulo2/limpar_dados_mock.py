#!/usr/bin/env python3
"""
Script para identificar e remover dados mockados do banco de dados.
Dados mockados podem ter sido importados antes de remover a estrutura DEV.

Critérios de identificação:
- Fornecedores mockados conhecidos
- Chaves de acesso com padrão específico
- XMLs com características de mock
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from projects.modulo2.db import get_conn, _row_to_dict


# Fornecedores mockados conhecidos (usados em _gerar_xml_mock)
FORNECEDORES_MOCK = [
    "FORNECEDOR ABC LTDA",
    "SUPPLY COMPANY XYZ",
    "SUPPLY COMANY XYZ",  # Versão com erro de digitação
    "DISTRIBUIDORA 123",
    "COMERCIAL DEF LTDA"
]

# Postos mockados conhecidos
POSTOS_MOCK = [
    "POSTO CENTRAL",
    "CLIENTE"
]


def identificar_dados_mock():
    """Identifica dados mockados no banco"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Buscar todas as NFes
    cur.execute("""
        SELECT id, chave_acesso, nome_emitente, valor_total, data_emissao, status
        FROM modulo2_nfe
        ORDER BY data_importacao DESC
    """)
    
    nfes_mock = []
    nfes_reais = []
    
    for row in cur.fetchall():
        r = _row_to_dict(row)
        nome_emitente = (r.get("nome_emitente") or "").upper().strip()
        
        # Verificar se é fornecedor mockado
        is_mock = False
        motivo = ""
        
        if any(forn in nome_emitente for forn in FORNECEDORES_MOCK):
            is_mock = True
            motivo = f"Fornecedor mockado: {r.get('nome_emitente')}"
        elif nome_emitente in ["DESCONHECIDO", ""]:
            # Pode ser mock ou real (investigar mais)
            # Por padrão, vamos manter se não tiver outras características
            pass
        
        if is_mock:
            nfes_mock.append({
                "id": r.get("id"),
                "chave": r.get("chave_acesso"),
                "fornecedor": r.get("nome_emitente"),
                "valor": r.get("valor_total"),
                "data": r.get("data_emissao"),
                "motivo": motivo
            })
        else:
            nfes_reais.append(r.get("id"))
    
    cur.close()
    conn.close()
    
    return nfes_mock, nfes_reais


def remover_dados_mock(confirmar=False):
    """
    Remove dados mockados do banco.
    Se confirmar=False, apenas mostra o que será removido.
    """
    print("=" * 60)
    print("IDENTIFICAÇÃO DE DADOS MOCKADOS")
    print("=" * 60)
    
    nfes_mock, nfes_reais = identificar_dados_mock()
    
    print(f"\nNFes mockadas encontradas: {len(nfes_mock)}")
    print(f"NFes reais: {len(nfes_reais)}")
    
    if nfes_mock:
        print("\nNFes mockadas identificadas:")
        print("-" * 60)
        for nfe in nfes_mock[:10]:  # Mostrar até 10
            print(f"  ID: {nfe['id']} | Chave: {nfe['chave'][:20]}...")
            print(f"    Fornecedor: {nfe['fornecedor']}")
            print(f"    Valor: R$ {nfe['valor']:.2f} | Data: {nfe['data']}")
            print(f"    Motivo: {nfe['motivo']}")
            print()
        
        if len(nfes_mock) > 10:
            print(f"  ... e mais {len(nfes_mock) - 10} NFes mockadas")
        
        if confirmar:
            print("\n" + "=" * 60)
            print("REMOVENDO DADOS MOCKADOS...")
            print("=" * 60)
            
            conn = get_conn()
            cur = conn.cursor()
            
            ids_para_remover = [nfe["id"] for nfe in nfes_mock]
            
            pendencias_removidas = 0
            itens_removidos = 0
            
            # Remover pendências relacionadas (se a tabela existir)
            try:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modulo2_pendencias'")
                if cur.fetchone():
                    cur.execute("""
                        DELETE FROM modulo2_pendencias
                        WHERE nfe_id IN ({})
                    """.format(",".join("?" * len(ids_para_remover))), ids_para_remover)
                    pendencias_removidas = cur.rowcount
            except Exception as e:
                print(f"[AVISO] Erro ao remover pendências: {e}")
            
            # Remover itens das NFes (se a tabela existir)
            try:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modulo2_nfe_itens'")
                if cur.fetchone():
                    cur.execute("""
                        DELETE FROM modulo2_nfe_itens
                        WHERE nfe_id IN ({})
                    """.format(",".join("?" * len(ids_para_remover))), ids_para_remover)
                    itens_removidos = cur.rowcount
            except Exception as e:
                print(f"[AVISO] Erro ao remover itens: {e}")
            
            # Remover as NFes
            cur.execute("""
                DELETE FROM modulo2_nfe
                WHERE id IN ({})
            """.format(",".join("?" * len(ids_para_remover))), ids_para_remover)
            nfes_removidas = cur.rowcount
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"\n[OK] Removido com sucesso:")
            print(f"  - {nfes_removidas} NFes mockadas")
            print(f"  - {itens_removidos} Itens de NFes")
            print(f"  - {pendencias_removidas} Pendências relacionadas")
            print("\n[AVISO] Banco de dados limpo de dados mockados!")
        else:
            print("\n[AVISO] Para realmente remover, execute:")
            print("   python projects/modulo2/limpar_dados_mock.py --confirmar")
    else:
        print("\n[OK] Nenhuma NFe mockada encontrada no banco!")
    
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Identificar e remover dados mockados do banco")
    parser.add_argument("--confirmar", action="store_true", help="Confirmar remoção (sem isso, apenas lista)")
    
    args = parser.parse_args()
    
    remover_dados_mock(confirmar=args.confirmar)
