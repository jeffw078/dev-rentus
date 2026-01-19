# projects/modulo2/config.py

import os
from pathlib import Path
from dotenv import load_dotenv

# ================================
# CARREGAR VARIÁVEIS DE AMBIENTE
# ================================
# Procura por .env na raiz do projeto
# Este arquivo está em: projects/modulo2/config.py
# Raiz do projeto está em: ../../ (subindo 2 níveis)
CONFIG_DIR = Path(__file__).resolve().parent  # projects/modulo2/
PROJECT_ROOT = CONFIG_DIR.parent.parent       # raiz do projeto

env_path = PROJECT_ROOT / ".env"

# Carregar arquivo .env se existir
if env_path.exists():
    load_dotenv(env_path)
    print(f"[CONFIG] Arquivo .env carregado de: {env_path}")
else:
    # Se não encontrar, tentar carregar de qualquer lugar (fallback)
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)
    print(f"[CONFIG] .env não encontrado em {env_path}, usando variáveis de ambiente do sistema")

# ================================
# MODO DE DESENVOLVIMENTO
# ================================
# Define se o sistema está em modo desenvolvimento
# Em modo DEV, as consultas à SEFAZ são mockadas
# Lê do arquivo .env ou variável de ambiente (com prioridade para variável de ambiente)
DEV_MODE = os.getenv("MODULO2_DEV_MODE", "true").lower() in ("true", "1", "yes")

print(f"[CONFIG] Modo de desenvolvimento: {'ATIVADO' if DEV_MODE else 'DESATIVADO'}")
