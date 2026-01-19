#!/usr/bin/env python3
"""
Script para limpar todos os postos de trabalho do banco de dados.
Útil para recarregar dados frescos da planilha Excel.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from projects.modulo2.db import get_conn


def limpar_postos(confirmar=False):
    """
    Remove todos os postos de trabalho do banco.
    ATENÇÃO: Isso também remove dados relacionados (orçado, etc.)
    """
    print("=" * 60)
    print("LIMPEZA DE POSTOS DE TRABALHO")
    print("=" * 60)
    
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Contar postos antes
        cur.execute("SELECT COUNT(*) FROM modulo2_postos_trabalho")
        total_postos = cur.fetchone()[0]
        
        print(f"\nPostos de trabalho encontrados: {total_postos}")
        
        if total_postos == 0:
            print("\nOK: Nenhum posto encontrado. Banco ja esta limpo!")
            return
        
        if not confirmar:
            print("\nAVISO: Para realmente limpar, execute:")
            print("   python projects/modulo2/limpar_postos.py --confirmar")
            print("\nATENCAO: Isso removara:")
            print(f"   - {total_postos} postos de trabalho")
            print("   - Todos os valores orcados relacionados")
            print("   - As referencias de posto nas NFes (mas as NFes permanecem)")
            return
        
        print("\n" + "=" * 60)
        print("REMOVENDO POSTOS...")
        print("=" * 60)
        
        # Primeiro, remover valores orçados relacionados
        cur.execute("DELETE FROM modulo2_orcado_posto")
        orcado_removido = cur.rowcount
        
        # Remover referências de posto_id nas NFes (definir como NULL)
        cur.execute("UPDATE modulo2_nfe SET posto_id = NULL, status = 'pendente'")
        nfes_atualizadas = cur.rowcount
        
        # Remover postos de trabalho
        cur.execute("DELETE FROM modulo2_postos_trabalho")
        postos_removidos = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\nOK: Limpeza concluida:")
        print(f"   - {postos_removidos} postos removidos")
        print(f"   - {orcado_removido} valores orcados removidos")
        print(f"   - {nfes_atualizadas} NFes atualizadas (posto_id = NULL)")
        print("\nOK: Banco limpo! Agora voce pode recarregar a planilha.")
        
    except Exception as e:
        print(f"\nERRO ao limpar postos: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Limpar todos os postos de trabalho do banco")
    parser.add_argument("--confirmar", action="store_true", help="Confirmar limpeza (sem isso, apenas mostra)")
    
    args = parser.parse_args()
    
    limpar_postos(confirmar=args.confirmar)
