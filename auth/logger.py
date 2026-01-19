# auth/logger.py
# Sistema de logs formatados para console

from datetime import datetime


def log(mensagem: str, nivel: str = "INFO"):
    """
    Imprime mensagem com timestamp no console
    
    Args:
        mensagem: Mensagem a ser exibida
        nivel: Nível do log (INFO, WARNING, ERROR, SUCCESS, DEBUG)
    """
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    # Cores ANSI para terminal (opcional, funciona em alguns terminais)
    cores = {
        "INFO": "\033[36m",      # Ciano
        "WARNING": "\033[33m",   # Amarelo
        "ERROR": "\033[31m",     # Vermelho
        "SUCCESS": "\033[32m",   # Verde
        "DEBUG": "\033[35m",     # Magenta
        "RESET": "\033[0m"       # Reset
    }
    
    cor = cores.get(nivel.upper(), "")
    reset = cores["RESET"]
    
    # Formato: [DD/MM/YYYY HH:MM:SS] [NIVEL] Mensagem
    print(f"[{timestamp}] [{cor}{nivel.upper()}{reset}] {mensagem}")


def log_info(mensagem: str):
    """Log de informação"""
    log(mensagem, "INFO")


def log_success(mensagem: str):
    """Log de sucesso"""
    log(mensagem, "SUCCESS")


def log_warning(mensagem: str):
    """Log de aviso"""
    log(mensagem, "WARNING")


def log_error(mensagem: str):
    """Log de erro"""
    log(mensagem, "ERROR")


def log_debug(mensagem: str):
    """Log de debug"""
    log(mensagem, "DEBUG")
