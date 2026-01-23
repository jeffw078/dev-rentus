import requests
import time

# Aguardar servidor iniciar
print("Aguardando servidor iniciar...")
time.sleep(5)

# Testar API corrigida
try:
    url = 'http://127.0.0.1:8000/api/modulo2/totais-gerais'
    params = {'data_ini': '2026-01-01', 'data_fim': '2026-01-23'}
    
    print(f"\nTestando: {url}")
    print(f"Parâmetros: {params}")
    
    r = requests.get(url, params=params, timeout=10)
    print(f'\n✅ Status HTTP: {r.status_code}')
    
    if r.status_code == 200:
        data = r.json()
        print(f"\n=== RESULTADO CORRIGIDO ===")
        print(f"Total Orçado: R$ {data['total_orcado']:,.2f}")
        print(f"Total Realizado: R$ {data['total_realizado']:,.2f}")
        print(f"Status (diferença): R$ {data['status']:,.2f}")
        print(f"Percentual: {data['percentual']:.2f}%")
        
        print(f"\n=== VALORES ESPERADOS ===")
        print(f"Total Orçado esperado: R$ 74.944.400,00 (2.711 postos)")
        print(f"Total Realizado esperado: R$ 666.601,42 (531 NFes)")
    else:
        print(f"❌ Erro: {r.text}")
        
except requests.exceptions.ConnectionError:
    print("❌ Servidor não está rodando em http://127.0.0.1:8000")
except Exception as e:
    print(f"❌ Erro: {e}")
