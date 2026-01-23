import requests

# Testar endpoint total-nfes
url = "http://127.0.0.1:8000/api/modulo2/dashboard/total-nfes"

try:
    response = requests.get(url)
    if response.ok:
        data = response.json()
        print("="*70)
        print("TESTE ENDPOINT: /api/modulo2/dashboard/total-nfes")
        print("="*70)
        print(f"Total NFes: {data.get('total_nfes', 0)}")
        print(f"Identificadas: {data.get('nfes_identificadas', 0)}")
        print(f"Pendentes: {data.get('nfes_pendentes', 0)}")
        print(f"Valor Total: R$ {data.get('valor_total', 0):,.2f}")
        print(f"Total Realizado: R$ {data.get('total_realizado', 0):,.2f}")
        print(f"Total Produtos: {data.get('total_produtos', 0)}")
        print("="*70)
        
        if abs(data.get('total_realizado', 0) - 666601.42) < 0.01:
            print("✅ VALOR TOTAL CORRETO!")
        else:
            print("❌ VALOR TOTAL INCORRETO!")
            print(f"   Esperado: R$ 666.601,42")
            print(f"   Recebido: R$ {data.get('total_realizado', 0):,.2f}")
    else:
        print(f"Erro HTTP {response.status_code}")
except Exception as e:
    print(f"Erro: {e}")
