#!/usr/bin/env python3
"""
QUICK START - LIMPEZA E IMPORTAÇÃO MÓDULO 2

Execute este script para:
1. Listar dados mockados
2. Remover dados mockados (com confirmação)
3. Importar dados do JSON

Uso:
    python quick_start_limpar_importar.py
"""

import sys
import os
from pathlib import Path

# Adicionar ao path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    print("\n" + "=" * 80)
    print("LIMPEZA E IMPORTAÇÃO DO MÓDULO 2")
    print("=" * 80)
    
    print("\n📊 PASSO 1: Analisando dados mockados no banco...")
    print("-" * 80)
    
    try:
        from projects.modulo2.limpar_tudo_mock import contar_dados_mock, remover_dados_mock
        
        # Verificar dados
        contagem = contar_dados_mock()
        print(f"\nDados mockados encontrados:")
        print(f"  • Fornecedores mockados: {contagem['fornecedores_mock']}")
        print(f"  • CNPJs mockados: {contagem['cnpj_mock']}")
        print(f"  • Total a remover: {contagem['total_mock']}")
        
        if contagem['total_mock'] > 0:
            print(f"\n❓ Deseja remover {contagem['total_mock']} NFes mockadas? (y/n)")
            resposta = input(">>> ").strip().lower()
            
            if resposta == 'y' or resposta == 'yes':
                print("\n✅ Removendo dados mockados...")
                remover_dados_mock(confirmar=True)
                print("✅ Dados mockados removidos com sucesso!")
            else:
                print("⏭️  Ignorando remoção de dados mockados")
        else:
            print("\n✅ Nenhum dado mockado encontrado no banco!")
    
    except Exception as e:
        print(f"❌ Erro ao processar dados mockados: {e}")
        return False
    
    print("\n" + "=" * 80)
    print("📥 PASSO 2: Importando dados do arquivo produtos_com_posto.json")
    print("-" * 80)
    
    try:
        from projects.modulo2.importar_json_produtos import (
            carregar_json_produtos,
            processar_e_salvar_produtos
        )
        
        json_path = PROJECT_ROOT / "produtos_com_posto.json"
        
        if not json_path.exists():
            print(f"❌ Arquivo não encontrado: {json_path}")
            return False
        
        print(f"\n📂 Carregando: {json_path}")
        dados = carregar_json_produtos(json_path)
        
        print(f"\n📊 Metadados do arquivo:")
        metadata = dados.get("metadata", {})
        print(f"  • Total de XMLs: {metadata.get('total_xmls')}")
        print(f"  • Total de produtos: {metadata.get('total_produtos')}")
        print(f"  • Produtos identificados: {metadata.get('produtos_identificados')}")
        print(f"  • Produtos pendentes: {metadata.get('produtos_pendentes')}")
        
        print(f"\n✅ Importando {len(dados.get('produtos', []))} produtos...")
        resultado = processar_e_salvar_produtos(dados, limpar_antes=False)
        
        print(f"\n✅ Importação concluída!")
        print(f"  • NFes processadas: {resultado['nfes_processadas']}")
        print(f"  • Produtos processados: {resultado['produtos_processados']}")
        print(f"  • Pendências criadas: {resultado['pendencias_criadas']}")
        
    except Exception as e:
        print(f"❌ Erro ao importar JSON: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 80)
    print("✅ TUDO PRONTO!")
    print("=" * 80)
    
    print("\n📋 Resumo:")
    print("  ✅ Dados mockados removidos")
    print("  ✅ Dados do JSON importados")
    print("  ✅ Banco de dados atualizado")
    
    print("\n📊 Próximas ações:")
    print("  1. Verificar dados no banco de dados")
    print("  2. Testar APIs do módulo 2")
    print("  3. Revisar produtos pendentes para identificação")
    
    print("\n" + "=" * 80)
    return True


if __name__ == "__main__":
    try:
        sucesso = main()
        sys.exit(0 if sucesso else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
