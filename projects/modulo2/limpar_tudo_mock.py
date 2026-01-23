#!/usr/bin/env python3
"""
Script para limpar TODOS os dados mockados do banco de dados.
Remove:
- NFes com fornecedores mockados conhecidos
- NFes com CNPJs mockados
- Itens e pendências relacionadas
- Restaura apenas dados do arquivo produtos_com_posto.json
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from projects.modulo2.db import get_conn, _row_to_dict


# Fornecedores mockados conhecidos
FORNECEDORES_MOCK = [
    "FORNECEDOR ABC LTDA",
    "SUPPLY COMPANY XYZ",
    "SUPPLY COMANY XYZ",  # Versão com erro de digitação
    "DISTRIBUIDORA 123",
    "COMERCIAL DEF LTDA"
]

# CNPJs mockados conhecidos
CNPJS_MOCK = [
    "12817803000112",
    "08818229000140",
    "56419492000109",
    "12345678000190"  # CNPJ do destinatário mockado
]


def contar_dados_mock():
    """Conta dados mockados no banco"""
    conn = get_conn()
    cur = conn.cursor()
    
    nfes_fornecedores_mock = 0
    nfes_cnpj_mock = 0
    nfes_origem_json = 0
    
    # Buscar todas as NFes
    cur.execute("""
        SELECT id, chave_acesso, nome_emitente, cnpj_emitente, xml, status
        FROM modulo2_nfe
        ORDER BY id DESC
    """)
    
    for row in cur.fetchall():
        r = _row_to_dict(row)
        nome_emitente = (r.get("nome_emitente") or "").upper().strip()
        cnpj_emitente = (r.get("cnpj_emitente") or "").strip()
        xml_content = (r.get("xml") or "").upper()
        
        # Verificar se é fornecedor mockado
        if any(forn in nome_emitente for forn in FORNECEDORES_MOCK):
            nfes_fornecedores_mock += 1
        # Verificar se é CNPJ mockado
        elif cnpj_emitente in CNPJS_MOCK:
            nfes_cnpj_mock += 1
        # Verificar se é origem JSON
        elif "ORIGEM" in xml_content and "JSON" in xml_content:
            nfes_origem_json += 1
    
    cur.close()
    conn.close()
    
    return {
        "fornecedores_mock": nfes_fornecedores_mock,
        "cnpj_mock": nfes_cnpj_mock,
        "origem_json": nfes_origem_json,
        "total_mock": nfes_fornecedores_mock + nfes_cnpj_mock
    }


def remover_dados_mock(confirmar=False):
    """
    Remove TODOS os dados mockados do banco.
    Mantém apenas dados com origem JSON (produtos_com_posto.json).
    """
    print("=" * 70)
    print("LIMPEZA COMPLETA DE DADOS MOCKADOS DO MÓDULO 2")
    print("=" * 70)
    
    # Contar dados
    contagem = contar_dados_mock()
    
    print(f"\nDados mockados identificados:")
    print(f"  - NFes com fornecedores mockados: {contagem['fornecedores_mock']}")
    print(f"  - NFes com CNPJs mockados: {contagem['cnpj_mock']}")
    print(f"  - NFes com origem JSON: {contagem['origem_json']}")
    print(f"  - Total de NFes mockadas a remover: {contagem['total_mock']}")
    
    if contagem['total_mock'] == 0:
        print("\n[OK] Nenhuma NFe mockada encontrada no banco!")
        print("=" * 70)
        return
    
    if not confirmar:
        print("\n[!] Para realmente remover, execute:")
        print("    python projects/modulo2/limpar_tudo_mock.py --confirmar")
        print("=" * 70)
        return
    
    # Proceder com limpeza
    print("\n" + "=" * 70)
    print("INICIANDO LIMPEZA...")
    print("=" * 70)
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # 1. Encontrar IDs das NFes mockadas
        nfes_mock_ids = []
        
        cur.execute("""
            SELECT id, chave_acesso, nome_emitente, cnpj_emitente
            FROM modulo2_nfe
            ORDER BY id DESC
        """)
        
        for row in cur.fetchall():
            r = _row_to_dict(row)
            nome_emitente = (r.get("nome_emitente") or "").upper().strip()
            cnpj_emitente = (r.get("cnpj_emitente") or "").strip()
            
            if any(forn in nome_emitente for forn in FORNECEDORES_MOCK) or \
               cnpj_emitente in CNPJS_MOCK:
                nfes_mock_ids.append(r.get("id"))
        
        print(f"\nEncontradas {len(nfes_mock_ids)} NFes mockadas para remover")
        
        if not nfes_mock_ids:
            print("[OK] Nenhuma NFe mockada encontrada para remover")
            return
        
        # 2. Remover pendências relacionadas
        placeholders = ",".join("?" * len(nfes_mock_ids))
        cur.execute(f"""
            DELETE FROM modulo2_pendencias
            WHERE nfe_id IN ({placeholders})
        """, nfes_mock_ids)
        pendencias_removidas = cur.rowcount
        print(f"  ✓ Removidas {pendencias_removidas} pendências")
        
        # 3. Remover itens das NFes
        cur.execute(f"""
            DELETE FROM modulo2_nfe_itens
            WHERE nfe_id IN ({placeholders})
        """, nfes_mock_ids)
        itens_removidos = cur.rowcount
        print(f"  ✓ Removidos {itens_removidos} itens de NFes")
        
        # 4. Remover as NFes
        cur.execute(f"""
            DELETE FROM modulo2_nfe
            WHERE id IN ({placeholders})
        """, nfes_mock_ids)
        nfes_removidas = cur.rowcount
        print(f"  ✓ Removidas {nfes_removidas} NFes mockadas")
        
        # 5. Limpar dados da tabela de empresas que não têm mais NFes
        cur.execute("""
            DELETE FROM modulo2_empresas
            WHERE id NOT IN (SELECT DISTINCT empresa_id FROM modulo2_nfe)
            AND id NOT IN (SELECT DISTINCT empresa_id FROM modulo2_nsu_checkpoint)
        """)
        empresas_removidas = cur.rowcount
        if empresas_removidas > 0:
            print(f"  ✓ Removidas {empresas_removidas} empresas orfãs")
        
        conn.commit()
        
        print("\n" + "=" * 70)
        print("LIMPEZA CONCLUÍDA COM SUCESSO!")
        print("=" * 70)
        print(f"\nResumo da remoção:")
        print(f"  - NFes mockadas removidas: {nfes_removidas}")
        print(f"  - Itens removidos: {itens_removidos}")
        print(f"  - Pendências removidas: {pendencias_removidas}")
        print(f"  - Empresas orfãs removidas: {empresas_removidas}")
        print("\n[!] O banco foi limpo de todos os dados mockados.")
        print("[!] Agora você pode importar dados APENAS do arquivo produtos_com_posto.json")
        print("=" * 70)
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Limpar TODOS os dados mockados do banco")
    parser.add_argument("--confirmar", action="store_true", help="Confirmar remoção (sem isso, apenas lista)")
    
    args = parser.parse_args()
    
    remover_dados_mock(confirmar=args.confirmar)
